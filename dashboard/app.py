import os
import streamlit as st
import pandas as pd
import numpy as np
from data_loader import load_team_stats
from charts import kpi_metrics, performance_over_time, endeavour_metrics

def team_selection(df):
    teams = df["team"].dropna().unique()
    selected_team = st.sidebar.selectbox("Select Team", sorted(teams))
    return selected_team

st.set_page_config(layout="wide", page_title="Rugby Intelligence Dashboard")
st.title("🏉 Rugby Intelligence Dashboard")

all_team_data = load_team_stats()
selected_team = team_selection(all_team_data)

selected_team_data = all_team_data[all_team_data["team"] == selected_team].copy()
team_df = selected_team_data.sort_values("game_date")

# Add Charts
kpi_metrics(team_df,selected_team)
performance_over_time(team_df, selected_team)
endeavour_metrics(all_team_data, selected_team)

# Display Raw Data
st.subheader("🔍 Raw Data")
st.dataframe(team_df)