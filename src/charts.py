"""Figures for the README.

  1. sharpness_vs_separation.png - space gained by a cut, Man vs Zone, by cut angle
  2. shiftiness_vs_man.png       - who is shiftiest, and does it pay off vs man?
  3. top_plays.png               - two real cuts: one vs man, one vs zone

Reads outputs/coverage_effect.csv, outputs/leaderboard.csv and
outputs/route_metrics.csv (from src.metrics / src.analysis).

    python -m src.charts
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.metrics import BREAK_FRAMES
from src.paths import (
    FIGURES,
    OUTPUTS,
    load_pff,
    load_plays,
    load_tracking,
    normalize_tracking,
)

EFFECT_FILE = OUTPUTS / "coverage_effect.csv"
LEADERBOARD_FILE = OUTPUTS / "leaderboard.csv"
METRICS_FILE = OUTPUTS / "route_metrics.csv"
MAIN_CHART = FIGURES / "sharpness_vs_separation.png"
SCATTER_CHART = FIGURES / "shiftiness_vs_man.png"
PLAYS_CHART = FIGURES / "top_plays.png"

# Two real plays, chosen from route_metrics.csv: a sharp, fast WR cut that
# started within 4 yd of the defender (src/analysis has the leaderboard).
#   vs Man : biggest-name example of a sharp cut that still LOST space
#   vs Zone: a top-5 shiftiest WR whose sharp cut GAINED space and was caught
TOP_PLAYS = [
    {"gameId": 2021100313, "playId": 3417, "player": "Chris Godwin"},
    {"gameId": 2021100308, "playId": 2550, "player": "DeVonta Smith"},
]
# Labeled on the scatter: the five shiftiest WRs, the best and worst vs man,
# and familiar names (Kupp is the callout).
SCATTER_LABELS = [
    "Sterling Shepard", "Cole Beasley", "Laviska Shenault", "DeVonta Smith",
    "Kadarius Toney", "Dyami Brown", "Gabe Davis", "Davante Adams",
    "Justin Jefferson", "Stefon Diggs", "Tyreek Hill",
]
CALLOUT = "Cooper Kupp"

POSITIONS = ("WR", "TE", "RB")
POSITION_NAMES = {"WR": "Wide receivers", "TE": "Tight ends", "RB": "Running backs"}

# Colors: categorical slots 1-2 of the validated reference palette.
# Man (the coverage the claim is about) gets the warmer, more prominent hue.
COLORS = {"Man": "#eb6834", "Zone": "#2a78d6"}
SURFACE = "#fcfcfb"
TEXT = "#0b0b0b"
TEXT_2 = "#52514e"
GRID = "#e4e3df"


def main_chart(effect: pd.DataFrame) -> None:
    angle_order = list(dict.fromkeys(effect["angle_bin"]))  # file is pre-sorted
    x = range(len(angle_order))

    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10})
    fig, axes = plt.subplots(1, 3, figsize=(12, 4.6), sharey=True, facecolor=SURFACE)

    for ax, pos in zip(axes, POSITIONS):
        ax.set_facecolor(SURFACE)
        ax.axhline(0, color=TEXT_2, lw=0.8, zorder=1)
        sub = effect.loc[effect["position"].eq(pos)]
        for cov in ("Zone", "Man"):
            s = sub.loc[sub["coverage"].eq(cov)].set_index("angle_bin").reindex(angle_order)
            ax.fill_between(x, s["mean"] - s["ci95"], s["mean"] + s["ci95"],
                            color=COLORS[cov], alpha=0.14, lw=0, zorder=2)
            ax.plot(x, s["mean"], color=COLORS[cov], lw=2, marker="o", ms=7,
                    markeredgecolor=SURFACE, markeredgewidth=1.5, zorder=3, label=cov)
            if pos == "WR":  # direct labels once; the legend covers the rest
                ax.annotate(cov, (x[-1], s["mean"].iloc[-1]), xytext=(8, 0),
                            textcoords="offset points", va="center",
                            color=TEXT, fontsize=10, fontweight="bold")

        n = int(sub["routes"].sum())
        ax.set_title(f"{POSITION_NAMES[pos]}  ·  {n:,} routes", color=TEXT,
                     fontsize=11, loc="left")
        ax.set_xticks(list(x), angle_order, color=TEXT_2)
        ax.set_xlabel("cut angle (sharpest change of direction in 0.5 s)", color=TEXT_2,
                      fontsize=9)
        ax.set_xlim(-0.3, len(angle_order) - 0.4)
        ax.grid(axis="y", color=GRID, lw=0.8, zorder=0)
        ax.tick_params(colors=TEXT_2, length=0)
        for side in ("top", "right", "left"):
            ax.spines[side].set_visible(False)
        ax.spines["bottom"].set_color(GRID)

    axes[0].set_ylabel("space gained on the defender during the cut (yd)", color=TEXT_2,
                       fontsize=9)
    axes[0].legend(loc="lower left", frameon=False, fontsize=9, labelcolor=TEXT)

    fig.suptitle("Sharp cuts don't beat man coverage", x=0.012, ha="left",
                 fontsize=16, fontweight="bold", color=TEXT, y=0.995)
    fig.text(0.012, 0.905,
             "Against man (orange), receivers gain less space than against zone (blue) "
             "on almost every kind of cut, and sharper cuts don't close the gap.",
             fontsize=10.5, color=TEXT_2)
    fig.text(0.012, 0.01,
             "Space gained = distance to the defender nearest at the start of the cut, "
             "0.5 s later minus at the start. Adjusted for starting gap, cut timing, "
             "route depth and time to throw. Bands = 95% CI.\n"
             "Data: NFL Big Data Bowl tracking, 2021 Weeks 1–8. Man/zone labels: PFF.",
             fontsize=8, color=TEXT_2, va="bottom")

    fig.tight_layout(rect=(0, 0.07, 1, 0.89))
    FIGURES.mkdir(parents=True, exist_ok=True)
    fig.savefig(MAIN_CHART, dpi=160, facecolor=SURFACE)
    plt.close(fig)
    print(f"saved {MAIN_CHART.relative_to(OUTPUTS.parent)}")


def style_axes(ax: plt.Axes) -> None:
    ax.set_facecolor(SURFACE)
    ax.tick_params(colors=TEXT_2, length=0)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)


# --------------------------------------------------------------------------- #
# 2. Shiftiness vs space gained against man (WR leaderboard as a picture)
# --------------------------------------------------------------------------- #
def shiftiness_chart(board: pd.DataFrame) -> None:
    wr = board.loc[board["position"].eq("WR")].copy()
    mx, my = wr["shiftiness"].median(), wr["gain_man"].median()
    rho = wr["shiftiness"].rank().corr(wr["gain_man"].rank())

    fig, ax = plt.subplots(figsize=(10, 6.4), facecolor=SURFACE)
    style_axes(ax)
    ax.axvline(mx, color=GRID, lw=1, zorder=1)
    ax.axhline(my, color=GRID, lw=1, zorder=1)

    labeled = wr["displayName"].isin(SCATTER_LABELS)
    callout = wr["displayName"].eq(CALLOUT)
    rest = ~labeled & ~callout
    ax.scatter(wr.loc[rest, "shiftiness"], wr.loc[rest, "gain_man"], s=34,
               color=COLORS["Zone"], alpha=0.35, lw=0, zorder=2)
    ax.scatter(wr.loc[labeled, "shiftiness"], wr.loc[labeled, "gain_man"], s=52,
               color=COLORS["Zone"], edgecolor=SURFACE, lw=1.2, zorder=3)
    ax.scatter(wr.loc[callout, "shiftiness"], wr.loc[callout, "gain_man"], s=90,
               color=COLORS["Man"], edgecolor=SURFACE, lw=1.5, zorder=4)

    for _, r in wr.loc[labeled | callout].iterrows():
        is_callout = r["displayName"] == CALLOUT
        dx = -8 if r["shiftiness"] > wr["shiftiness"].quantile(0.9) else 8
        ax.annotate(r["displayName"], (r["shiftiness"], r["gain_man"]),
                    xytext=(dx, 0), textcoords="offset points", va="center",
                    ha="right" if dx < 0 else "left",
                    fontsize=10 if is_callout else 8.5,
                    fontweight="bold" if is_callout else "normal",
                    color=TEXT if is_callout else TEXT_2, zorder=5)

    # Quadrant names, in the corners.
    pad = dict(fontsize=9, color=TEXT_2, style="italic", alpha=0.9)
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    ax.text(x1, y1, "Shifty AND wins vs man", ha="right", va="top", **pad)
    ax.text(x0, y1, "Not shifty, still wins vs man", ha="left", va="top", **pad)
    ax.text(x1, y0, "Shifty, but loses vs man", ha="right", va="bottom", **pad)
    ax.text(x0, y0, "Neither", ha="left", va="bottom", **pad)

    ax.set_xlabel("shiftiness → (average Break Sharpness per route)", color=TEXT_2)
    ax.set_ylabel("space gained per cut vs man coverage (yd) →", color=TEXT_2)
    fig.suptitle("Being shifty doesn't decide who wins against man", x=0.012,
                 ha="left", fontsize=15, fontweight="bold", color=TEXT, y=0.985)
    fig.text(0.012, 0.915,
             f"Each dot is a wide receiver ({len(wr)} with 50+ routes, 20+ vs man). "
             f"The shiftiest receivers land on both sides of the line (rank correlation "
             f"{rho:+.2f}).",
             fontsize=10, color=TEXT_2)
    fig.text(0.012, 0.012,
             "Space gained is adjusted for starting gap, cut timing, route depth and "
             "time to throw. Lines = medians.",
             fontsize=8, color=TEXT_2)
    fig.tight_layout(rect=(0, 0.03, 1, 0.9))
    fig.savefig(SCATTER_CHART, dpi=160, facecolor=SURFACE)
    plt.close(fig)
    print(f"saved {SCATTER_CHART.relative_to(OUTPUTS.parent)}")


# --------------------------------------------------------------------------- #
# 3. Two real plays: the receiver's path and the defender on him
# --------------------------------------------------------------------------- #
def play_paths(game_id: int, play_id: int, player: str, metrics: pd.DataFrame,
               pff: pd.DataFrame) -> dict:
    """Receiver and nearest-at-break Coverage defender paths, snap to throw."""
    m = metrics.loc[metrics["gameId"].eq(game_id) & metrics["playId"].eq(play_id)
                    & metrics["displayName"].eq(player)].iloc[0]
    trk = normalize_tracking(load_tracking(game_id))
    trk = trk.loc[trk["playId"].eq(play_id)]
    snap = trk.loc[trk["event"].eq("ball_snap"), "frameId"].min()
    throw = trk.loc[trk["event"].eq("pass_forward"), "frameId"].min()
    trk = trk.loc[trk["frameId"].between(snap, throw)]

    rec = trk.loc[trk["nflId"].eq(m["nflId"])].sort_values("frameId")
    f0 = snap + int(round(m["break_time_s"] * 10))
    f1 = f0 + BREAK_FRAMES

    cover_ids = pff.loc[pff["gameId"].eq(game_id) & pff["playId"].eq(play_id)
                        & pff["pff_role"].eq("Coverage"), "nflId"]
    at0 = trk.loc[trk["frameId"].eq(f0) & trk["nflId"].isin(cover_ids)]
    r0 = rec.loc[rec["frameId"].eq(f0)].iloc[0]
    k = np.hypot(at0["x"] - r0["x"], at0["y"] - r0["y"]).idxmin()
    defn = trk.loc[trk["nflId"].eq(at0.loc[k, "nflId"])].sort_values("frameId")
    ball = trk.loc[trk["team"].eq("football") & trk["frameId"].eq(snap)].iloc[0]
    return {"m": m, "rec": rec, "def": defn, "f0": f0, "f1": f1, "los": ball["x"]}


def plays_chart(metrics: pd.DataFrame) -> None:
    pff = load_pff()
    plays = load_plays().set_index(["gameId", "playId"])

    fig, axes = plt.subplots(1, 2, figsize=(12, 5.6), facecolor=SURFACE)
    for ax, spec in zip(axes, TOP_PLAYS):
        p = play_paths(spec["gameId"], spec["playId"], spec["player"], metrics, pff)
        m, rec, dfn = p["m"], p["rec"], p["def"]
        cov_color = COLORS[m["coverage"]]

        ax.set_facecolor(SURFACE)
        ax.axvline(p["los"], color=GRID, lw=2, zorder=1)
        ax.plot(dfn["x"], dfn["y"], color=TEXT_2, lw=2, ls=(0, (4, 3)), zorder=2,
                label="nearest defender")
        ax.plot(rec["x"], rec["y"], color=cov_color, lw=2.5, zorder=3,
                label=f"{m['displayName']}")
        for path, c in ((rec, cov_color), (dfn, TEXT_2)):
            ax.scatter(path["x"].iloc[0], path["y"].iloc[0], s=40, color=SURFACE,
                       edgecolor=c, lw=1.5, zorder=4)
            ax.scatter(path["x"].iloc[-1], path["y"].iloc[-1], s=40, color=c, zorder=4)

        # Gap at the start and end of the cut.
        for f, tag in ((p["f0"], "start"), (p["f1"], "end")):
            r = rec.loc[rec["frameId"].eq(f)].iloc[0]
            d = dfn.loc[dfn["frameId"].eq(f)].iloc[0]
            gap = np.hypot(r["x"] - d["x"], r["y"] - d["y"])
            ax.plot([r["x"], d["x"]], [r["y"], d["y"]], color=TEXT, lw=1, ls=":", zorder=3)
            ax.scatter(r["x"], r["y"], s=60, color=cov_color, edgecolor=SURFACE,
                       lw=1.2, zorder=5)
            below = tag == "start"
            ax.annotate(f"cut {tag}: {gap:.1f} yd",
                        ((r["x"] + d["x"]) / 2, min(r["y"], d["y"]) if below else max(r["y"], d["y"])),
                        xytext=(0, -14 if below else 14), textcoords="offset points",
                        fontsize=9, fontweight="bold", color=TEXT, ha="center",
                        va="top" if below else "bottom", zorder=6,
                        bbox=dict(boxstyle="round,pad=0.2", fc=SURFACE, ec="none", alpha=0.85))

        # Crop to the paths; keep yards square so angles look true.
        xs = pd.concat([rec["x"], dfn["x"], pd.Series([p["los"]])])
        ys = pd.concat([rec["y"], dfn["y"]])
        half_h = max((ys.max() - ys.min()) / 2 + 2.5, 5)
        cy = (ys.max() + ys.min()) / 2
        ax.set_xlim(xs.min() - 1.5, xs.max() + 2.5)
        ax.set_ylim(cy - half_h, cy + half_h)
        ax.set_aspect("equal")
        ax.set_xticks([])
        ax.set_yticks([])
        for side in ax.spines.values():
            side.set_color(GRID)

        gain = m["sep_gain"]
        verdict = "lost" if gain < 0 else "gained"
        ax.set_title(
            f"vs {m['coverage'].upper()} ({m['coverage_scheme']}): "
            f"{m['displayName']} {verdict} {abs(gain):.1f} yd",
            loc="left", fontsize=11.5, fontweight="bold", color=TEXT)
        desc = plays.loc[(spec["gameId"], spec["playId"]), "playDescription"]
        ax.text(0.0, -0.04,
                f"{m['break_angle']:.0f}° cut at {m['speed_before']:.1f} yd/s → "
                f"{m['speed_after']:.1f} yd/s\n{desc}",
                transform=ax.transAxes, fontsize=8, color=TEXT_2, va="top", wrap=True)
        ax.legend(loc="upper left", frameon=False, fontsize=8.5, labelcolor=TEXT)
        ax.text(p["los"], ax.get_ylim()[0], " line of scrimmage", rotation=90,
                fontsize=7.5, color=TEXT_2, va="bottom", ha="right")

    fig.suptitle("Same kind of cut, different result", x=0.012, ha="left",
                 fontsize=15, fontweight="bold", color=TEXT, y=0.99)
    fig.text(0.012, 0.915,
             "Snap to throw; offense moves left → right. Dotted lines: gap to the "
             "defender at the start and end of the cut (0.5 s). ○ = snap, ● = throw.",
             fontsize=9.5, color=TEXT_2)
    fig.tight_layout(rect=(0, 0.04, 1, 0.9))
    fig.savefig(PLAYS_CHART, dpi=160, facecolor=SURFACE)
    plt.close(fig)
    print(f"saved {PLAYS_CHART.relative_to(OUTPUTS.parent)}")


def main() -> None:
    main_chart(pd.read_csv(EFFECT_FILE))
    shiftiness_chart(pd.read_csv(LEADERBOARD_FILE))
    plays_chart(pd.read_csv(METRICS_FILE))


if __name__ == "__main__":
    main()
