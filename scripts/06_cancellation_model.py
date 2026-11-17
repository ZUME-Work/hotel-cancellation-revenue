"""Cancellation model, deposit-policy simulation and A/B test sizing.

Run after build_db.py:  python scripts/06_cancellation_model.py
Writes outputs/tables/model_*.csv, policy_*.csv, ab_*.csv and outputs/charts/*.png
"""
from pathlib import Path

import duckdb
import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

ROOT = Path(__file__).resolve().parents[1]
TAB, CHART = ROOT / "outputs" / "tables", ROOT / "outputs" / "charts"
TAB.mkdir(parents=True, exist_ok=True)
CHART.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# 1. Data: block level (one row per distinct booking record), as decided in README
# ---------------------------------------------------------------------------
con = duckdb.connect(str(ROOT / "hotel.duckdb"), read_only=True)
df = con.sql("SELECT * FROM bookings_block").df()
con.close()
df["arrival_date"] = pd.to_datetime(df["arrival_date"])
df["arrival_month"] = df["arrival_date"].dt.month.astype(str)

# Only fields known when the booking is made.
# Excluded on purpose (see README "Leakage"):
#   reservation_status        -> is the outcome
#   required_car_parking_spaces -> 0% cancellation when > 0: recorded at arrival
#   country                   -> may be confirmed at check-in in the source system
#   assigned_room_type, booking_changes -> happen after booking (dropped in SQL)
NUM = ["lead_time", "nights", "adr", "adults", "children", "babies", "n_rooms",
       "previous_cancellations", "previous_bookings_not_canceled",
       "total_of_special_requests", "is_repeated_guest"]
CAT = ["hotel", "market_segment", "distribution_channel", "deposit_type",
       "customer_type", "arrival_month", "has_agent", "has_company"]
for c in ["has_agent", "has_company"]:
    df[c] = df[c].astype(str)
TARGET = "is_canceled"

# Time-based split: train on arrivals up to 2016, test on 2017 (Jan-Aug).
train = df[df.arrival_date < "2017-01-01"].copy()
test = df[df.arrival_date >= "2017-01-01"].copy()

pre = ColumnTransformer([
    ("num", StandardScaler(), NUM),
    ("cat", OneHotEncoder(handle_unknown="ignore", min_frequency=20), CAT),
])
models = {
    "Logistic regression": Pipeline([("pre", pre), ("clf", LogisticRegression(max_iter=2000, C=1.0))]),
    "Gradient boosting": Pipeline([
        ("pre", ColumnTransformer([
            ("num", "passthrough", NUM),
            ("cat", OneHotEncoder(handle_unknown="ignore", min_frequency=20, sparse_output=False), CAT),
        ])),
        ("clf", HistGradientBoostingClassifier(max_iter=300, learning_rate=0.05,
                                               max_leaf_nodes=31, random_state=42)),
    ]),
}

rows, preds = [], {}
for name, m in models.items():
    m.fit(train[NUM + CAT], train[TARGET])
    p = m.predict_proba(test[NUM + CAT])[:, 1]
    preds[name] = p
    top = test.assign(p=p).nlargest(int(len(test) * 0.10), "p")
    rows.append({
        "model": name,
        "test_auc": round(roc_auc_score(test[TARGET], p), 3),
        "test_brier": round(brier_score_loss(test[TARGET], p), 3),
        "mean_predicted_pct": round(p.mean() * 100, 1),
        "actual_cancel_pct": round(test[TARGET].mean() * 100, 1),
        "top10pct_actual_cancel_pct": round(top[TARGET].mean() * 100, 1),
    })
perf = pd.DataFrame(rows)
perf.to_csv(TAB / "model_performance.csv", index=False)
print(perf.to_string(index=False))

best = perf.sort_values("test_auc", ascending=False).iloc[0]["model"]
test["p_cancel"] = preds[best]
print(f"Using {best} for the policy simulation")

# Logistic coefficients for interpretation (direction, not causation)
lr = models["Logistic regression"]
names = lr.named_steps["pre"].get_feature_names_out()
coef = pd.DataFrame({"feature": names, "coef": lr.named_steps["clf"].coef_[0]})
coef["abs"] = coef.coef.abs()
coef.sort_values("abs", ascending=False).head(15).drop(columns="abs") \
    .round(3).to_csv(TAB / "model_top_coefficients.csv", index=False)

# Calibration by decile (test set)
test["decile"] = pd.qcut(test.p_cancel.rank(method="first"), 10, labels=range(1, 11))
calib = test.groupby("decile", observed=True).agg(
    blocks=(TARGET, "size"),
    predicted_pct=("p_cancel", lambda s: round(s.mean() * 100, 1)),
    actual_pct=(TARGET, lambda s: round(s.mean() * 100, 1)),
).reset_index()
calib.to_csv(TAB / "model_calibration_deciles.csv", index=False)

fig, ax = plt.subplots(figsize=(6, 4.5))
ax.plot([0, 100], [0, 100], ls="--", c="#999", lw=1)
ax.plot(calib.predicted_pct, calib.actual_pct, marker="o", c="#2b5c8a")
ax.set_xlabel("Predicted cancel % (decile mean)")
ax.set_ylabel("Actual cancel % (2017 test set)")
ax.set_title(f"{best}: calibration on unseen 2017 bookings", fontsize=10)
ax.spines[["top", "right"]].set_visible(False)
fig.tight_layout()
fig.savefig(CHART / "model_calibration.png", dpi=150)

