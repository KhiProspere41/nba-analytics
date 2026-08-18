# NBA Player Performance Analytics

Analyzes the relationship between NBA player salaries and on-court performance for the
2025-26 season, using real per-game box scores and real salary/position data. Computes
advanced metrics (True Shooting %, an efficiency score, a salary-adjusted "Value Index"),
runs a correlation analysis, and produces seven charts.

![Salary vs Performance](examples/salary_vs_performance.png)

## Quickstart

```bash
pip install -r requirements.txt

python main.py                # bundled real 2025-26 box scores, offline, top 80 scorers
python main.py --live-data    # re-fetch current stats from the NBA Stats API instead
```

Other options:

```bash
python main.py --top-n 200          # widen to the top 200 scorers instead of 80
python main.py --skip-viz           # skip chart generation, just produce the CSV
python main.py --live-data --season 2024-25   # a different season, fetched live
```

Output lands in `output/`: `processed_player_data.csv` plus seven PNG charts.

## Data sources

- **Stats** — [`data/nba_dailyleaders_2025_26.csv`](data/nba_dailyleaders_2025_26.csv):
  real per-game box scores for the 2025-26 season (582 players, 26,651 game rows), pulled
  from the official **[NBA Stats API](https://www.nba.com/stats)** (`stats.nba.com`) via
  its `LeagueGameLog` endpoint, accessed through the
  **[`nba_api`](https://github.com/swar/nba_api)** Python client, and bundled so the
  project runs offline by default. `analysis.aggregate_season_stats()` collapses it into
  one season-average row per player. `--live-data` re-fetches current per-game stats from
  the same API instead of the bundled file — useful for a different season or the latest
  games. If that call fails, `main.py` catches `LiveDataUnavailable` and falls back to the
  bundled file automatically.
- **Salary & position** — [`data/nba_salaries_2025_26.csv`](data/nba_salaries_2025_26.csv):
  real 2025-26 salaries and positions for 475 players, sourced from
  **[ESPN NBA Salaries](https://www.espn.com/nba/salaries/_/year/2026/seasontype/4)**
  (`espn.com/nba/salaries`), transcribed from a plain-text export (rank/name/team/salary,
  position embedded in the name field). Positions are ESPN's own broad G/F/C
  classification — a handful of rows used the finer PG/SG/SF/PF labels (apparent
  data-entry inconsistencies on ESPN's end); those are normalized to G/F/C to match the
  rest.
- **Awards** — [`data/nba_player_awards.csv`](data/nba_player_awards.csv): career award
  counts (MVP, DPOY, ROY, Most Improved, Finals MVP, championships, All-Star, All-NBA,
  All-Defensive, All-Rookie selections) for 474 of the 475 salaried players, pulled from
  the NBA Stats API's `PlayerAwards` endpoint via `nba_api`. Regenerate it with
  [`scripts/fetch_awards.py`](scripts/fetch_awards.py) (~475 requests, a few minutes). A
  `MAJOR_AWARDS` column sums all of the above into one composite accolade count. One
  player (a recent, obscure signing) had no matching ID in `nba_api`'s static player list
  and is treated as having zero awards.
  ⚠️ Matching a player name to an `nba_api` player ID must preserve suffixes exactly
  (`"Gary Payton II"`, not `"Gary Payton"`) — `nba_api`'s static list spans all of NBA
  history and includes real father/son pairs under the same base name (Gary Payton /
  Gary Payton II, Larry Nance / Larry Nance Jr., Tim Hardaway / Tim Hardaway Jr.).
  Stripping suffixes here, like `analysis._name_key` does for the salary/stats join,
  silently collided active players with their retired, more decorated relatives on the
  first pull of this data — Gary Payton II briefly showed his father's 9 All-Star nods,
  9 All-Defensive selections, and 1996 DPOY. `scripts/fetch_awards.py` matches on exact
  full names for this reason.

## How it works

1. **Aggregate** — box-score rows are grouped by player: games played, season-total
   points (used for ranking), and per-game averages for every stat.
2. **Select top N** — `analysis.select_top_players()` keeps the top 80 players (`--top-n`
   to change it) ranked by total season points, before the salary join.
3. **Merge salary** — joined by player name, normalized to survive accents, periods, and
   suffixes (e.g. `Nikola Jokić` vs `Nikola Jokic`, trailing `Jr.`/`III`). Players with no
   salary match are dropped and the count is reported.
4. **Merge awards** — career award counts are left-joined the same way; unlike the salary
   join, a non-match here just means zero career awards on record, so no players are
   dropped at this step.
5. **Metrics** (`analysis.compute_advanced_metrics`):
   - **TS%** — `PTS / (2 * (FGA + 0.44 * FTA))`, the standard shooting-efficiency formula.
   - **EFF** — a simplified per-game efficiency score (PTS + REB + AST + STL + BLK minus
     missed shots and turnovers), the same idea as the NBA's official "EFF" stat.
   - **Value Index** — `EFF / (salary in $M)`. Higher means more production per dollar.
6. **Output** — a correlation matrix (salary vs. PTS/REB/AST/EFF/TS%/MIN/MAJOR_AWARDS),
   top-15 "most undervalued," "most overpaid," and "most decorated" tables
   (`analysis.top_value_players` / `analysis.bottom_value_players` /
   `analysis.most_decorated_players`), and seven charts (`visualizations.py`).

## Example output

| Chart | What it shows |
|---|---|
| `salary_vs_performance.png` | Scatter of salary vs. efficiency, colored by position |
| `correlation_heatmap.png` | Correlation matrix across salary and performance stats |
| `top_value_players.png` | Players with the highest production per salary dollar |
| `bottom_value_players.png` | Highest-paid players producing the least per dollar |
| `awards_vs_salary.png` | Scatter of career major awards vs. salary, colored by position |
| `most_decorated_players.png` | Players with the highest career major-award counts |
| `position_breakdown.png` | Average salary and Value Index by position |

More examples in [`examples/`](examples/), generated from the bundled dataset so they're
reproducible without a live API call. For a full walkthrough of each chart with the
actual numbers behind it, see [`CHARTS.md`](CHARTS.md).

## Project structure

```
main.py             CLI entry point
analysis.py         data loading, aggregation, merging, metric calculations
visualizations.py   chart generation
scripts/
  fetch_awards.py                 regenerates nba_player_awards.csv from the NBA Stats API
data/
  nba_dailyleaders_2025_26.csv   real 2025-26 per-game box scores (582 players)
  nba_salaries_2025_26.csv       real 2025-26 salary + position data (475 players)
  nba_player_awards.csv          career award counts (474 players)
output/              generated CSV + charts (gitignored)
examples/            committed example charts from the bundled dataset
```

## Caveats

- The salary file covers 475 players — enough that, as of this writing, every one of the
  top 80 scorers has a salary match. That can still slip below 100% over time as rosters
  turn over (trades, new call-ups) faster than the bundled file is refreshed; any
  unmatched players are dropped and the count is reported.
- Positions are ESPN's broad G/F/C classification, not the traditional PG/SG/SF/PF/C
  breakdown — see Data sources above.
- The "most overpaid" list (`bottom_value_players.png`) is dominated by max-contract
  superstars (Curry, Booker, LeBron, Durant, etc.) — that's expected, not a bug. Value
  Index measures production *per salary dollar*, and at the $50M+ tier even an All-NBA
  season can't keep pace with the denominator. Read it as "lowest surplus value relative
  to cost," not "worst players."
- Symmetrically, the "most undervalued" list (`top_value_players.png`) is dominated by
  players on rookie-scale or minimum contracts producing solid rotation-level stats —
  not necessarily the best players in the league, just the cheapest ones relative to
  their output. Read it as "highest surplus value relative to cost," not "best players."
- The bundled box score log is a point-in-time snapshot — it won't include games played
  after it was pulled. Use `--live-data` for the latest numbers.
- The NBA Stats API is undocumented and can change or rate-limit without notice; that's
  what the `--live-data` fallback path is for.
- `MAJOR_AWARDS` is an unweighted sum — an MVP counts the same as a single All-Star
  selection. It's meant as a rough "how decorated is this player" signal alongside Value
  Index, not a serious accolade-weighted rating.
- The awards file is a point-in-time snapshot of career totals, like the box score log —
  it won't reflect awards announced after it was pulled (e.g. this season's eventual
  All-Star selections, which are typically named partway through the season).
