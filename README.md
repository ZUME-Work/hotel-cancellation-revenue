# Hotel Bookings: Which Bookings Actually Make Money After Cancellations?

> **Status:** work in progress. Data loading and data-quality diagnostics are done; the analysis is next.

## TL;DR
- **Question:** After cancellations are taken into account, which booking segments bring in the most realized revenue, and what policy should apply to high-risk bookings?
- **Answer:** _TODO: one number that matters._
- **Recommendation:** _TODO_

## Business context
Long-lead bookings often pay a higher ADR, but they also cancel more often. Judging a channel or lead-time bucket on ADR or conversion alone can overstate its value. This project measures **realized revenue per booking** (ADR × nights × probability of not cancelling) and tests whether a targeted deposit or overbooking policy would pay off.

## Data
- **Source:** Antonio, N., Almeida, A., & Nunes, L. (2019). *Hotel booking demand datasets.* Data in Brief, 22, 41–49. CSV taken from the TidyTuesday 2020-02-11 mirror (`scripts/download_data.py`).
- **Scope:** 119,390 bookings from two hotels in Portugal (City Hotel 79,330, Resort Hotel 40,060), arrivals from 2015-07-01 to 2017-08-31.
- **Grain:** one row per booking record. There is **no booking ID**.

## Data quality checks
All counts come from `sql/01_data_quality.sql` and `sql/02_duplicate_diagnostic.sql`.

| Check | Rows | Decision |
|---|---:|---|
| Exact duplicate rows (extra copies) | 31,994 | See below: this is the main decision |
| Zero guests (adults + children + babies = 0) | 180 | Exclude |
| Zero nights | 715 | _TODO_ |
| ADR < 0 | 1 | Exclude |
| ADR = 0 | 1,959 | _TODO: complimentary or data error?_ |
| ADR > 1,000 | 1 | Exclude (outlier) |
| `children` missing | 4 | Treat as 0 |
| `country` missing | 488 | Keep, label "Unknown" |
| `agent` / `company` missing | 16,340 / 112,593 | Missing means no agent/company, not missing data |
| `reservation_status` vs target mismatch | 0 | Confirms it leaks the target: never use it as a feature |

### The duplicate problem
The 31,994 extra copies are concentrated in group and agency bookings, so they look like separate rooms in one block rather than ingestion errors. They change the story a lot:

| Deposit type | Segment | Rows in duplicate groups | Cancel % (all rows) | Cancel % (unique rows only) |
|---|---|---:|---:|---:|
| Non Refund | Groups | 98.4% | 99.3% | 84.8% |
| Non Refund | Offline TA/TO | 98.8% | 99.9% | 94.8% |
| No Deposit | Groups | 72.5% | 28.3% | 12.0% |
| No Deposit | Online TA | 14.6% | 36.6% | 34.5% |

The overall cancel rate is 37.0% on all rows and 27.5% after removing duplicates. Read naively, the data says "non-refundable bookings cancel 99% of the time," which is a property of a few large group blocks, not of the deposit policy itself.

**Analysis grain decision:** _TODO_

## Method
_TODO: metric definitions, lead-time buckets, model, time-based train/test split (train 2015–2016, test 2017)._

## Findings
_TODO: 3–5 findings, each with one chart and one number._

## Recommendation and how to test it
_TODO: policy, A/B test design, primary metric (realized revenue per booking), guardrails (conversion, cancellation)._

## Limitations
- No booking ID, so duplicate rows cannot be told apart from separate rooms with certainty.
- Two hotels in one country; results may not generalize.
- The data only contains bookings that were made, not searches or abandoned bookings, so it says nothing about conversion.

## How to run
```bash
pip install -r requirements.txt
python scripts/download_data.py   # only if data/raw/hotels.csv is missing
python scripts/build_db.py        # rebuilds hotel.duckdb from sql/*.sql
```

## Repo structure
```
data/raw/            raw CSV (committed, ~17 MB)
sql/                 numbered SQL steps, run in order by build_db.py
scripts/             download + build scripts
notebooks/           analysis notebooks
outputs/tables|charts  small result files shown in this README
```
