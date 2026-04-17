import os
import pandas as pd
import streamlit as st
from concurrent.futures import ThreadPoolExecutor, as_completed
from rugbypy.team import fetch_all_teams, fetch_team_stats

TEAM_CACHE_FILE = "team_stats.parquet"

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
