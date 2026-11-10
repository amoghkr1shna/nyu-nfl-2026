"""Main chart: space gained by a cut, Man vs Zone, by cut angle.

Reads outputs/coverage_effect.csv (from src.analysis) and saves
outputs/figures/sharpness_vs_separation.png, the image the README embeds.

    python -m src.charts
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd

from src.paths import FIGURES, OUTPUTS

EFFECT_FILE = OUTPUTS / "coverage_effect.csv"
MAIN_CHART = FIGURES / "sharpness_vs_separation.png"

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


def main() -> None:
    effect = pd.read_csv(EFFECT_FILE)
    main_chart(effect)


if __name__ == "__main__":
    main()