# ---------------------------------------------------------------------------
# 2. Policy simulation on the 2017 test set (room level = block x n_rooms)
#    Policy: charge a first-night deposit, kept on cancellation, to the
#    top-k% riskiest bookings. Bookings that are put off and walk away lose
#    the revenue they would have realized.
# ---------------------------------------------------------------------------
t = test.copy()
t["first_night"] = t.adr                                   # deposit = 1 night ADR
t["realized"] = t.adr * t.nights * (1 - t[TARGET]) * t.n_rooms
t["deposit_kept_if_cancel"] = t.first_night * t[TARGET] * t.n_rooms
base_realized = t.realized.sum()

# Existing Non Refund bookings already pay up front: never target them again.
eligible = t[t.deposit_type == "No Deposit"]


def simulate(target_share, walk_away, cancel_reduction, rank_col="p_cancel"):
    """Change in realized revenue (EUR) vs doing nothing.

    target_share     share of eligible bookings that get the deposit
    walk_away        share of targeted bookings that no longer book
    cancel_reduction relative drop in cancellation among targeted bookings that stay
    """
    k = int(len(eligible) * target_share)
    tgt = eligible.nlargest(k, rank_col) if rank_col else eligible.sample(k, random_state=0)
    stay = 1 - walk_away
    full_value = (tgt.adr * tgt.nights * tgt.n_rooms)
    # Revenue the targeted group realizes today
    today = tgt.realized.sum()
    # With the policy, stayers cancel less, and cancellers forfeit one night
    p_c = tgt[TARGET] * (1 - cancel_reduction)
    with_policy = stay * ((full_value * (1 - p_c)).sum()
                          + (tgt.first_night * tgt.n_rooms * p_c).sum())
    return with_policy - today, k


grid = []
for share in [0.05, 0.10, 0.20]:
    for walk in [0.0, 0.10, 0.20, 0.30]:
        for red in [0.0, 0.25]:
            d_model, k = simulate(share, walk, red, "p_cancel")
            d_rand, _ = simulate(share, walk, red, None)
            grid.append({
                "target_share_pct": int(share * 100), "bookings_targeted": k,
                "walk_away_pct": int(walk * 100), "cancel_reduction_pct": int(red * 100),
                "delta_rev_model_targeted_eur": round(d_model),
                "delta_rev_random_targeted_eur": round(d_rand),
                "delta_pct_of_total_realized": round(d_model / base_realized * 100, 2),
            })
policy = pd.DataFrame(grid)
policy.to_csv(TAB / "policy_simulation.csv", index=False)
print(policy.to_string(index=False))

# Break-even walk-away rate for the headline policy (top 10%, no behaviour change)
walks = np.linspace(0, 0.6, 121)
deltas = [simulate(0.10, w, 0.0)[0] for w in walks]
breakeven = next((w for w, d in zip(walks, deltas) if d <= 0), None)
pd.DataFrame({"walk_away_pct": (walks * 100).round(1), "delta_rev_eur": np.round(deltas)}) \
    .to_csv(TAB / "policy_breakeven_curve.csv", index=False)
print("break-even walk-away (top 10%, no cancel reduction):", breakeven)

fig, ax = plt.subplots(figsize=(7, 4.2))
for share, col in [(0.05, "#9bb5cf"), (0.10, "#2b5c8a"), (0.20, "#c97b3a")]:
    ax.plot(walks * 100, [simulate(share, w, 0.0)[0] / 1000 for w in walks],
            label=f"Top {int(share*100)}% riskiest", c=col)
ax.axhline(0, c="#999", lw=1)
ax.set_xlabel("Share of targeted bookings that walk away because of the deposit (%)")
ax.set_ylabel("Change in realized revenue, 2017 Jan-Aug (EUR k)")
ax.set_title("A first-night deposit on high-risk bookings pays off only if few walk away", fontsize=10)
ax.legend(frameon=False, fontsize=8)
ax.spines[["top", "right"]].set_visible(False)
fig.tight_layout()
fig.savefig(CHART / "policy_breakeven.png", dpi=150)

# ---------------------------------------------------------------------------
# 3. A/B test sizing for the top-10% deposit policy
#    Unit: booking attempt in the top risk decile. Metric: realized revenue per booking.
# ---------------------------------------------------------------------------
k = int(len(eligible) * 0.10)
seg = eligible.nlargest(k, "p_cancel")
per_booking = seg.adr * seg.nights * (1 - seg[TARGET])        # per booking record
mu, sd = per_booking.mean(), per_booking.std()
z_a, z_b = 1.96, 0.84                                        # alpha 0.05 two-sided, power 0.80
ab = []
for mde in [0.05, 0.10, 0.15]:
    n = 2 * ((z_a + z_b) * sd / (mu * mde)) ** 2
    weekly = len(seg) / (8 * 52 / 12)                        # test set spans ~8 months
    ab.append({"mde_relative_pct": int(mde * 100), "baseline_mean_eur": round(mu, 1),
               "sd_eur": round(sd, 1), "n_per_arm": int(np.ceil(n)),
               "weeks_needed_at_2017_volume": round(2 * n / weekly, 1)})
ab = pd.DataFrame(ab)
ab.to_csv(TAB / "ab_sample_size.csv", index=False)
print(ab.to_string(index=False))
