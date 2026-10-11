"""AeroPulse - Indian Aviation Analytics dashboard.

Data: DGCA and Ministry of Civil Aviation (India), collected by
https://github.com/Vonter/india-aviation-traffic  (ODbL licence).
"""
from pathlib import Path
import sqlite3

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

DATA = Path(__file__).parent / "data"

st.set_page_config(page_title="AeroPulse", page_icon="✈️", layout="wide")


# ======================================================================
# STEP 1 - CLEANING ("preparing the bricks")
# Each function reads one CSV, fixes problems, and returns a tidy table.
# @st.cache_data = "remember the result so we don't redo it every click".
# ======================================================================
@st.cache_data
def load_routes():
    df = pd.read_csv(DATA / "city.csv")
    df = df.drop_duplicates()                          # remove exact copies

    for col in ["City1", "City2"]:                     # "Delhi " -> "DELHI"
        df[col] = df[col].str.strip().str.upper()
    for col in ["PaxToCity2", "PaxFromCity2"]:         # make sure these are numbers
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # we can't use a row without a date, a route or passenger numbers
    df = df.dropna(subset=["Year", "Month", "City1", "City2", "PaxToCity2", "PaxFromCity2"])

    # passengers flying in BOTH directions on that route
    df["Passengers"] = df["PaxToCity2"] + df["PaxFromCity2"]

    # The same route can be written DELHI-MUMBAI or MUMBAI-DELHI.
    # Put the names in alphabetical order so both become one route.
    first = np.where(df["City1"] < df["City2"], df["City1"], df["City2"])
    second = np.where(df["City1"] < df["City2"], df["City2"], df["City1"])
    df["Route"] = first + " ↔ " + second

    df["Year"] = df["Year"].astype(int)
    df["Month"] = df["Month"].astype(int)
    return df[["Year", "Month", "Route", "Passengers"]]


@st.cache_data
def load_airlines():
    df = pd.read_csv(DATA / "carrier.csv")
    df = df[df["Type"] == "ScheduledDomestic"]                  # normal domestic airlines
    df = df[~df["Airline"].str.startswith("Total")]             # drop the "Total ..." summary rows
    df["Passengers"] = pd.to_numeric(df["Passenger Number"], errors="coerce")
    df["Load Factor"] = pd.to_numeric(df["Passenger Load Factor"], errors="coerce")
    df = df.dropna(subset=["Passengers"])
    df["Year"] = df["Year"].astype(int)
    return df[["Airline", "Year", "Month", "Passengers", "Load Factor"]]


@st.cache_data
def load_ontime():
    df = pd.read_csv(DATA / "daily.csv", parse_dates=["Date"])
    cols = [c for c in df.columns if c.startswith("On Time Performance")]
    long = df[["Date"] + cols].melt("Date", var_name="Airline", value_name="OTP")
    long["Airline"] = (long["Airline"]
                       .str.replace("On Time Performance (", "", regex=False)
                       .str.rstrip(")"))
    # values look like "94.4%" (text!) -> remove % and turn into a number
    long["OTP"] = pd.to_numeric(
        long["OTP"].astype("string").str.replace("%", "", regex=False), errors="coerce")
    long = long.dropna(subset=["OTP"])
    long["Month"] = long["Date"].dt.to_period("M").dt.to_timestamp()
    monthly = (long.groupby(["Month", "Airline"])
               .agg(OTP=("OTP", "mean"), Days=("OTP", "size"))
               .reset_index())
    return monthly


# ======================================================================
# STEP 2 - SQL ("the rooms of the house")
# We copy the routes table into a tiny in-memory database and ask it
# questions in SQL.
# ======================================================================
@st.cache_resource
def get_database():
    con = sqlite3.connect(":memory:", check_same_thread=False)
    load_routes().to_sql("routes", con, index=False)
    return con


def run_sql(query, params=()):
    return pd.read_sql_query(query, get_database(), params=params)


SQL_YEARLY = """
SELECT Year, SUM(Passengers) AS Passengers
FROM routes
GROUP BY Year
ORDER BY Year
"""

SQL_TOP_ROUTES = """
SELECT Route, SUM(Passengers) AS Passengers
FROM routes
WHERE Year BETWEEN ? AND ?
GROUP BY Route
ORDER BY Passengers DESC
LIMIT 10
"""

SQL_ROUTE_BY_YEAR = """
SELECT Year, SUM(Passengers) AS Passengers
FROM routes
WHERE Route = ?
GROUP BY Year
ORDER BY Year
"""

# ======================================================================
# STEP 3 - THE DASHBOARD ("furniture and paint")
# ======================================================================
if not (DATA / "city.csv").exists():
    st.error("Data files not found. Run `python download_data.py` first.")
    st.stop()

st.title("✈️ AeroPulse")
st.caption("Indian aviation traffic and on-time performance, from DGCA and "
           "Ministry of Civil Aviation data.")

routes = load_routes()
airlines = load_airlines()
ontime = load_ontime()

latest_year = int(routes["Year"].max())
latest_months = int(routes.loc[routes["Year"] == latest_year, "Month"].max())

