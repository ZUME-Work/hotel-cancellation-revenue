"""Download the Hotel Booking Demand dataset into data/raw/.

Original source: Antonio, N., Almeida, A., & Nunes, L. (2019).
Hotel booking demand datasets. Data in Brief, 22, 41-49.
Mirror used here: TidyTuesday 2020-02-11 (cleaned CSV of both hotels).
"""
from pathlib import Path
import urllib.request

URL = ("https://raw.githubusercontent.com/rfordatascience/tidytuesday/"
       "master/data/2020/2020-02-11/hotels.csv")
OUT = Path(__file__).resolve().parents[1] / "data" / "raw" / "hotels.csv"

if __name__ == "__main__":
    OUT.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(URL, OUT)
    print(f"Saved {OUT} ({OUT.stat().st_size / 1e6:.1f} MB)")
