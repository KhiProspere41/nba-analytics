"""NBA player performance analytics: live data fetch, salary merge, advanced metrics."""

import time
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).parent / "data"
OUTPUT_DIR = Path(__file__).parent / "output"

STAT_COLUMNS = [
    "PLAYER", "TEAM", "POSITION", "GP", "MIN", "PTS", "REB", "AST",
    "STL", "BLK", "TOV", "FGM", "FGA", "FG3M", "FG3A", "FTM", "FTA",
]


class LiveDataUnavailable(Exception):
    """Raised when the NBA Stats API can't be reached or returns no usable data."""


def fetch_live_stats(season: str = "2023-24", min_games: int = 20) -> pd.DataFrame:
    """Fetch current player per-game stats from the official NBA Stats API.

    Requires network access. Positions come from PlayerIndex when available;
    older nba_api versions that lack it fall back to POSITION="N/A".
    """
    try:
        from nba_api.stats.endpoints import leaguedashplayerstats
    except ImportError as exc:
        raise LiveDataUnavailable("nba_api is not installed") from exc

    try:
        stats = leaguedashplayerstats.LeagueDashPlayerStats(
            season=season,
            per_mode_detailed="PerGame",
            timeout=30,
        ).get_data_frames()[0]
    except Exception as exc:  # network errors, API schema changes, rate limiting
        raise LiveDataUnavailable(f"NBA Stats API request failed: {exc}") from exc

    if stats.empty:
        raise LiveDataUnavailable(f"NBA Stats API returned no rows for season {season}")

    stats = stats.rename(columns={"PLAYER_NAME": "PLAYER", "TEAM_ABBREVIATION": "TEAM"})
    stats = stats[stats["GP"] >= min_games].copy()

    positions = _fetch_positions()
    stats["POSITION"] = stats["PLAYER"].map(positions).fillna("N/A")

    return stats[STAT_COLUMNS].reset_index(drop=True)


def _fetch_positions() -> dict:
    """Best-effort player -> position lookup. Returns {} if unavailable."""
    try:
        from nba_api.stats.endpoints import playerindex

        time.sleep(0.5)  # be polite to the API between calls
        idx = playerindex.PlayerIndex(timeout=30).get_data_frames()[0]
        idx["PLAYER"] = idx["PLAYER_FIRST_NAME"] + " " + idx["PLAYER_LAST_NAME"]
        return dict(zip(idx["PLAYER"], idx["POSITION"]))
    except Exception:
        return {}


def load_sample_stats() -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / "sample_stats.csv")


def load_salary_data() -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / "salary_data.csv")


def merge_with_salary(stats_df: pd.DataFrame, salary_df: pd.DataFrame) -> pd.DataFrame:
    """Inner join stats with salary data on player name."""
    merged = stats_df.merge(salary_df, on="PLAYER", how="inner")
    unmatched = len(stats_df) - len(merged)
    if unmatched:
        print(f"  Note: {unmatched} players had no salary match and were dropped.")
    return merged


def compute_advanced_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Add True Shooting %, a simplified efficiency score, and a Value Index."""
    df = df.copy()

    # True Shooting % — accounts for the extra value of 3s and free throws.
    denom = 2 * (df["FGA"] + 0.44 * df["FTA"])
    df["TS_PCT"] = (df["PTS"] / denom.replace(0, pd.NA) * 100).round(1)

    # Simplified efficiency score (à la the classic NBA "EFF" formula), per game.
    df["EFF"] = (
        df["PTS"] + df["REB"] + df["AST"] + df["STL"] + df["BLK"]
        - (df["FGA"] - df["FGM"])
        - (df["FTA"] - df["FTM"])
        - df["TOV"]
    ).round(1)

    # Value Index: production per $1M of salary. Higher = more bang for the buck.
    salary_millions = df["SALARY"] / 1_000_000
    df["VALUE_INDEX"] = (df["EFF"] / salary_millions).round(2)

    return df


def correlation_matrix(df: pd.DataFrame) -> pd.DataFrame:
    cols = ["SALARY", "PTS", "REB", "AST", "EFF", "TS_PCT", "MIN"]
    return df[cols].corr().round(3)


def top_value_players(df: pd.DataFrame, n: int = 15) -> pd.DataFrame:
    return df.nlargest(n, "VALUE_INDEX")[
        ["PLAYER", "TEAM", "POSITION", "SALARY", "PTS", "EFF", "VALUE_INDEX"]
    ].reset_index(drop=True)


def position_summary(df: pd.DataFrame) -> pd.DataFrame:
    return (
        df.groupby("POSITION")
        .agg(
            players=("PLAYER", "count"),
            avg_salary=("SALARY", "mean"),
            avg_pts=("PTS", "mean"),
            avg_eff=("EFF", "mean"),
            avg_value_index=("VALUE_INDEX", "mean"),
        )
        .round(1)
        .sort_values("avg_salary", ascending=False)
    )


def save_processed_data(df: pd.DataFrame, filename: str = "processed_player_data.csv") -> Path:
    OUTPUT_DIR.mkdir(exist_ok=True)
    path = OUTPUT_DIR / filename
    df.to_csv(path, index=False)
    return path
