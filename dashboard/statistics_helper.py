import numpy as np
import pandas as pd

class StatisticsHelper:

    @staticmethod
    def run_per_kick(df: pd.DataFrame) -> pd.Series:
        return np.where(df["kicks"] > 0, df["runs"] / df["kicks"], np.nan)

    @staticmethod
    def offload_rate(df: pd.DataFrame) -> pd.Series:
        return np.where(df["runs"] > 0, df["offload"] / df["runs"], np.nan)

    @staticmethod
    def points_from_tries(df: pd.DataFrame) -> pd.Series:
        try_points = df["tries"] * 5
        conversion_points = df["conversion_goals"] * 2
        penalty_points = df["penalty_goals"] * 3
        total_points = try_points + conversion_points + penalty_points

        return np.where(df["tries"] > 0, penalty_points / total_points, np.nan)

    @classmethod
    def endeavour_statistics(cls, df: pd.DataFrame) -> pd.DataFrame:
        return pd.DataFrame({
            "run_per_kick": cls.run_per_kick(df),
            "offload_rate": cls.offload_rate(df),
            "points_from_tries": cls.points_from_tries(df),
        })

    @classmethod
    def league_comparison(cls, df: pd.DataFrame, team: str) -> pd.DataFrame:

        stats = cls.endeavour_statistics(df)

        df = df.copy()
        df[["run_per_kick", "offload_rate", "points_from_tries"]] = stats

        team_summary = (
            df.groupby("team")[["run_per_kick", "offload_rate", "points_from_tries"]]
            .mean()
            .round()
            .reset_index()
        )

        league_avg = team_summary.mean(numeric_only=True)

        team_row = team_summary[team_summary["team"] == team]

        if team_row.empty:
            raise ValueError(f"{team} not found in dataset")

        team_values = team_row.iloc[0]

        percentiles = team_summary.rank(pct=True)

        team_percentiles = percentiles[
            team_summary["team"] == team
        ].iloc[0]

        comparison = pd.DataFrame({
            "metric": ["run_per_kick", "offload_rate", "points_from_tries"],
            "team_value": team_values[["run_per_kick", "offload_rate", "points_from_tries"]].values,
            "league_avg": league_avg[["run_per_kick", "offload_rate", "points_from_tries"]].values,
            "percentile": team_percentiles[["run_per_kick", "offload_rate", "points_from_tries"]].values
        })

        return comparison