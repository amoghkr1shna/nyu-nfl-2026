# Break Sharpness vs. Man/Zone Coverage

NFL Big Data Bowl — NYU Edition (2021 season, Weeks 1–8).

**Audience:** scouts and coaches.

## Summary

_TODO: fill in from results._

We built Break Sharpness, a metric that scores how sharply a WR, TE, or RB changes direction at the top of his route while keeping speed, using 2021 Next Gen Stats tracking data. Comparing it to separation from the nearest defender at the throw shows [whether sharp breaks create space against man coverage but not zone]. [Player X] posts the sharpest breaks among [position], averaging [Y] yards of separation against man. Scouts can use it to evaluate route-running beyond 40 times, and coaches can use it to decide which receivers to feature against man-heavy defenses.

![Break Sharpness vs. separation, man vs. zone](outputs/figures/sharpness_vs_separation.png)

## Results at a glance

You don't need to run anything to see the results; they are committed in `outputs/`:

| File | What it is |
|---|---|
| `outputs/figures/sharpness_vs_separation.png` | Main chart: binned Break Sharpness vs. mean separation, Man vs. Zone, faceted by WR / TE / RB |
| `outputs/leaderboard.csv` | Top players by mean Break Sharpness (minimum route count applies) |
| `outputs/route_metrics.csv` | One row per route: game, play, player, position, coverage, sharpness, separation |

## How to run

Requires Python 3.11+ (developed on 3.13).

1. Clone this repo:

   ```bash
   git clone <this-repo-url> && cd nyu-nfl-2026
   ```

2. Download the data (about 830 MB; it is not stored in this repo) into the expected folder:

   ```bash
   git clone https://github.com/ThompsonJamesBliss/nfl-big-data-bowl-regional-event-data data/nfl-big-data-bowl-regional-event-data
   ```

   The code reads from `data/nfl-big-data-bowl-regional-event-data/data/` (`games.csv`, `plays.csv`, `players.csv`, `pffScoutingData.csv`, `tracking/`).

3. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

4. Run the pipeline. It writes everything into `outputs/`:

   ```bash
   python run.py
   ```

## Method

1. **Normalize direction.** Flip every play so the offense moves toward +x (mirror `x`, `y`; rotate `o`, `dir` by 180° for left-moving plays).
2. **Routes.** Players with `pff_role == "Pass Route"` in `pffScoutingData.csv`, positions WR / TE / RB.
3. **Window.** From `ball_snap` to `pass_forward` (or their `autoevent_` versions). Plays with no forward pass (sacks, scrambles) are dropped.
4. **Break Sharpness.** Smooth `dir` (handling the 0/360 wraparound), find the largest direction change over a 0.5 s (5-frame) window, and multiply the angle change (degrees) by speed retention (speed after ÷ speed before the break, capped at 1).
5. **Separation.** Distance from the receiver to the nearest defender at the `pass_forward` frame.
6. **Coverage.** `pff_passCoverageType` from `plays.csv` (Man / Zone; "Other" excluded).

## Assumptions and limitations

- Separation is measured at the throw, not at the catch.
- All routes are included, not only targeted ones.
- Each route is assumed to have one main break (the largest direction change).
- The nearest defender is a proxy for the covering defender.

## Repo layout

```
src/            analysis code (paths, loaders, metrics)
run.py          single entry point: data -> outputs/
outputs/        committed results (CSVs and figures)
data/           raw data, cloned separately (git-ignored)
```
