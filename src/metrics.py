"""Route-level metrics: Break Sharpness and separation at the throw.

For every WR/TE/RB route run between the snap and the throw on a Man or Zone
play, compute:

  * break_angle  - largest heading change (deg) over a 0.5 s window, searched
                   only where the receiver is already moving >= MIN_SPEED
  * sharpness    - break_angle x speed retention (speed after / before, <= 1)
  * separation   - distance (yd) to the nearest Coverage defender at the throw

Writes outputs/route_metrics.csv (one row per route).

    python -m src.metrics              # all 122 games
    python -m src.metrics --games 5    # quick run on the first 5 games
"""

from __future__ import annotations

import argparse
import time

import numpy as np
import pandas as pd

from src.paths import (
    OUTPUTS,
    ROUTE_POSITIONS,
    load_pff,
    load_players,
    load_plays,
    load_tracking,
    normalize_tracking,
    tracking_files,
)

# Tracking is 10 fps, so 5 frames = 0.5 s (the break window from CLAUDE.md).
BREAK_FRAMES = 5
# `dir` is noise when a player is nearly still (see EDA_FINDINGS.md). Only
# frames where the receiver already moves this fast can start a break.
MIN_SPEED = 3.0
# Centered rolling mean on the unwrapped heading, to damp frame-to-frame jitter.
SMOOTH_FRAMES = 3

COVERAGES = ("Man", "Zone")
OUT_FILE = OUTPUTS / "route_metrics.csv"


# --------------------------------------------------------------------------- #
# Inputs that do not depend on tracking
# --------------------------------------------------------------------------- #
def load_context() -> dict[str, pd.DataFrame]:
    """Load the small tables once and filter them to the analysis sample."""
    plays = load_plays()
    plays = plays.loc[
        plays["pff_passCoverageType"].isin(COVERAGES),
        ["gameId", "playId", "down", "yardsToGo", "passResult",
         "pff_passCoverage", "pff_passCoverageType"],
    ]

    # Snap/throw frames for every play with both events (built by src.eda).
    windows = pd.read_csv(OUTPUTS / "play_windows.csv")
    windows[["snap_frame", "throw_frame"]] = windows[["snap_frame", "throw_frame"]].astype(int)
    plays = plays.merge(windows[["gameId", "playId", "snap_frame", "throw_frame"]],
                        on=["gameId", "playId"], how="inner")

    pff = load_pff()[["gameId", "playId", "nflId", "pff_role"]]
    players = load_players()[["nflId", "displayName", "officialPosition"]]

    routes = pff.loc[pff["pff_role"].eq("Pass Route")].merge(players, on="nflId")
    routes = routes.loc[routes["officialPosition"].isin(ROUTE_POSITIONS)]
    routes = routes.merge(plays[["gameId", "playId"]], on=["gameId", "playId"])

    defenders = pff.loc[pff["pff_role"].eq("Coverage"), ["gameId", "playId", "nflId"]]

    return {"plays": plays, "routes": routes, "defenders": defenders}


# --------------------------------------------------------------------------- #
# Core math (pure functions on arrays, easy to test)
# --------------------------------------------------------------------------- #
def smooth_heading(dir_deg: np.ndarray) -> np.ndarray:
    """Unwrap `dir` across 0/360, then smooth it. Returns degrees."""
    unwrapped = np.degrees(np.unwrap(np.radians(dir_deg)))
    return (
        pd.Series(unwrapped)
        .rolling(SMOOTH_FRAMES, center=True, min_periods=1)
        .mean()
        .to_numpy()
    )


def break_sharpness(dir_deg: np.ndarray, speed: np.ndarray) -> dict[str, float] | None:
    """Find the main break in one route and score it.

    The break is the largest heading change over BREAK_FRAMES frames, chosen
    only among start frames where speed >= MIN_SPEED. Returns None when the
    route is too short or never reaches the speed gate.
    """
    if len(dir_deg) <= BREAK_FRAMES or np.isnan(dir_deg).any():
        return None

    heading = smooth_heading(dir_deg)
    change = np.abs(heading[BREAK_FRAMES:] - heading[:-BREAK_FRAMES])
    s_before = speed[:-BREAK_FRAMES]
    s_after = speed[BREAK_FRAMES:]

    eligible = s_before >= MIN_SPEED
    if not eligible.any():
        return None

    i = int(np.argmax(np.where(eligible, change, -np.inf)))
    retention = min(s_after[i] / s_before[i], 1.0)
    return {
        "break_angle": float(change[i]),
        "speed_before": float(s_before[i]),
        "speed_after": float(s_after[i]),
        "speed_retention": float(retention),
        "sharpness": float(change[i] * retention),
        "break_frame_offset": i,  # frames after the snap where the break starts
    }


def nearest_distance(rx: np.ndarray, ry: np.ndarray,
                     dx: np.ndarray, dy: np.ndarray) -> np.ndarray:
    """Distance from each receiver to the closest defender (yards)."""
    return np.hypot(rx[:, None] - dx[None, :], ry[:, None] - dy[None, :]).min(axis=1)


