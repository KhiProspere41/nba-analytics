#!/usr/bin/env python3
"""NBA Player Performance Analytics — entry point.

Fetches live per-game stats from the official NBA Stats API and merges them with
real 2025-26 salary/position data. No local box-score fallback is bundled for this
season, so this requires network access.

Usage:
    python main.py                # 2025-26 season, top 80 scorers
    python main.py --top-n 200    # widen to the top 200 scorers
    python main.py --season 2024-25   # a different season (salary file stays 2025-26)
"""

import argparse
import sys

import analysis
import visualizations


def parse_args():
    parser = argparse.ArgumentParser(description="NBA salary vs. performance analytics")
    parser.add_argument(
        "--season", default="2025-26",
        help="Season to fetch from the NBA Stats API (default: 2025-26).",
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

    print(f"Fetching live NBA stats for the {args.season} season...")
    try:
        stats_df = analysis.fetch_live_stats(season=args.season)
    except analysis.LiveDataUnavailable as exc:
        print(f"Live fetch failed: {exc}", file=sys.stderr)
        sys.exit(1)
    print(f"  Retrieved {len(stats_df)} players from the NBA Stats API.")

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
