"""NBA player performance analytics: live 2025-26 season stats + real salary/position data."""

import re
import unicodedata
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).parent / "data"
OUTPUT_DIR = Path(__file__).parent / "output"

GAME_LOG_PATH = DATA_DIR / "nba_dailyleaders_2025_26.csv"
SALARY_PATH = DATA_DIR / "nba_salaries_2025_26.csv"

STAT_COLUMNS = [
    "PLAYER", "TEAM", "GP", "MIN", "PTS", "REB", "AST",
    "STL", "BLK", "TOV", "FGM", "FGA", "FG3M", "FG3A", "FTM", "FTA",
]


class LiveDataUnavailable(Exception):
    """Raised when the NBA Stats API can't be reached or returns no usable data."""


def _name_key(name: str) -> str:
    """Normalize a player name for matching across datasets (accents, punctuation, suffixes)."""
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    name = name.replace(".", "").strip().lower()
    name = re.sub(r"\s+(jr|sr|ii|iii|iv)\.?$", "", name)
    return re.sub(r"\s+", " ", name)


def load_game_logs(path: Path = GAME_LOG_PATH) -> pd.DataFrame:
    """Load the bundled per-game box score log (one row per player per game)."""
    return pd.read_csv(path)


def aggregate_season_stats(logs: pd.DataFrame) -> pd.DataFrame:
    """Collapse per-game rows into one season-average row per player."""
    grouped = logs.groupby("PLAYER")
    agg = grouped.agg(
        GP=("PTS", "size"),
        TOTAL_PTS=("PTS", "sum"),
        TEAM=("TEAM", lambda s: s.mode().iat[0]),
        MIN=("MIN", "mean"),
        PTS=("PTS", "mean"),
        REB=("REB", "mean"),
        AST=("AST", "mean"),
        STL=("STL", "mean"),
        BLK=("BLK", "mean"),
        TOV=("TOV", "mean"),
        FGM=("FGM", "mean"),
        FGA=("FGA", "mean"),
        FG3M=("FG3M", "mean"),
        FG3A=("FG3A", "mean"),
        FTM=("FTM", "mean"),
        FTA=("FTA", "mean"),
    ).reset_index()

    round_cols = ["MIN", "PTS", "REB", "AST", "STL", "BLK", "TOV", "FGM", "FGA", "FG3M", "FG3A", "FTM", "FTA"]
    agg[round_cols] = agg[round_cols].round(1)
    return agg


def fetch_live_stats(season: str = "2025-26", min_games: int = 10) -> pd.DataFrame:
    """Fetch player per-game stats for a season from the official NBA Stats API.

    This is the only stats source in this pipeline — no local box score file is
    bundled for 2025-26, so a network call is required.
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
    stats["TOTAL_PTS"] = (stats["PTS"] * stats["GP"]).round(1)

    return stats[STAT_COLUMNS + ["TOTAL_PTS"]].reset_index(drop=True)


def select_top_players(df: pd.DataFrame, n: int = 80, by: str = "TOTAL_PTS") -> pd.DataFrame:
    """Keep only the top-n players ranked by total season points."""
    return df.nlargest(n, by).reset_index(drop=True)


def load_salary_data(path: Path = SALARY_PATH) -> pd.DataFrame:
    """Load real 2025-26 salary + position data (parsed from a text export)."""
    df = pd.read_csv(path)
    return df[df["SALARY"] > 0].drop_duplicates("PLAYER").reset_index(drop=True)


def merge_with_salary(stats_df: pd.DataFrame, salary_df: pd.DataFrame) -> pd.DataFrame:
    """Join stats with salary/position data, matching names loosely (accents/punctuation/suffixes)."""
    stats_df = stats_df.copy()
    salary_df = salary_df.copy()
    stats_df["_key"] = stats_df["PLAYER"].map(_name_key)
    salary_df["_key"] = salary_df["PLAYER"].map(_name_key)

    merged = stats_df.merge(
        salary_df[["_key", "SALARY", "POSITION"]], on="_key", how="inner"
    ).drop(columns="_key")

    unmatched = len(stats_df) - len(merged)
    if unmatched:
        print(f"  Note: {unmatched} players had no salary match and were dropped.")
    return merged


def compute_advanced_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Add True Shooting %, a simplified efficiency score, and a Value Index."""
    df = df.copy()

    denom = 2 * (df["FGA"] + 0.44 * df["FTA"])
    df["TS_PCT"] = (df["PTS"] / denom.replace(0, pd.NA) * 100).round(1)

    df["EFF"] = (
        df["PTS"] + df["REB"] + df["AST"] + df["STL"] + df["BLK"]
        - (df["FGA"] - df["FGM"])
        - (df["FTA"] - df["FTM"])
        - df["TOV"]
    ).round(1)

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