# --------------------------------------------------------------------------- #
# One game
# --------------------------------------------------------------------------- #
def process_game(game_id: int, ctx: dict[str, pd.DataFrame]) -> pd.DataFrame:
    plays = ctx["plays"].loc[ctx["plays"]["gameId"].eq(game_id)]
    if plays.empty:
        return pd.DataFrame()
    routes = ctx["routes"].loc[ctx["routes"]["gameId"].eq(game_id)]
    defenders = ctx["defenders"].loc[ctx["defenders"]["gameId"].eq(game_id)]

    trk = normalize_tracking(load_tracking(game_id))
    trk = trk.merge(plays[["playId", "snap_frame", "throw_frame"]], on="playId")
    trk = trk.loc[trk["frameId"].between(trk["snap_frame"], trk["throw_frame"])]
    trk = trk.sort_values(["playId", "nflId", "frameId"])

    # Line of scrimmage = ball x at the snap; used for route depth at the throw.
    ball = trk.loc[trk["team"].eq("football") & trk["frameId"].eq(trk["snap_frame"])]
    los = ball.set_index("playId")["x"]

    at_throw = trk.loc[trk["frameId"].eq(trk["throw_frame"])]
    def_at_throw = at_throw.merge(defenders[["playId", "nflId"]], on=["playId", "nflId"])

    route_trk = trk.merge(routes[["playId", "nflId"]], on=["playId", "nflId"])

    rows = []
    for play_id, play_trk in route_trk.groupby("playId", sort=False):
        d = def_at_throw.loc[def_at_throw["playId"].eq(play_id)]
        throw_pos = at_throw.loc[at_throw["playId"].eq(play_id)].set_index("nflId")

        for nfl_id, r in play_trk.groupby("nflId", sort=False):
            brk = break_sharpness(r["dir"].to_numpy(), r["s"].to_numpy())
            if brk is None or nfl_id not in throw_pos.index or d.empty:
                continue
            rx, ry = throw_pos.loc[nfl_id, ["x", "y"]].to_numpy(dtype=float)
            sep = nearest_distance(np.array([rx]), np.array([ry]),
                                   d["x"].to_numpy(), d["y"].to_numpy())[0]
            rows.append({
                "gameId": game_id,
                "playId": play_id,
                "nflId": int(nfl_id),
                **brk,
                "break_time_s": brk["break_frame_offset"] / 10.0,
                "separation": float(sep),
                "route_depth": float(rx - los.get(play_id, np.nan)),
                "n_frames": len(r),
            })
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- #
# All games
# --------------------------------------------------------------------------- #
def build_route_metrics(ctx: dict[str, pd.DataFrame],
                        n_games: int | None = None) -> pd.DataFrame:
    game_ids = [int(p.stem.split("_")[1]) for p in tracking_files()][:n_games]

    parts = []
    t0 = time.time()
    for k, gid in enumerate(game_ids, 1):
        parts.append(process_game(gid, ctx))
        if k % 20 == 0 or k == len(game_ids):
            print(f"  {k}/{len(game_ids)} games  ({time.time() - t0:.0f} s)")

    out = pd.concat(parts, ignore_index=True).drop(columns="break_frame_offset")

    # Attach player and play context.
    out = out.merge(
        ctx["routes"][["gameId", "playId", "nflId", "displayName", "officialPosition"]],
        on=["gameId", "playId", "nflId"], how="left",
    ).merge(ctx["plays"], on=["gameId", "playId"], how="left")
    out["time_to_throw"] = (out["throw_frame"] - out["snap_frame"]) / 10.0
    out = out.rename(columns={
        "officialPosition": "position",
        "pff_passCoverageType": "coverage",
        "pff_passCoverage": "coverage_scheme",
    }).drop(columns=["snap_frame", "throw_frame"])

    cols = [
        "gameId", "playId", "nflId", "displayName", "position",
        "coverage", "coverage_scheme", "down", "yardsToGo", "passResult",
        "time_to_throw", "break_time_s", "break_angle", "speed_before",
        "speed_after", "speed_retention", "sharpness", "separation",
        "route_depth", "n_frames",
    ]
    return out[cols]


def summarize(df: pd.DataFrame, routes_in_sample: int) -> None:
    print(f"\nRoutes scored: {len(df):,} of {routes_in_sample:,} "
          f"({len(df) / routes_in_sample:.1%}); the rest never reached "
          f"{MIN_SPEED} yd/s or had missing tracking")
    print("\nBy position x coverage (route counts):")
    print(pd.crosstab(df["position"], df["coverage"], margins=True).to_string())
    print("\nMedians by position x coverage:")
    print(df.groupby(["position", "coverage"])[["break_angle", "sharpness", "separation"]]
            .median().round(2).to_string())
    print(f"\nBreak angle > 120 deg: {(df['break_angle'] > 120).mean():.1%}")
    print(f"Separation outside 0-40 yd: {(~df['separation'].between(0, 40)).sum()}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--games", type=int, default=None,
                        help="only process the first N games (quick check)")
    args = parser.parse_args()

    print(f"Computing route metrics (gate {MIN_SPEED} yd/s, "
          f"{BREAK_FRAMES}-frame break window)...")
    ctx = load_context()
    df = build_route_metrics(ctx, args.games)
    if args.games is None:
        df.to_csv(OUT_FILE, index=False)
        print(f"saved {OUT_FILE.relative_to(OUTPUTS.parent)}")
    else:
        print("(quick run: not saving)")

    total = ctx["routes"]
    if args.games is not None:
        total = total.loc[total["gameId"].isin(df["gameId"].unique())]
    summarize(df, len(total))


if __name__ == "__main__":
    main()
