"""Run the whole Break Sharpness pipeline: raw tracking data -> outputs/.

    python run.py          # metrics -> analysis -> charts (about 1 minute)
    python run.py --eda    # also re-run the exploratory checks first

Steps:
  0. (optional) src.eda       data checks; writes outputs/play_windows.csv and
                              outputs/eda_report.txt
  1. src.metrics              Break Sharpness + separation for every route
                              -> outputs/route_metrics.csv
  2. src.analysis             fair Man vs Zone comparison + leaderboard
                              -> outputs/coverage_effect.csv, regression_summary.csv,
                                 leaderboard.csv
  3. src.charts               README figures -> outputs/figures/*.png
  4. src.site                 data for the interactive page -> docs/data.js
"""

from __future__ import annotations

import argparse
import contextlib
import sys
import time

from src.paths import DATA, OUTPUTS, TRACKING

DATA_REPO = "https://github.com/ThompsonJamesBliss/nfl-big-data-bowl-regional-event-data"
WINDOWS_FILE = OUTPUTS / "play_windows.csv"
EDA_REPORT = OUTPUTS / "eda_report.txt"


def check_data() -> None:
    needed = ["games.csv", "plays.csv", "players.csv", "pffScoutingData.csv"]
    missing = [f for f in needed if not (DATA / f).exists()]
    if missing or not any(TRACKING.glob("tracking_*.csv")):
        print("Data not found.\n"
              f"Expected the Big Data Bowl files in: {DATA}\n\n"
              "Download them (about 830 MB) from the repo root with:\n\n"
              f"  git clone {DATA_REPO} data/nfl-big-data-bowl-regional-event-data\n",
              file=sys.stderr)
        sys.exit(1)


def step(name: str):
    """Print a header and the time a step took."""
    @contextlib.contextmanager
    def timer():
        print(f"\n=== {name} ===", flush=True)
        t0 = time.time()
        yield
        print(f"--- {name}: done in {time.time() - t0:.0f} s", flush=True)
    return timer()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Break Sharpness pipeline.")
    parser.add_argument("--eda", action="store_true",
                        help="re-run the exploratory checks (src.eda) first")
    args = parser.parse_args()

    check_data()
    OUTPUTS.mkdir(exist_ok=True)
    t0 = time.time()

    # The EDA builds the snap/throw window cache the metrics step reuses.
    if args.eda or not WINDOWS_FILE.exists():
        from src import eda
        with step(f"0. EDA checks (report -> {EDA_REPORT.relative_to(OUTPUTS.parent)})"):
            with open(EDA_REPORT, "w") as fh, contextlib.redirect_stdout(fh):
                eda.main()

    from src import analysis, charts, metrics, site

    with step("1. Route metrics"):
        ctx = metrics.load_context()
        df = metrics.build_route_metrics(ctx)
        df.to_csv(metrics.OUT_FILE, index=False)
        print(f"saved {metrics.OUT_FILE.relative_to(OUTPUTS.parent)}")
        metrics.summarize(df, len(ctx["routes"]))

    with step("2. Man vs Zone analysis + leaderboard"):
        analysis.main()

    with step("3. Charts"):
        charts.main()

    with step("4. Interactive page data (docs/data.js)"):
        site.main()

    print(f"\nAll done in {time.time() - t0:.0f} s. Results are in "
          f"{OUTPUTS.relative_to(OUTPUTS.parent)}/")


if __name__ == "__main__":
    main()
