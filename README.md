# NBA Player Performance Analytics

Analyzes the relationship between NBA player salaries and on-court performance for the
2025-26 season, using live per-game stats from the official NBA Stats API and real
salary/position data. Computes advanced metrics (True Shooting %, an efficiency score,
a salary-adjusted "Value Index"), runs a correlation analysis, and produces four charts.

![Salary vs Performance](examples/salary_vs_performance.png)

## Quickstart

```bash
pip install -r requirements.txt

python main.py                # 2025-26 season, top 80 scorers, full run with charts
python main.py --skip-viz     # skip chart generation, just produce the CSV
```

Other options:

```bash
python main.py --top-n 200          # widen to the top 200 scorers instead of 80
python main.py --season 2024-25     # analyze a different season's live stats
```

This requires network access — stats are fetched live for every run; there's no bundled
offline dataset for the current season. Output lands in `output/`:
`processed_player_data.csv` plus four PNG charts.

## Data sources

- **Stats** — `analysis.fetch_live_stats()` calls `LeagueDashPlayerStats` from
  [`nba_api`](https://github.com/swar/nba_api), the same endpoints stats.nba.com's own
  site uses, for real per-game numbers (PTS, REB, AST, shooting splits, etc.).
- **`data/nba_salaries_2025_26.csv`** — real 2025-26 salaries and positions for 240
  players, parsed from a plain-text salary export (rank/name/team/salary, with position
  embedded in the name field, e.g. `"Stephen Curry, G"`).

## How it works

1. **Fetch** — live per-game stats for every player with at least 10 games played in
   the target season.
2. **Select top N** — `analysis.select_top_players()` keeps the top 80 players (`--top-n`
   to change it) ranked by total season points.
3. **Merge salary** — joined by player name, normalized to survive accents, periods, and
   suffixes (e.g. `Nikola Jokić` vs `Nikola Jokic`, trailing `Jr.`/`III`). Players with no
   salary match are dropped and the count is reported.
4. **Metrics** (`analysis.compute_advanced_metrics`):
   - **TS%** — `PTS / (2 * (FGA + 0.44 * FTA))`, the standard shooting-efficiency formula.
   - **EFF** — a simplified per-game efficiency score (PTS + REB + AST + STL + BLK minus
     missed shots and turnovers), the same idea as the NBA's official "EFF" stat.
   - **Value Index** — `EFF / (salary in $M)`. Higher means more production per dollar.
5. **Output** — a correlation matrix (salary vs. PTS/REB/AST/EFF/TS%/MIN), a top-15
   "most undervalued players" table, and four charts (`visualizations.py`).

## Example output

| Chart | What it shows |
|---|---|
| `salary_vs_performance.png` | Scatter of salary vs. efficiency, colored by position |
| `correlation_heatmap.png` | Correlation matrix across salary and performance stats |
| `top_value_players.png` | Players with the highest production per salary dollar |
| `position_breakdown.png` | Average salary and Value Index by position |

More examples in [`examples/`](examples/).

## Project structure

```
main.py             CLI entry point
analysis.py         live data fetching, merging, metric calculations
visualizations.py   chart generation
data/
  nba_salaries_2025_26.csv   real 2025-26 salary + position data (240 players)
output/              generated CSV + charts (gitignored)
examples/            committed example charts from a live run
```

## Caveats

- Requires network access — there's no bundled local stats file for 2025-26, unlike
  earlier versions of this project that shipped a static season dataset.
- The salary file covers 240 notable players; roughly 10-15% of the top scorers by
  points don't have a salary entry (recent rookies not yet in the export, or name
  variants the normalizer doesn't catch) and are dropped from the salary-linked analysis.
- The NBA Stats API is undocumented and can change or rate-limit without notice.
