"""Prints real numbers from the data so YOU can write your own findings.
Run:  python findings.py
"""
from pathlib import Path
import numpy as np
import pandas as pd

DATA = Path(__file__).parent / "data"

# ---- routes ----
r = pd.read_csv(DATA / "city.csv").drop_duplicates()
r["Passengers"] = r["PaxToCity2"] + r["PaxFromCity2"]
a = np.where(r["City1"] < r["City2"], r["City1"], r["City2"])
b = np.where(r["City1"] < r["City2"], r["City2"], r["City1"])
r["Route"] = a + " <-> " + b

yearly = r.groupby("Year")["Passengers"].sum()
print("=== Passengers per year (millions) ===")
print((yearly / 1e6).round(1))
print("\nChange 2019 -> 2020: %.1f%%" % ((yearly[2020] / yearly[2019] - 1) * 100))
print("Change 2019 -> 2025: %.1f%%" % ((yearly[2025] / yearly[2019] - 1) * 100))

print("\n=== Top 5 routes of all time (millions) ===")
print((r.groupby("Route")["Passengers"].sum().sort_values(ascending=False).head(5) / 1e6).round(1))

month_share = r.groupby("Month")["Passengers"].sum()
print("\n=== Share of traffic by month (%) ===")
print((month_share / month_share.sum() * 100).round(1))

# ---- airlines ----
air = pd.read_csv(DATA / "carrier.csv")
air = air[(air["Type"] == "ScheduledDomestic") & (~air["Airline"].str.startswith("Total"))]
for year in [2019, 2025]:
    s = air[air["Year"] == year].groupby("Airline")["Passenger Number"].sum()
    print(f"\n=== Market share {year} (%) ===")
    print((s / s.sum() * 100).round(1).sort_values(ascending=False).head(4))

# ---- on-time performance ----
d = pd.read_csv(DATA / "daily.csv")
cols = [c for c in d.columns if c.startswith("On Time Performance")]
for c in cols:
    d[c] = pd.to_numeric(d[c].astype("string").str.replace("%", "", regex=False), errors="coerce")
print("\n=== Average on-time performance per airline (%) - daily reports ===")
print(d[cols].mean().round(1).rename(lambda x: x.replace("On Time Performance (", "").rstrip(")")))
print("\nDays with any on-time data:", int(d[cols].notna().any(axis=1).sum()))
