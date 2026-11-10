## How to run

Requires Python 3.11+ (developed on 3.13). All results are already committed in `outputs/`, so you only need to run this to reproduce them.

1. Clone this repo:

   ```bash
   git clone https://github.com/amoghkr1shna/nyu-nfl-2026 && cd nyu-nfl-2026
   ```

2. Download the data (about 830 MB; not stored in this repo):

   ```bash
   git clone https://github.com/ThompsonJamesBliss/nfl-big-data-bowl-regional-event-data data/nfl-big-data-bowl-regional-event-data
   ```

3. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

4. Run everything (about a minute):

   ```bash
   python run.py
   ```

   Add `--eda` to also rerun the exploratory checks.

## Repo layout

```
run.py              one command: metrics -> analysis -> charts -> page data
src/paths.py        file paths, loaders, direction normalization
src/eda.py          data checks (report: outputs/eda_report.txt)
src/metrics.py      Break Sharpness + space gained for every route
src/analysis.py     fair man-vs-zone comparison + leaderboard
src/charts.py       the three figures in the README
src/site.py         exports results to docs/data.js for the interactive page
docs/               interactive page (GitHub Pages): index.html + data.js
EDA_FINDINGS.md     what the data checks found, and the bug they caught
outputs/            results: route_metrics.csv, coverage_effect.csv,
                    regression_summary.csv, leaderboard.csv, figures/
data/               raw data, downloaded separately (git-ignored)
```

## Data

- Tracking, plays, players and PFF scouting data: [NFL Big Data Bowl regional event data](https://github.com/ThompsonJamesBliss/nfl-big-data-bowl-regional-event-data) (NFL Next Gen Stats, Pro Football Focus), 2021 season Weeks 1–8.
- No external data was used.
