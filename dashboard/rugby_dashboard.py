import os
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from concurrent.futures import ThreadPoolExecutor, as_completed

from rugbypy.team import fetch_all_teams, fetch_team_stats
from statistics_helper import StatisticsHelper

# -----------------------------
# PAGE CONFIG
# -----------------------------
st.set_page_config(layout="wide", page_title="Rugby Intelligence Dashboard")
st.title("🏉 Rugby Intelligence Dashboard")

TEAM_CACHE_FILE = "team_stats.parquet"


# -----------------------------
# LOAD DATA
# -----------------------------
@st.cache_data
def load_team_stats(force_refresh=False):

    if os.path.exists(TEAM_CACHE_FILE) and not force_refresh:
        df = pd.read_parquet(TEAM_CACHE_FILE)
    else:
        teams = fetch_all_teams()

        def fetch_team(row):
            try:
                stats = fetch_team_stats(team_id=row["team_id"])
                if stats is not None and not stats.empty:
                    stats["team"] = row["team"]
                    return stats
            except Exception:
                return None

        all_stats = []

        with ThreadPoolExecutor(max_workers=30) as executor:
            futures = [executor.submit(fetch_team, row) for _, row in teams.iterrows()]
            for f in as_completed(futures):
                r = f.result()
                if r is not None:
                    all_stats.append(r)

        df = pd.concat(all_stats, ignore_index=True)
        df.to_parquet(TEAM_CACHE_FILE, index=False)

    df["game_date"] = pd.to_datetime(df["game_date"], errors="coerce")
    return df


df = load_team_stats()

# -----------------------------
# TEAM SELECTOR
# -----------------------------
teams = df["team"].dropna().unique()
selected_team = st.sidebar.selectbox("Select Team", sorted(teams))

team_df = df[df["team"] == selected_team].copy()
team_df = team_df.sort_values("game_date")

# -----------------------------
# SAFE NUMERIC FEATURES
# -----------------------------
def safe_mean(col):
    return team_df[col].mean() if col in team_df.columns else np.nan


# =========================================================
# 🧠 TOP KPI ROW
# =========================================================
st.subheader(f"📊 {selected_team} Core Performance")

k1, k2, k3, k4, k5 = st.columns(5)

k1.metric("Tries", round(safe_mean("tries"), 2))
k2.metric("Line Breaks", round(safe_mean("line_breaks"), 2))
k3.metric("Carries", round(safe_mean("carries"), 1))
k4.metric("Metres Carried", round(safe_mean("metres_carried"), 1))
k5.metric("Tackles Made", round(safe_mean("tackles_made"), 1))


# =========================================================
# 📈 TIME SERIES
# =========================================================
st.subheader("📈 Performance Over Time")

metric_choice = st.multiselect(
    "Metrics",
    ["tries", "line_breaks", "22m_entries", "carries", "metres_carried", "tackles_made", "turnovers_won"],
    default=["tries", "line_breaks", "22m_entries"]
)

fig = px.line(
    team_df,
    x="game_date",
    y=metric_choice,
    title="Performance Trends"
)

st.plotly_chart(fig, use_container_width=True)


# =========================================================
# 🔥 ROLLING FORM
# =========================================================
if "tries" in team_df.columns:
    team_df["rolling_tries"] = team_df["tries"].rolling(3).mean()

    fig_roll = px.line(
        team_df,
        x="game_date",
        y="rolling_tries",
        title="3-Game Rolling Try Form"
    )
    st.plotly_chart(fig_roll, use_container_width=True)


# =========================================================
# 🚀 ENDEAVOUR STATISTICS (UNCHANGED LOGIC)
# =========================================================
st.subheader("🚀 Endeavour Statistics")

comparison_df = StatisticsHelper.league_comparison(df, selected_team)

fig_end = px.bar(
    comparison_df,
    x="metric",
    y="percentile",
    color="team_value",
    title="Endeavour Metrics vs League",
    range_y=[0, 1]
)

st.plotly_chart(fig_end, use_container_width=True)

# =========================================================
# 🔍 RAW DATA
# =========================================================
st.subheader("🔍 Raw Data")
st.dataframe(team_df)