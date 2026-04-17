import pandas as pd
import numpy as np
import plotly.express as px
from concurrent.futures import ThreadPoolExecutor, as_completed

class TeamStats:
    def __init__(self, teams):
        self.teams = teams
    
    def generate_team_stats(self):
        # Calculate the team statistics for each team in the league
        stats = []
        
        with ThreadPoolExecutor(max_workers=30) as executor:
            futures = [executor.submit(fetch_team, row) for _, row in self.teams.iterrows()]
            for f in as_completed(futures):
                r = f.result()
                if r is not None:
                    stats.append(r)
        
        # Combine the statistics into a single DataFrame
        df = pd.concat(stats, ignore_index=True)
        
        # Perform any necessary cleanup or processing of the data
        return df
    
    def generate_league_comparison(self):
        # Calculate the league comparison for each team in the league
        comparison = []
        
        with ThreadPoolExecutor(max_workers=30) as executor:
            futures = [executor.submit(fetch_team, row) for _, row in self.teams.iterrows()]
            for f in as_completed(futures):
                r = f.result()
                if r is not None:
                    comparison.append(r)
        
        # Combine the comparison data into a single DataFrame
        df = pd.concat(comparison, ignore_index=True)
        
        # Perform any necessary cleanup or processing of the data
        return df