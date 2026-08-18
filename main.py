#!/usr/bin/env python3
"""NBA Player Performance Analytics — entry point.

Usage:
    python main.py --sample-data --skip-viz   # instant offline test
    python main.py --live-data                # fetch real current-season stats
    python main.py --live-data --season 2022-23
"""

import argparse
import sys

import analysis
import visualizations


def parse_args():
    parser = argparse.ArgumentParser(description="NBA salary vs. performance analytics")
    source = parser.add_mutually_exclusive_group()
    source.add_argument(
        "--live-data", action="store_true",
        help="Fetch live stats from the official NBA Stats API (requires network access).",
    )
    source.add_argument(
        "--sample-data", action="store_true",
        help="Use the bundled sample dataset (default, no network required).",
    )
    parser.add_argument(
        "--season", default="2023-24",
        help="Season to fetch in live mode, e.g. 2023-24 (default: 2023-24).",
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
            print("  Falling back to bundled sample data.")
            stats_df = analysis.load_sample_stats()
    else:
        print("Using bundled sample dataset...")
        stats_df = analysis.load_sample_stats()

    salary_df = analysis.load_salary_data()

    print("Merging stats with salary data...")
    merged = analysis.merge_with_salary(stats_df, salary_df)
    if merged.empty:
        print("No players matched between stats and salary data. Aborting.", file=sys.stderr)
        sys.exit(1)

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
