import os
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from concurrent.futures import ThreadPoolExecutor, as_completed
from rugbypy.team import fetch_all_teams, fetch_team_stats

# -----------------------------
# PAGE CONFIG + DARK STYLE
# -----------------------------
st.set_page_config(layout="wide", page_title="Rugby Intelligence Dashboard")

st.title("🏉 Rugby Intelligence Dashboard")

TEAM_CACHE_FILE = "team_stats.parquet"

ALLOWED_TEAMS = ["Scotland", "Edinburgh"]

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
                    stats["team_name"] = row["team_name"]
                    return stats
            except:
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

    # 🔥 HARD FILTER (CRITICAL)
    df = df[df["team_name"].isin(ALLOWED_TEAMS)].copy()

    return df


# -----------------------------
# SIDEBAR CONTROLS
# -----------------------------
force_refresh = st.sidebar.button("🔄 Refresh Data")

metric_choice = st.sidebar.multiselect(
    "📌 Metrics to view",
    ["tries", "line_breaks", "tackles", "metres_carried", "turnovers_won"],
    default=["tries", "line_breaks"]
)

show_raw = st.sidebar.checkbox("🔍 Show Raw Data", False)

# -----------------------------
# LOAD DATA
# -----------------------------
df = load_team_stats(force_refresh=force_refresh)

df["game_date"] = pd.to_datetime(df["game_date"], errors="coerce")

teams = ALLOWED_TEAMS
selected_team = st.sidebar.radio("Select Team", teams)

team_df = df[df["team_name"] == selected_team].copy()
team_df = team_df.sort_values("game_date")

# -----------------------------
# KPIs
# -----------------------------
st.subheader(f"📊 {selected_team} Performance on Average")

c1, c2, c3, c4 = st.columns(4)

c1.metric("Tries", round(team_df["tries"].mean(), 2))
c2.metric("Line Breaks", round(team_df["line_breaks"].mean(), 2))
c3.metric("Metres Carried", round(team_df["metres_carried"].mean(), 1))
c4.metric("Tackles", round(team_df["tackles"].mean(), 1))

# -----------------------------
# TREND ANALYSIS
# -----------------------------
st.subheader("📈 Performance Trends")

fig = px.line(
    team_df,
    x="game_date",
    y=metric_choice,
    title="Selected Metrics Over Time"
)

st.plotly_chart(fig, use_container_width=True)

# Rolling form
if "tries" in team_df.columns:
    team_df["rolling"] = team_df["tries"].rolling(window=3).mean()

    fig2 = px.line(
        team_df,
        x="game_date",
        y="rolling",
        title=f"Rolling Try Form"
    )

    st.plotly_chart(fig2, use_container_width=True)

# -----------------------------
# DISTRIBUTION INSIGHTS
# -----------------------------
st.subheader("📊 Distribution Insights")

fig3 = px.box(
    team_df,
    y=metric_choice,
    title="Performance Spread"
)
st.plotly_chart(fig3, use_container_width=True)

# -----------------------------
# TEAM DNA
# -----------------------------
st.subheader("🧬 Team DNA")

profile = team_df[metric_choice].mean().reset_index()
profile.columns = ["metric", "value"]

fig6 = px.bar(
    profile,
    x="metric",
    y="value",
    title="Team Style Profile"
)
st.plotly_chart(fig6, use_container_width=True)

# -----------------------------
# RAW DATA
# -----------------------------
if show_raw:
    st.subheader("🔍 Raw Data")
    st.dataframe(team_df)