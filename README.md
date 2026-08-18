# NBA Player Performance Analytics

Analyzes the relationship between NBA player salaries and on-court performance using
live data from the official NBA Stats API. Computes advanced metrics (True Shooting %,
efficiency score, a salary-adjusted "Value Index"), runs a correlation analysis, and
produces four charts.

![Salary vs Performance](examples/salary_vs_performance.png)

## Quickstart

```bash
pip install -r requirements.txt

# Instant offline run on the bundled sample dataset
python main.py --sample-data --skip-viz

# Fetch real current-season stats from stats.nba.com and generate charts
python main.py --live-data
```

Other options:

```bash
python main.py --live-data --season 2022-23   # a specific season
python main.py --sample-data                  # sample data + charts
```

Output lands in `output/`: `processed_player_data.csv` plus four PNG charts.

## How it works

1. **Stats** — `analysis.fetch_live_stats()` calls `LeagueDashPlayerStats` from
   [`nba_api`](https://github.com/swar/nba_api), the Python wrapper around the same
   endpoints stats.nba.com's own site uses. Player position is filled in from
   `PlayerIndex`. If the API call fails (network down, endpoint changed, rate limited),
   `main.py` catches `LiveDataUnavailable` and falls back to the bundled sample dataset
   automatically.
2. **Salary** — `data/salary_data.csv` is a hand-compiled table of ~90 players' 2023-24
   salaries (public reporting). Stats are joined to it by player name; unmatched players
   are dropped and reported.
3. **Sample dataset** — `data/sample_stats.csv` is synthetic-but-consistent per-game data
   generated from each player's salary tier plus noise (see the generation logic — it's
   not real box scores). It exists so the project runs instantly with no network call;
   `--live-data` is what pulls real numbers.
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

More examples in [`examples/`](examples/) (generated from the sample dataset, so they're
reproducible without a live API call).

## Project structure

```
main.py             CLI entry point
analysis.py         data fetching, merging, metric calculations
visualizations.py   chart generation
data/
  salary_data.csv   player -> 2023-24 salary lookup
  sample_stats.csv  offline sample stats (generated, not real box scores)
output/              generated CSV + charts (gitignored)
examples/            committed example charts from the sample dataset
```

## Caveats

- Salary data is a static snapshot (~90 notable players) compiled from public reporting;
  it doesn't reflect in-season trades or signings.
- The sample dataset's stats are synthetic and meant only for fast offline testing —
  use `--live-data` for real numbers.
- The NBA Stats API is undocumented and can change or rate-limit without notice; that's
  what the fallback path is for.
