import streamlit as st
import numpy as np
import plotly.express as px
from statistics_helper import StatisticsHelper

def safe_mean(team_df,col):
    return team_df[col].mean() if col in team_df.columns else np.nan

def kpi_metrics(team_df, selected_team):
    st.subheader(f"📊 {selected_team} Core Performance")

    k1, k2, k3, k4, k5 = st.columns(5)

    k1.metric("Tries", round(safe_mean(team_df,"tries"), 2))
    k2.metric("Line Breaks", round(safe_mean(team_df,"line_breaks"), 2))
    k3.metric("Carries", round(safe_mean(team_df,"carries"), 1))
    k4.metric("Metres Carried", round(safe_mean(team_df,"metres_carried"), 1))
    k5.metric("Tackles Made", round(safe_mean(team_df,"tackles_made"), 1))

def performance_over_time(team_df, selected_team):
    st.subheader(f"📈 {selected_team} Performance Over Time")

    metric_choice = st.multiselect(
        "Metrics",
        ["tries", "line_breaks", "22m_entries", "carries", "metres_carried", "tackles_made", "turnovers_won"],
        default=["tries", "line_breaks", "22m_entries"]
    )

    fig = px.line(
        team_df,
        x="game_date",
        y=metric_choice,
        title=f"{selected_team} Performance Trends"
    )

    st.plotly_chart(fig, use_container_width=True)

def endeavour_metrics(all_team_data, selected_team):
    st.subheader("🚀 Endeavour Statistics")

    comparison_df = StatisticsHelper.league_comparison(all_team_data, selected_team)

    fig_end = px.bar(
        comparison_df,
        x="metric",
        y="percentile",
        color="team_value",
        title="Endeavour Metrics vs League",
        range_y=[0, 1]
    )

    st.plotly_chart(fig_end, use_container_width=True)