tab1, tab2, tab3, tab4 = st.tabs(
    ["📈 Overview", "🛫 Routes", "🏢 Airlines", "⏱️ On-time performance"])

# ---------------------------- Overview --------------------------------
with tab1:
    yearly = run_sql(SQL_YEARLY)
    c1, c2, c3 = st.columns(3)
    c1.metric("Years of data", f"{yearly['Year'].min()} – {yearly['Year'].max()}")
    c2.metric("Different routes", f"{routes['Route'].nunique():,}")
    peak = yearly.loc[yearly["Passengers"].idxmax()]
    c3.metric("Busiest year (so far)", int(peak["Year"]),
              f"{peak['Passengers']/1e6:.0f} million passenger movements", delta_color="off")

    fig = px.bar(yearly, x="Year", y="Passengers",
                 title="Passenger movements on domestic routes, by year")
    st.plotly_chart(fig, width="stretch")
    st.info(f"Note: {latest_year} only has data up to month {latest_months}, "
            "so it looks smaller than a full year. The 2020 dip is the COVID-19 "
            "lockdown. 2015 also starts mid-year.")

# ----------------------------- Routes ---------------------------------
with tab2:
    years = sorted(routes["Year"].unique())
    y_from, y_to = st.select_slider("Choose years", options=years,
                                    value=(years[0], years[-1]))
    top = run_sql(SQL_TOP_ROUTES, (int(y_from), int(y_to)))  # int() so SQL understands it
    fig = px.bar(top.sort_values("Passengers"), x="Passengers", y="Route",
                 orientation="h", title=f"Top 10 routes, {y_from}–{y_to}")
    st.plotly_chart(fig, width="stretch")

    st.subheader("Look at one route over time")
    all_routes = sorted(routes["Route"].unique())
    default = top["Route"].iloc[0]
    route = st.selectbox("Route", all_routes, index=all_routes.index(default))
    trend = run_sql(SQL_ROUTE_BY_YEAR, (route,))
    st.plotly_chart(px.line(trend, x="Year", y="Passengers", markers=True,
                            title=route), width="stretch")

# ---------------------------- Airlines --------------------------------
with tab3:
    st.write("Share of passengers carried by each scheduled domestic airline.")
    totals = airlines.groupby("Airline")["Passengers"].sum().sort_values(ascending=False)
    top_names = list(totals.head(6).index)
    chart_df = airlines.copy()
    chart_df["Airline"] = np.where(chart_df["Airline"].isin(top_names),
                                   chart_df["Airline"], "Others")
    by_year = chart_df.groupby(["Year", "Airline"], as_index=False)["Passengers"].sum()
    fig = px.bar(by_year, x="Year", y="Passengers", color="Airline",
                 title="Market share by year (top 6 airlines + others)")
    fig.update_layout(barnorm="percent")        # make every bar add up to 100%
    fig.update_yaxes(title="% of passengers")
    st.plotly_chart(fig, width="stretch")

    lf = (airlines.dropna(subset=["Load Factor"])
          .groupby(["Year", "Airline"], as_index=False)["Load Factor"].mean())
    lf = lf[lf["Airline"].isin(top_names)]
    st.plotly_chart(px.line(lf, x="Year", y="Load Factor", color="Airline", markers=True,
                            title="Average passenger load factor (% of seats filled)"),
                    width="stretch")

# ------------------------ On-time performance -------------------------
with tab4:
    st.write("Share of flights that left on time, from the Ministry's daily reports "
             "(only available from mid-2021, and not every day is reported).")
    min_days = st.slider("Only show months with at least this many reported days",
                         1, 15, 5)
    m = ontime[ontime["Days"] >= min_days]
    names = sorted(m["Airline"].unique())
    chosen = st.multiselect("Airlines", names,
                            default=[n for n in ["Indigo", "Air India", "Akasa Air", "Spicejet"]
                                     if n in names])
    m = m[m["Airline"].isin(chosen)]
    st.plotly_chart(px.line(m, x="Month", y="OTP", color="Airline", markers=True,
                            title="Monthly average on-time performance (%)"),
                    width="stretch")
    avg = (m.groupby("Airline", as_index=False)["OTP"].mean()
           .sort_values("OTP", ascending=False))
    st.plotly_chart(px.bar(avg, x="Airline", y="OTP",
                           title="Average on-time performance over the months shown"),
                    width="stretch")
    st.caption("Each monthly value is a simple average of the days reported. "
               "Airlines like Vistara, AirAsia India and GoAir stop appearing after they merged or closed.")

with st.expander("About the data and its limits"):
    st.markdown("""
- **Source:** DGCA and Ministry of Civil Aviation, collected by
  [Vonter/india-aviation-traffic](https://github.com/Vonter/india-aviation-traffic)
  under the Open Database License (ODbL).
- Route numbers add passengers in **both directions**, so they are passenger
  movements, not unique people.
- The on-time data comes from the daily reports, which have gaps and cover
  only part of the period. Averages of daily values are not the same as
  averaging every single flight.
""")
