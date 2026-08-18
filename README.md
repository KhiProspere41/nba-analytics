# NBA Player Performance Analytics

Analyzes the relationship between NBA player salaries and on-court performance for the
2024-25 season, using real per-game box scores and real salary data. Computes advanced
metrics (True Shooting %, an efficiency score, a salary-adjusted "Value Index"), runs a
correlation analysis, and produces four charts.

![Salary vs Performance](examples/salary_vs_performance.png)

## Quickstart

```bash
pip install -r requirements.txt

# Bundled real 2024-25 season data, offline, top 80 scorers
python main.py --skip-viz

# Full run with charts
python main.py

# Or pull current stats from the NBA Stats API instead
python main.py --live-data
```

Other options:

```bash
python main.py --top-n 200          # widen to the top 200 scorers instead of 80
python main.py --live-data --season 2023-24
```

Output lands in `output/`: `processed_player_data.csv` plus four PNG charts.

## Data sources

- **`data/nba_dailyleaders_2024_25.csv`** — real per-game box scores for the 2024-25
  season (569 players, 28,265 game rows), including playoffs. `analysis.aggregate_season_stats()`
  collapses this into one season-average row per player.
- **`data/nba_salaries_2024_25.csv`** — real 2024-25 salary data. Rows reporting `$0` are
  treated as missing/unreported (not an actual $0 salary — the file lists it for several
  clearly active, highly paid players) and dropped rather than used as-is.
- **`--live-data`** swaps both of the above for a live pull from the official NBA Stats
  API (`nba_api`) instead, for a different/current season. If that call fails, `main.py`
  catches `LiveDataUnavailable` and falls back to the bundled files automatically.

## How it works

1. **Aggregate** — box-score rows are grouped by player: games played, season-total
   points (used for ranking), and per-game averages for every stat.
2. **Select top N** — `analysis.select_top_players()` keeps the top 80 players (`--top-n`
   to change it) ranked by total season points, before the salary join.
3. **Merge salary** — joined by player name, normalized to survive accents, periods, and
   suffixes (e.g. `Nikola Jokić` / `Alperen Şengün`, `A.J. Green` vs `AJ Green`, trailing
   `Jr.`). Players with no usable salary match are dropped and the count is reported.
4. **Metrics** (`analysis.compute_advanced_metrics`):
   - **TS%** — `PTS / (2 * (FGA + 0.44 * FTA))`, the standard shooting-efficiency formula.
   - **EFF** — a simplified per-game efficiency score: PTS + AST + STL + BLK minus missed
     shots and turnovers. Rebounds are intentionally excluded — the source box score file
     doesn't include a rebounds column.
   - **Value Index** — `EFF / (salary in $M)`. Higher means more production per dollar.
5. **Output** — a correlation matrix (salary vs. PTS/AST/EFF/TS%/MIN), a top-15 "most
   undervalued players" table, and four charts (`visualizations.py`).

## Example output

| Chart | What it shows |
|---|---|
| `salary_vs_performance.png` | Scatter of salary vs. efficiency, sized by points/game |
| `correlation_heatmap.png` | Correlation matrix across salary and performance stats |
| `top_value_players.png` | Players with the highest production per salary dollar |
| `team_breakdown.png` | Average salary and Value Index by team |

More examples in [`examples/`](examples/), generated from the bundled dataset so they're
reproducible without a live API call.

## Project structure

```
main.py             CLI entry point
analysis.py         data loading, aggregation, merging, metric calculations
visualizations.py   chart generation
data/
  nba_dailyleaders_2024_25.csv   real 2024-25 per-game box scores
  nba_salaries_2024_25.csv       real 2024-25 salary data
output/              generated CSV + charts (gitignored)
examples/            committed example charts from the bundled dataset
```

## Caveats

- Only ~56% of the top 80 scorers have usable salary data (many well-known players show
  `$0` in the source salary file and are dropped rather than guessed at) — the
  salary-linked analysis runs on that smaller, real subset.
- Season averages blend regular-season and playoff games (some players show more than 82
  games played as a result), since the box score file doesn't separate them.
- No rebounds or position data exist in the source box scores, so `EFF` and the charts
  are built without them — see "How it works" above.
- The NBA Stats API (`--live-data`) is undocumented and can change or rate-limit without
  notice; that's what the fallback path is for.
