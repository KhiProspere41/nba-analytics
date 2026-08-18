#!/usr/bin/env python3
"""NBA Player Performance Analytics — entry point.

Usage:
    python main.py                # bundled real 2025-26 box scores (offline), top 80
    python main.py --live-data    # re-fetch current stats from the NBA Stats API instead
    python main.py --top-n 200    # widen to the top 200 scorers
"""

import argparse
import sys

import analysis
import visualizations


def parse_args():
    parser = argparse.ArgumentParser(description="NBA salary vs. performance analytics")
    parser.add_argument(
        "--live-data", action="store_true",
        help="Fetch live stats from the official NBA Stats API instead of the bundled "
             "2025-26 box score log (requires network access).",
    )
    parser.add_argument(
        "--season", default="2025-26",
        help="Season to fetch in live mode (default: 2025-26).",
    )
    parser.add_argument(
        "--top-n", type=int, default=80,
        help="Keep only the top N players by total season points (default: 80).",
    )
    parser.add_argument(
        "--skip-viz", action="store_true",
        help="Skip chart generation and only produce the processed CSV.",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    if args.live_data:
        print(f"Fetching live NBA stats for the {args.season} season...")
        try:
            stats_df = analysis.fetch_live_stats(season=args.season)
            print(f"  Retrieved {len(stats_df)} players from the NBA Stats API.")
        except analysis.LiveDataUnavailable as exc:
            print(f"  Live fetch failed ({exc})")
            print("  Falling back to the bundled 2025-26 box score log.")
            args.live_data = False

    if not args.live_data:
        print("Loading bundled 2025-26 season game logs...")
        logs = analysis.load_game_logs()
        stats_df = analysis.aggregate_season_stats(logs)
        print(f"  Aggregated {len(stats_df)} players from {len(logs)} game log rows.")

    print(f"Selecting top {args.top_n} players by total season points...")
    stats_df = analysis.select_top_players(stats_df, n=args.top_n)

    salary_df = analysis.load_salary_data()

    print("Merging stats with salary/position data...")
    merged = analysis.merge_with_salary(stats_df, salary_df)
    if merged.empty:
        print("No players matched between stats and salary data. Aborting.", file=sys.stderr)
        sys.exit(1)
    print(f"  {len(merged)} of {len(stats_df)} top players had usable salary data.")

    print("Computing advanced metrics (TS%, EFF, Value Index)...")
    df = analysis.compute_advanced_metrics(merged)

    corr_df = analysis.correlation_matrix(df)
    value_df = analysis.top_value_players(df)
    position_df = analysis.position_summary(df)

    out_path = analysis.save_processed_data(df)
    print(f"Processed data saved to {out_path}")

    print("\nTop 5 most undervalued players (Value Index):")
    print(value_df.head(5).to_string(index=False))

    print("\nSalary <-> performance correlations:")
    print(corr_df["SALARY"].drop("SALARY").to_string())

    if not args.skip_viz:
        print("\nGenerating charts...")
        paths = visualizations.generate_all_charts(df, corr_df, value_df, position_df)
        for p in paths:
            print(f"  Saved {p}")
    else:
        print("\nSkipping chart generation (--skip-viz).")

    print("\nDone.")


if __name__ == "__main__":
    main()
