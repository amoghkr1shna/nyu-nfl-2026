"""Exploratory data analysis for Break Sharpness vs. man/zone coverage.

Runs the pre-analysis checks: coverage column values, event availability in
tracking, the route population after filtering, and a normalized sample play.

    python -m src.eda
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.paths import (
    FIELD_LENGTH,
    FIELD_WIDTH,
    FIGURES,
    OUTPUTS,
    ROUTE_POSITIONS,
    load_games,
    load_pff,
    load_players,
    load_plays,
    load_tracking,
    normalize_tracking,
    tracking_files,
)

# Number of games sampled for the event-availability and frame-rate checks.
EVENT_CHECK_GAMES = 12


def header(title: str) -> None:
    print(f"\n{'=' * 78}\n{title}\n{'=' * 78}")


def check_shapes(games, players, plays, pff) -> None:
    header("1. FILE SHAPES")
    for name, df in [
        ("games.csv", games),
        ("players.csv", players),
        ("plays.csv", plays),
        ("pffScoutingData.csv", pff),
    ]:
        print(f"{name:<24} {df.shape[0]:>8,} rows  x {df.shape[1]:>3} cols")
    print(f"{'tracking/*.csv':<24} {len(tracking_files()):>8,} games")
    print(
        f"\ngames: season(s) {sorted(games['season'].unique())}, "
        f"weeks {games['week'].min()}-{games['week'].max()}"
    )
    print(f"plays: {plays.groupby(['gameId', 'playId']).ngroups:,} unique gameId+playId")


def check_coverage(plays: pd.DataFrame) -> pd.DataFrame:
    header("2. COVERAGE COLUMNS (the man/zone label)")

    print("pff_passCoverageType value counts (incl. missing):")
    vc = plays["pff_passCoverageType"].value_counts(dropna=False)
    for value, n in vc.items():
        print(f"  {str(value):<10} {n:>6,}  ({n / len(plays):>6.1%})")

    print("\npff_passCoverage (the specific scheme) — top 15:")
    for value, n in plays["pff_passCoverage"].value_counts(dropna=False).head(15).items():
        print(f"  {str(value):<28} {n:>6,}  ({n / len(plays):>6.1%})")

    print("\nCrosstab: scheme x type (sanity-check the Man/Zone mapping)")
    ct = pd.crosstab(plays["pff_passCoverage"], plays["pff_passCoverageType"])
    print(ct.to_string())

    print("\npassResult value counts:")
    for value, n in plays["passResult"].value_counts(dropna=False).items():
        print(f"  {str(value):<10} {n:>6,}  ({n / len(plays):>6.1%})")

    print("\nplayDirection is on tracking, not plays. offenseFormation:")
    for value, n in plays["offenseFormation"].value_counts(dropna=False).items():
        print(f"  {str(value):<12} {n:>6,}")

    print("\nMissing-value rate for analysis columns:")
    cols = [
        "down",
        "yardsToGo",
        "passResult",
        "offenseFormation",
        "defendersInBox",
        "dropBackType",
        "pff_playAction",
        "pff_passCoverage",
        "pff_passCoverageType",
    ]
    for col in cols:
        print(f"  {col:<24} {plays[col].isna().mean():>6.2%}")

    return plays


def check_roles(pff: pd.DataFrame, players: pd.DataFrame) -> pd.DataFrame:
    header("3. PFF ROLES AND THE ROUTE POPULATION")

    print("pff_role value counts:")
    for value, n in pff["pff_role"].value_counts(dropna=False).items():
        print(f"  {str(value):<14} {n:>8,}  ({n / len(pff):>6.1%})")

    routes = pff.loc[pff["pff_role"].eq("Pass Route")].merge(
        players[["nflId", "officialPosition", "displayName"]], on="nflId", how="left"
    )
    print(f"\nPass Route rows: {len(routes):,}")
    print("\nofficialPosition of Pass Route players:")
    for value, n in routes["officialPosition"].value_counts(dropna=False).items():
        flag = " <- keep" if value in ROUTE_POSITIONS else ""
        print(f"  {str(value):<8} {n:>8,}{flag}")

    kept = routes.loc[routes["officialPosition"].isin(ROUTE_POSITIONS)]
    print(f"\nRoutes at WR/TE/RB: {len(kept):,}  ({len(kept) / len(routes):.1%} of routes)")
    print(f"Distinct players: {kept['nflId'].nunique():,}")
    print(f"Routes per play: mean {len(kept) / kept.groupby(['gameId', 'playId']).ngroups:.2f}")

    print("\nRoutes per player (for the min-route leaderboard threshold):")
    per_player = kept.groupby("nflId").size()
    print(per_player.describe().to_string())
    for thresh in (10, 20, 30, 50, 75, 100):
        print(f"  players with >= {thresh:>3} routes: {(per_player >= thresh).sum():>4}")

    print("\nWR/TE/RB route counts by position at >=30 routes:")
    pos = kept.groupby(["nflId", "officialPosition"]).size().reset_index(name="n")
    print(pos.loc[pos["n"] >= 30, "officialPosition"].value_counts().to_string())

    print("\npff_positionLinedUp for kept routes — top 12:")
    print(kept["pff_positionLinedUp"].value_counts().head(12).to_string())

    return kept


def check_events(plays: pd.DataFrame) -> pd.DataFrame:
    header(f"4. TRACKING EVENTS (sample of {EVENT_CHECK_GAMES} games)")

    files = tracking_files()
    step = max(1, len(files) // EVENT_CHECK_GAMES)
    sample = files[::step][:EVENT_CHECK_GAMES]

    event_counts: dict[str, int] = {}
    rows = []
    frames_per_play = []
    for path in sample:
        game_id = int(path.stem.split("_")[1])
        trk = pd.read_csv(path, usecols=["gameId", "playId", "frameId", "event", "playDirection"])
        for value, n in trk["event"].value_counts().items():
            event_counts[value] = event_counts.get(value, 0) + int(n)

        per_play = trk.groupby("playId").agg(
            n_frames=("frameId", "max"),
            events=("event", lambda s: set(s.dropna().unique())),
        )
        frames_per_play.append(per_play["n_frames"])
        rows.append(
            pd.DataFrame(
                {
                    "gameId": game_id,
                    "playId": per_play.index,
                    "has_snap": per_play["events"].apply(lambda s: "ball_snap" in s),
                    "has_forward": per_play["events"].apply(lambda s: "pass_forward" in s),
                }
            )
        )

    print("Event tag counts across sampled games (one tag per player-frame):")
    for value, n in sorted(event_counts.items(), key=lambda kv: -kv[1]):
        print(f"  {value:<26} {n:>8,}")

    per_play = pd.concat(rows, ignore_index=True)
    n = len(per_play)
    both = per_play["has_snap"] & per_play["has_forward"]
    print(f"\nSampled plays: {n:,}")
    print(f"  with ball_snap            {per_play['has_snap'].sum():>6,}  ({per_play['has_snap'].mean():.1%})")
    print(f"  with pass_forward         {per_play['has_forward'].sum():>6,}  ({per_play['has_forward'].mean():.1%})")
    print(f"  with BOTH (usable window) {both.sum():>6,}  ({both.mean():.1%})")

    frames = pd.concat(frames_per_play)
    print("\nFrames per play (10 fps, so ~1 frame = 0.1 s):")
    print(frames.describe().to_string())

    merged = per_play.merge(plays, on=["gameId", "playId"], how="left")
    print("\nWhy plays lack pass_forward — passResult of dropped plays:")
    dropped = merged.loc[~merged["has_forward"]]
    print(dropped["passResult"].value_counts(dropna=False).to_string())
    print("\nRetention of usable plays by coverage type:")
    print(
        merged.groupby("pff_passCoverageType", dropna=False)["has_forward"]
        .agg(plays="size", pct_with_forward="mean")
        .to_string()
    )
    return merged


def check_snap_to_throw(plays: pd.DataFrame) -> None:
    header("5. SNAP-TO-THROW WINDOW LENGTH (first 6 games)")
    rows = []
    for path in tracking_files()[:6]:
        game_id = int(path.stem.split("_")[1])
        trk = pd.read_csv(path, usecols=["playId", "frameId", "event"])
        ev = trk.loc[trk["event"].isin(["ball_snap", "pass_forward"])]
        pivot = ev.groupby(["playId", "event"])["frameId"].min().unstack()
        if {"ball_snap", "pass_forward"}.issubset(pivot.columns):
            pivot = pivot.dropna()
            pivot["gameId"] = game_id
            rows.append(pivot)
    win = pd.concat(rows)
    win["seconds"] = (win["pass_forward"] - win["ball_snap"]) / 10.0
    print(f"Plays with a clean snap->throw window: {len(win):,}")
    print(win["seconds"].describe(percentiles=[0.05, 0.25, 0.5, 0.75, 0.95]).to_string())
    print(f"\nWindows shorter than 1.0 s (too short for a 0.5 s break): {(win['seconds'] < 1.0).mean():.2%}")
    print(f"Windows shorter than 1.5 s: {(win['seconds'] < 1.5).mean():.2%}")


def check_tracking_columns() -> pd.DataFrame:
    header("6. TRACKING SCHEMA AND NORMALIZATION")
    trk = load_tracking(2021090900)
    print(f"tracking_2021090900.csv: {trk.shape[0]:,} rows x {trk.shape[1]} cols")
    print("\ndtypes:")
    print(trk.dtypes.to_string())
    print("\nplayDirection:")
    print(trk["playDirection"].value_counts().to_string())
    print("\nteam:")
    print(trk["team"].value_counts().to_string())
    print("\nMissing values per column:")
    print(trk.isna().mean().mul(100).round(2).to_string())

    print("\nRaw x/y/s/a/dir ranges:")
    print(trk[["x", "y", "s", "a", "o", "dir"]].describe().round(2).to_string())

    norm = normalize_tracking(trk)
    print("\nAfter normalization — mean x of offense at snap, by original playDirection:")
    snap = norm.loc[norm["event"].eq("ball_snap")]
    print(
        snap.groupby("playDirection")[["x", "y", "dir"]].mean().round(2).to_string()
    )
    return norm


def plot_sample_play(norm: pd.DataFrame, pff: pd.DataFrame, players: pd.DataFrame) -> None:
    header("7. SAMPLE PLAY PLOT")

    game_id = int(norm["gameId"].iloc[0])
    game_pff = pff.loc[pff["gameId"].eq(game_id)]

    # Pick a left-direction play with a pass_forward so the plot also proves the flip.
    candidates = (
        norm.loc[norm["playDirection"].eq("left")]
        .groupby("playId")["event"]
        .apply(lambda s: {"ball_snap", "pass_forward"}.issubset(set(s.dropna())))
    )
    play_id = int(candidates[candidates].index[0])

    play = norm.loc[norm["playId"].eq(play_id)].copy()
    snap = int(play.loc[play["event"].eq("ball_snap"), "frameId"].min())
    throw = int(play.loc[play["event"].eq("pass_forward"), "frameId"].min())
    window = play.loc[play["frameId"].between(snap, throw)]
    print(f"gameId {game_id}, playId {play_id} (playDirection=left)")
    print(f"snap frame {snap} -> throw frame {throw}  ({(throw - snap) / 10:.1f} s)")

    roles = game_pff.loc[game_pff["playId"].eq(play_id), ["nflId", "pff_role"]]
    window = window.merge(roles, on="nflId", how="left").merge(
        players[["nflId", "officialPosition", "displayName"]], on="nflId", how="left"
    )

    fig, ax = plt.subplots(figsize=(11, 6.5))
    for yard in range(10, 111, 5):
        ax.axvline(yard, color="0.88", lw=0.8, zorder=0)
    for yard in range(10, 111, 10):
        ax.axvline(yard, color="0.75", lw=1.2, zorder=0)
    for yard in (10, 110):
        ax.axvline(yard, color="0.3", lw=1.8, zorder=0)

    styles = {
        "Pass Route": ("#1b7837", "Route runner"),
        "Coverage": ("#762a83", "Coverage defender"),
        "Pass Rush": ("#d95f02", "Pass rush"),
        "Pass Block": ("#4575b4", "Pass block"),
        "Pass": ("#000000", "Passer"),
    }
    for role, (color, label) in styles.items():
        sub = window.loc[window["pff_role"].eq(role)]
        first = True
        for _, trace in sub.groupby("nflId"):
            trace = trace.sort_values("frameId")
            ax.plot(
                trace["x"], trace["y"], color=color, lw=1.6, alpha=0.85,
                label=label if first else None,
            )
            # Hollow marker = snap position, filled = position at the throw.
            ax.scatter(
                trace["x"].iloc[0], trace["y"].iloc[0],
                facecolors="white", edgecolors=color, s=26, lw=1.3, zorder=3,
            )
            ax.scatter(trace["x"].iloc[-1], trace["y"].iloc[-1], color=color, s=34, zorder=4)
            first = False

    ball = window.loc[window["team"].eq("football")].sort_values("frameId")
    ax.plot(ball["x"], ball["y"], color="saddlebrown", lw=2, ls="--", label="Ball")

    # Label receivers, nudging each label vertically so they do not collide.
    route_ends = (
        window.loc[window["pff_role"].eq("Pass Route")]
        .sort_values("frameId")
        .groupby("nflId")
        .last()
        .sort_values("y")
    )
    for i, (_, row) in enumerate(route_ends.iterrows()):
        ax.annotate(
            f"{row['displayName']} ({row['officialPosition']})",
            (row["x"], row["y"]),
            textcoords="offset points",
            xytext=(8, 8 if i % 2 == 0 else -14),
            fontsize=8,
            color="#1b7837",
        )

    pad = 4.0
    ax.set_xlim(max(0, window["x"].min() - pad), min(FIELD_LENGTH, window["x"].max() + pad))
    ax.set_ylim(0, FIELD_WIDTH)
    ax.set_xlabel("x (yards, normalized so the offense always attacks to the right)")
    ax.set_ylabel("y (yards)")
    ax.set_title(
        f"Normalization check — game {game_id}, play {play_id}\n"
        f"snap (hollow) to pass_forward (filled); original playDirection = left"
    )
    ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1.0), fontsize=8, frameon=False)
    ax.set_aspect("equal")
    fig.tight_layout()

    FIGURES.mkdir(parents=True, exist_ok=True)
    out = FIGURES / "eda_sample_play.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(f"saved {out.relative_to(FIGURES.parents[1])}")

    # Route runners must gain x after the flip; blockers legitimately lose x.
    routes = window.loc[window["pff_role"].eq("Pass Route")].sort_values("frameId")
    route_drift = routes.groupby("nflId")["x"].agg(lambda s: s.iloc[-1] - s.iloc[0])
    blockers = window.loc[window["pff_role"].eq("Pass Block")].sort_values("frameId")
    block_drift = blockers.groupby("nflId")["x"].agg(lambda s: s.iloc[-1] - s.iloc[0])
    print(f"Route runners gaining x: {(route_drift > 0).sum()}/{len(route_drift)}  "
          f"(median {route_drift.median():+.2f} yd)")
    print(f"Pass blockers, median x drift: {block_drift.median():+.2f} yd (negative = dropping back)")


def check_normalization_across_games(pff: pd.DataFrame, players: pd.DataFrame) -> None:
    header(f"7b. NORMALIZATION HOLDS BOTH DIRECTIONS ({EVENT_CHECK_GAMES} games)")

    files = tracking_files()
    step = max(1, len(files) // EVENT_CHECK_GAMES)
    receivers = set(
        pff.loc[pff["pff_role"].eq("Pass Route"), "nflId"]
        .pipe(lambda s: s[s.isin(players.loc[players["officialPosition"].isin(ROUTE_POSITIONS), "nflId"])])
    )

    rows = []
    for path in files[::step][:EVENT_CHECK_GAMES]:
        trk = normalize_tracking(load_tracking(int(path.stem.split("_")[1])))
        trk = trk.loc[trk["nflId"].isin(receivers)]
        throws = trk.loc[trk["event"].eq("pass_forward")].groupby("playId")["frameId"].min()
        snaps = trk.loc[trk["event"].eq("ball_snap")].groupby("playId")["frameId"].min()
        keys = snaps.index.intersection(throws.index)
        trk = trk.loc[trk["playId"].isin(keys)].copy()
        trk["snap"] = trk["playId"].map(snaps)
        trk["throw"] = trk["playId"].map(throws)
        win = trk.loc[trk["frameId"].between(trk["snap"], trk["throw"])]
        drift = (
            win.sort_values("frameId")
            .groupby(["playDirection", "playId", "nflId"])["x"]
            .agg(lambda s: s.iloc[-1] - s.iloc[0])
            .reset_index(name="x_drift")
        )
        rows.append(drift)

    drift = pd.concat(rows, ignore_index=True)
    print("Receiver x drift from snap to throw, split by the ORIGINAL playDirection.")
    print("If normalization worked, both rows look the same and both are positive.\n")
    print(
        drift.groupby("playDirection")["x_drift"]
        .agg(routes="size", mean="mean", median="median", pct_positive=lambda s: (s > 0).mean())
        .round(3)
        .to_string()
    )


def separation_feasibility(norm: pd.DataFrame, pff: pd.DataFrame, players: pd.DataFrame) -> None:
    header("8. SEPARATION AT THE THROW — FEASIBILITY ON ONE GAME")

    game_id = int(norm["gameId"].iloc[0])
    roles = pff.loc[pff["gameId"].eq(game_id), ["gameId", "playId", "nflId", "pff_role"]]
    throws = (
        norm.loc[norm["event"].eq("pass_forward")]
        .groupby("playId")["frameId"]
        .min()
        .rename("throw_frame")
        .reset_index()
    )
    frames = norm.merge(throws, on="playId").query("frameId == throw_frame")
    frames = frames.merge(roles, on=["gameId", "playId", "nflId"], how="inner").merge(
        players[["nflId", "officialPosition", "displayName"]], on="nflId", how="left"
    )

    recv = frames.loc[
        frames["pff_role"].eq("Pass Route") & frames["officialPosition"].isin(ROUTE_POSITIONS)
    ]
    defs = frames.loc[frames["pff_role"].eq("Coverage")]
    print(f"Plays with a pass_forward frame: {frames['playId'].nunique():,}")
    print(f"Receiver-frames: {len(recv):,}   Coverage-defender-frames: {len(defs):,}")

    out = []
    for play_id, rgrp in recv.groupby("playId"):
        dgrp = defs.loc[defs["playId"].eq(play_id)]
        if dgrp.empty:
            continue
        dist = np.hypot(
            rgrp["x"].to_numpy()[:, None] - dgrp["x"].to_numpy()[None, :],
            rgrp["y"].to_numpy()[:, None] - dgrp["y"].to_numpy()[None, :],
        )
        out.append(
            pd.DataFrame(
                {
                    "playId": play_id,
                    "displayName": rgrp["displayName"].to_numpy(),
                    "officialPosition": rgrp["officialPosition"].to_numpy(),
                    "separation": dist.min(axis=1),
                }
            )
        )
    sep = pd.concat(out, ignore_index=True)
    print(f"\nSeparation values computed: {len(sep):,}")
    print(sep["separation"].describe(percentiles=[0.05, 0.25, 0.5, 0.75, 0.95]).round(2).to_string())
    print("\nBy position:")
    print(
        sep.groupby("officialPosition")["separation"]
        .agg(n="size", mean="mean", median="median")
        .round(2)
        .to_string()
    )
    print(f"\nImplausible values (<0 or >40 yd): {((sep['separation'] < 0) | (sep['separation'] > 40)).sum()}")


def check_direction_signal(norm: pd.DataFrame, pff: pd.DataFrame, players: pd.DataFrame) -> None:
    header("9. DIRECTION SIGNAL — IS A BREAK DETECTABLE IN `dir`?")

    game_id = int(norm["gameId"].iloc[0])
    recv_ids = set(
        pff.loc[pff["gameId"].eq(game_id) & pff["pff_role"].eq("Pass Route"), "nflId"]
    ) & set(players.loc[players["officialPosition"].isin(ROUTE_POSITIONS), "nflId"])

    throws = norm.loc[norm["event"].eq("pass_forward")].groupby("playId")["frameId"].min()
    snaps = norm.loc[norm["event"].eq("ball_snap")].groupby("playId")["frameId"].min()
    keys = snaps.index.intersection(throws.index)

    trk = norm.loc[norm["nflId"].isin(recv_ids) & norm["playId"].isin(keys)].copy()
    trk["snap"] = trk["playId"].map(snaps)
    trk["throw"] = trk["playId"].map(throws)
    win = trk.loc[trk["frameId"].between(trk["snap"], trk["throw"])].sort_values(
        ["playId", "nflId", "frameId"]
    )

    print(f"Receiver-route windows on game {game_id}: "
          f"{win.groupby(['playId', 'nflId']).ngroups:,}")
    print(f"Frames per route window: "
          f"{win.groupby(['playId', 'nflId']).size().describe()[['mean', 'min', 'max']].round(1).to_dict()}")

    # Raw `dir` wraps at 0/360. np.unwrap on radians removes the artificial jumps.
    naive_jumps = 0
    unwrapped_jumps = 0
    best = None
    for (play_id, nfl_id), grp in win.groupby(["playId", "nflId"]):
        d = grp["dir"].to_numpy()
        if len(d) < 6 or np.isnan(d).any():
            continue
        naive = np.abs(np.diff(d))
        unwrapped = np.degrees(np.unwrap(np.radians(d)))
        true_step = np.abs(np.diff(unwrapped))
        naive_jumps += int((naive > 180).sum())
        unwrapped_jumps += int((true_step > 180).sum())

        # Largest heading change over a 5-frame (0.5 s) window.
        if len(unwrapped) >= 6:
            change = np.abs(unwrapped[5:] - unwrapped[:-5])
            i = int(np.argmax(change))
            cand = (float(change[i]), play_id, nfl_id, i, grp)
            if best is None or cand[0] > best[0]:
                best = cand

    print(f"\nFrame-to-frame |d dir| > 180 deg using RAW dir:       {naive_jumps:,} "
          f"(these are 0/360 wraparound artifacts, not real turns)")
    print(f"Frame-to-frame |d dir| > 180 deg after np.unwrap:     {unwrapped_jumps:,}")
    print("=> unwrap (or sin/cos) is required before measuring break angle.")

    change, play_id, nfl_id, i, grp = best
    name = players.loc[players["nflId"].eq(nfl_id), "displayName"].iloc[0]
    print(f"\nSharpest 0.5 s heading change on this game: {change:.1f} deg")
    print(f"  playId {play_id}, {name}")
    s_before = grp["s"].to_numpy()[i]
    s_after = grp["s"].to_numpy()[i + 5]
    print(f"  speed before break {s_before:.2f} yd/s -> after {s_after:.2f} yd/s "
          f"(retention {min(s_after / s_before, 1.0) if s_before else float('nan'):.2f})")
    print(f"  provisional sharpness = {change * min(s_after / s_before, 1.0):.1f}")


def check_speed_gate(pff: pd.DataFrame, players: pd.DataFrame) -> None:
    """`dir` is unreliable at low speed, which can fake a huge break.

    A near-stationary player can swing `dir` by 180 deg in one frame, and the
    speed-retention term rewards it (tiny speed before / larger after, capped
    at 1.0). This quantifies the problem and tests a minimum-speed gate.
    """
    header("9b. LOW-SPEED ARTIFACT IN THE BREAK DETECTOR")

    recv_ids = set(players.loc[players["officialPosition"].isin(ROUTE_POSITIONS), "nflId"])
    route_ids = set(pff.loc[pff["pff_role"].eq("Pass Route"), "nflId"]) & recv_ids

    gates = (0.0, 1.0, 2.0, 3.0, 4.0)
    rows = []
    for path in tracking_files()[:20]:
        norm = normalize_tracking(load_tracking(int(path.stem.split("_")[1])))
        snaps = norm.loc[norm["event"].eq("ball_snap")].groupby("playId")["frameId"].min()
        throws = norm.loc[norm["event"].eq("pass_forward")].groupby("playId")["frameId"].min()
        keys = snaps.index.intersection(throws.index)
        trk = norm.loc[norm["nflId"].isin(route_ids) & norm["playId"].isin(keys)].copy()
        trk["snap"] = trk["playId"].map(snaps)
        trk["throw"] = trk["playId"].map(throws)
        win = trk.loc[trk["frameId"].between(trk["snap"], trk["throw"])]

        for (play_id, nfl_id), grp in win.sort_values("frameId").groupby(["playId", "nflId"]):
            d = grp["dir"].to_numpy()
            s = grp["s"].to_numpy()
            if len(d) < 6 or np.isnan(d).any():
                continue
            unwrapped = np.degrees(np.unwrap(np.radians(d)))
            change = np.abs(unwrapped[5:] - unwrapped[:-5])
            s_before, s_after = s[:-5], s[5:]

            rec = {
                "gameId": int(grp["gameId"].iloc[0]),
                "playId": play_id,
                "nflId": nfl_id,
                "frames": len(d),
                "max_speed": float(s.max()),
            }
            # Pick the break as the largest change among frames that clear the
            # gate, rather than discarding routes whose unfiltered argmax is slow.
            for gate in gates:
                ok = s_before >= gate
                if not ok.any():
                    rec[f"angle_g{gate}"] = np.nan
                    rec[f"sbefore_g{gate}"] = np.nan
                    rec[f"sharp_g{gate}"] = np.nan
                    continue
                masked = np.where(ok, change, -np.inf)
                i = int(np.argmax(masked))
                ret = min(s_after[i] / s_before[i], 1.0) if s_before[i] > 0 else np.nan
                rec[f"angle_g{gate}"] = float(change[i])
                rec[f"sbefore_g{gate}"] = float(s_before[i])
                rec[f"sharp_g{gate}"] = float(change[i] * ret) if ret == ret else np.nan
            rows.append(rec)

    br = pd.DataFrame(rows)
    print(f"Route windows analysed (first 20 games): {len(br):,}")

    print("\nWith NO gate, the detector lands on the snap frame, where the receiver")
    print("is still set and `dir` is meaningless:")
    print(f"  median speed before the 'break': {br['sbefore_g0.0'].median():.2f} yd/s")
    print(f"  share of breaks found at < 1.0 yd/s: {(br['sbefore_g0.0'] < 1.0).mean():.1%}")
    print(f"  share of 'breaks' exceeding 120 deg: {(br['angle_g0.0'] > 120).mean():.1%}")
    print("\nUngated angle distribution (deg):")
    print(br["angle_g0.0"].describe(percentiles=[0.5, 0.9, 0.99]).round(1).to_string())

    print("\nApplying the gate INSIDE the search keeps nearly every route and")
    print("produces football-plausible break angles:")
    print(f"  {'gate (yd/s)':>12} {'routes kept':>12} {'%kept':>7} "
          f"{'med speed':>10} {'mean ang':>9} {'med ang':>8} {'p99 ang':>8} {'>120deg':>8}")
    for gate in gates:
        a = br[f"angle_g{gate}"]
        keep = a.notna()
        print(
            f"  {gate:>12.1f} {keep.sum():>12,} {keep.mean():>7.1%} "
            f"{br.loc[keep, f'sbefore_g{gate}'].median():>10.2f} "
            f"{a.mean():>9.1f} {a.median():>8.1f} {a.quantile(0.99):>8.1f} "
            f"{(a > 120).mean():>8.1%}"
        )

    print("\nBreak Sharpness (angle x speed retention) under each gate:")
    for gate in gates:
        col = br[f"sharp_g{gate}"]
        print(f"  gate {gate:>3.1f}: n={col.notna().sum():>5,}  mean={col.mean():>6.1f}  "
              f"median={col.median():>6.1f}  p99={col.quantile(0.99):>6.1f}")

    fig, axes = plt.subplots(1, 2, figsize=(12.5, 4.8))
    axes[0].scatter(br["sbefore_g0.0"], br["angle_g0.0"], s=4, alpha=0.18, color="#762a83")
    axes[0].axvline(3.0, color="crimson", ls="--", lw=1.4, label="3.0 yd/s gate")
    axes[0].axhline(120, color="0.3", ls=":", lw=1.2, label="120 deg (implausible)")
    axes[0].set_xlabel("speed before the detected break (yd/s)")
    axes[0].set_ylabel("largest 0.5 s heading change (deg)")
    axes[0].set_title("No gate: big 'breaks' cluster at a standstill")
    axes[0].legend(fontsize=8)

    bins = np.linspace(0, 310, 62)
    axes[1].hist(br["angle_g0.0"].dropna(), bins=bins, color="0.78", label="no gate")
    axes[1].hist(
        br["angle_g3.0"].dropna(), bins=bins, color="#1b7837", alpha=0.85,
        label="gate applied inside search (3.0 yd/s)",
    )
    axes[1].axvline(120, color="0.3", ls=":", lw=1.2)
    axes[1].set_xlabel("largest 0.5 s heading change (deg)")
    axes[1].set_ylabel("routes")
    axes[1].set_title("Gating removes the implausible tail")
    axes[1].legend(fontsize=8)

    fig.tight_layout()
    FIGURES.mkdir(parents=True, exist_ok=True)
    out = FIGURES / "eda_break_angle_vs_speed.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(f"\nsaved figures/{out.name}")
    print("=> gate the break search on pre-break speed; do not let `dir` noise at a")
    print("   standstill masquerade as a sharp cut.")


def check_final_sample(plays: pd.DataFrame, pff: pd.DataFrame, players: pd.DataFrame) -> pd.DataFrame:
    header("10. EXACT ANALYSIS SAMPLE — ALL 122 GAMES")

    rows = []
    for path in tracking_files():
        game_id = int(path.stem.split("_")[1])
        trk = pd.read_csv(path, usecols=["playId", "frameId", "event"])
        ev = trk.loc[trk["event"].isin(["ball_snap", "pass_forward"])]
        if ev.empty:
            continue
        pivot = ev.groupby(["playId", "event"])["frameId"].min().unstack()
        for col in ("ball_snap", "pass_forward"):
            if col not in pivot.columns:
                pivot[col] = np.nan
        pivot = pivot.reset_index().rename(
            columns={"ball_snap": "snap_frame", "pass_forward": "throw_frame"}
        )
        pivot["gameId"] = game_id
        rows.append(pivot[["gameId", "playId", "snap_frame", "throw_frame"]])

    windows = pd.concat(rows, ignore_index=True)
    print(f"Plays in tracking: {len(windows):,}  (plays.csv has {len(plays):,})")

    usable = windows.dropna(subset=["snap_frame", "throw_frame"]).copy()
    usable["window_frames"] = usable["throw_frame"] - usable["snap_frame"]
    usable = usable.loc[usable["window_frames"] > 0]
    print(f"Plays with snap AND pass_forward: {len(usable):,}  ({len(usable) / len(windows):.1%})")

    merged = usable.merge(plays, on=["gameId", "playId"], how="inner")
    man_zone = merged.loc[merged["pff_passCoverageType"].isin(["Man", "Zone"])]
    print(f"...and a Man/Zone label: {len(man_zone):,}  (drops {len(merged) - len(man_zone):,} 'Other')")
    print("\nPlay counts by coverage type in the final play set:")
    print(man_zone["pff_passCoverageType"].value_counts().to_string())

    routes = (
        pff.loc[pff["pff_role"].eq("Pass Route"), ["gameId", "playId", "nflId"]]
        .merge(players[["nflId", "officialPosition", "displayName"]], on="nflId", how="left")
        .query("officialPosition in @ROUTE_POSITIONS")
        .merge(
            man_zone[["gameId", "playId", "pff_passCoverageType", "window_frames"]],
            on=["gameId", "playId"],
            how="inner",
        )
    )
    print(f"\nROUTE-LEVEL OBSERVATIONS FOR THE MAIN CHART: {len(routes):,}")
    print("\nBy position x coverage:")
    print(
        pd.crosstab(
            routes["officialPosition"], routes["pff_passCoverageType"], margins=True
        ).to_string()
    )

    print("\nPlayers with >=30 routes in BOTH man and zone (leaderboard eligibility):")
    per = routes.groupby(["nflId", "displayName", "officialPosition", "pff_passCoverageType"]).size().unstack(fill_value=0)
    eligible = per.loc[(per.get("Man", 0) >= 30) & (per.get("Zone", 0) >= 30)]
    print(f"  {len(eligible)} players")
    print("\nPlayers with >=30 total routes, by position:")
    tot = routes.groupby(["nflId", "officialPosition"]).size().reset_index(name="n")
    print(tot.loc[tot["n"] >= 30, "officialPosition"].value_counts().to_string())

    print("\nCooper Kupp's route sample (the planned player callout):")
    kupp = routes.loc[routes["displayName"].eq("Cooper Kupp")]
    if kupp.empty:
        print("  NOT FOUND in the route set")
    else:
        print(kupp["pff_passCoverageType"].value_counts().to_string())

    OUTPUTS.mkdir(parents=True, exist_ok=True)
    out = OUTPUTS / "play_windows.csv"
    usable.to_csv(out, index=False)
    print(f"\nsaved {out.name} — snap/throw frame index reused by the main analysis")
    return usable


def main() -> None:
    games, players, plays, pff = load_games(), load_players(), load_plays(), load_pff()
    check_shapes(games, players, plays, pff)
    check_coverage(plays)
    check_roles(pff, players)
    check_events(plays)
    check_snap_to_throw(plays)
    norm = check_tracking_columns()
    plot_sample_play(norm, pff, players)
    check_normalization_across_games(pff, players)
    separation_feasibility(norm, pff, players)
    check_direction_signal(norm, pff, players)
    check_speed_gate(pff, players)
    check_final_sample(plays, pff, players)
    header("EDA COMPLETE")


if __name__ == "__main__":
    main()
