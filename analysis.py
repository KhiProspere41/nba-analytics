"""NBA player performance analytics: real 2024-25 season data + salary merge."""

import re
import time
import unicodedata
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).parent / "data"
OUTPUT_DIR = Path(__file__).parent / "output"

GAME_LOG_PATH = DATA_DIR / "nba_dailyleaders_2024_25.csv"
SALARY_PATH = DATA_DIR / "nba_salaries_2024_25.csv"

# The game log has no rebounds column, so metrics below deliberately omit REB.
STAT_COLUMNS = [
    "PLAYER", "TEAM", "GP", "MIN", "PTS", "AST", "STL", "BLK", "TOV",
    "FGM", "FGA", "FG3M", "FG3A", "FTM", "FTA",
]


class LiveDataUnavailable(Exception):
    """Raised when the NBA Stats API can't be reached or returns no usable data."""


def _name_key(name: str) -> str:
    """Normalize a player name for matching across datasets (accents, punctuation, suffixes)."""
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    name = name.replace(".", "").strip().lower()
    name = re.sub(r"\s+(jr|sr|ii|iii|iv)\.?$", "", name)
    return re.sub(r"\s+", " ", name)


def _parse_minutes(mp: str) -> float:
    minutes, seconds = mp.split(":")
    return int(minutes) + int(seconds) / 60


def load_game_logs(path: Path = GAME_LOG_PATH) -> pd.DataFrame:
    """Load the per-game box score log (one row per player per game)."""
    df = pd.read_csv(path)
    df["MIN"] = df["MP"].map(_parse_minutes)
    return df.rename(columns={"3P": "FG3M", "3PA": "FG3A", "FT": "FTM"})


def aggregate_season_stats(logs: pd.DataFrame) -> pd.DataFrame:
    """Collapse per-game rows into one season-average row per player."""
    grouped = logs.groupby("Player")
    agg = grouped.agg(
        GP=("PTS", "size"),
        TOTAL_PTS=("PTS", "sum"),
        TEAM=("Tm", lambda s: s.mode().iat[0]),
        MIN=("MIN", "mean"),
        PTS=("PTS", "mean"),
        AST=("AST", "mean"),
        STL=("STL", "mean"),
        BLK=("BLK", "mean"),
        TOV=("TOV", "mean"),
        FGM=("FG", "mean"),
        FGA=("FGA", "mean"),
        FG3M=("FG3M", "mean"),
        FG3A=("FG3A", "mean"),
        FTM=("FTM", "mean"),
        FTA=("FTA", "mean"),
    ).reset_index().rename(columns={"Player": "PLAYER"})

    round_cols = ["MIN", "PTS", "AST", "STL", "BLK", "TOV", "FGM", "FGA", "FG3M", "FG3A", "FTM", "FTA"]
    agg[round_cols] = agg[round_cols].round(1)
    return agg


def select_top_players(df: pd.DataFrame, n: int = 200, by: str = "TOTAL_PTS") -> pd.DataFrame:
    """Keep only the top-n players ranked by total season scoring output."""
    return df.nlargest(n, by).reset_index(drop=True)


def load_salary_data(path: Path = SALARY_PATH) -> pd.DataFrame:
    """Load the salary table. Rows with $0 are treated as missing (stale/unreported
    contract data, not an actual $0 salary) and dropped."""
    df = pd.read_csv(path)
    salary_col = [c for c in df.columns if "2024" in c][0]
    df["SALARY"] = (
        df[salary_col].astype(str).str.replace(r"[$,]", "", regex=True).str.strip().astype(float)
    )
    df = df.rename(columns={"Player Name": "PLAYER"})[["PLAYER", "SALARY"]]
    df = df[df["SALARY"] > 0]
    return df.sort_values("SALARY", ascending=False).drop_duplicates("PLAYER").reset_index(drop=True)


def merge_with_salary(stats_df: pd.DataFrame, salary_df: pd.DataFrame) -> pd.DataFrame:
    """Join stats with salary data, matching names loosely (accents/punctuation/suffixes)."""
    stats_df = stats_df.copy()
    salary_df = salary_df.copy()
    stats_df["_key"] = stats_df["PLAYER"].map(_name_key)
    salary_df["_key"] = salary_df["PLAYER"].map(_name_key)

    merged = stats_df.merge(
        salary_df[["_key", "SALARY"]], on="_key", how="inner"
    ).drop(columns="_key")

    unmatched = len(stats_df) - len(merged)
    if unmatched:
        print(f"  Note: {unmatched} players had no valid salary match (missing or $0) and were dropped.")
    return merged


def fetch_live_stats(season: str = "2024-25", min_games: int = 20) -> pd.DataFrame:
    """Fetch current player per-game stats from the official NBA Stats API.

    Requires network access. Used as an alternative to the bundled local season data.
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


def compute_advanced_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Add True Shooting %, a simplified efficiency score, and a Value Index.

    EFF intentionally omits rebounds — the source game log doesn't include them.
    """
    df = df.copy()

    denom = 2 * (df["FGA"] + 0.44 * df["FTA"])
    df["TS_PCT"] = (df["PTS"] / denom.replace(0, pd.NA) * 100).round(1)

    df["EFF"] = (
        df["PTS"] + df["AST"] + df["STL"] + df["BLK"]
        - (df["FGA"] - df["FGM"])
        - (df["FTA"] - df["FTM"])
        - df["TOV"]
    ).round(1)

    salary_millions = df["SALARY"] / 1_000_000
    df["VALUE_INDEX"] = (df["EFF"] / salary_millions).round(2)

    return df


def correlation_matrix(df: pd.DataFrame) -> pd.DataFrame:
    cols = ["SALARY", "PTS", "AST", "EFF", "TS_PCT", "MIN"]
    return df[cols].corr().round(3)


def top_value_players(df: pd.DataFrame, n: int = 15) -> pd.DataFrame:
    return df.nlargest(n, "VALUE_INDEX")[
        ["PLAYER", "TEAM", "SALARY", "PTS", "EFF", "VALUE_INDEX"]
    ].reset_index(drop=True)


def team_summary(df: pd.DataFrame) -> pd.DataFrame:
    return (
        df.groupby("TEAM")
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
