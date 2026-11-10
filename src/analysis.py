"""Does a sharp cut beat man coverage? The fair man-vs-zone comparison.

Reads outputs/route_metrics.csv (from src.metrics) and answers the question on
`sep_gain`, the space a cut creates on the defender nearest at its start.

A raw comparison is unfair: sharper cuts tend to happen later in the route and
start with the defender closer, and both of those change how much space opens
up regardless of the cut. So we compare like with like by adjusting each route
for four things we hold fixed:

    sep_before     how close the defender was when the cut started
    break_time_s   when in the route the cut happened (s after the snap)
    route_depth    yards past the line of scrimmage at the throw
    time_to_throw  how long the play lasted

Outputs:
    outputs/coverage_effect.csv     adjusted space gained, by position x cut angle x coverage
    outputs/regression_summary.csv  the model behind the headline, per position
    outputs/leaderboard.csv         per player: shiftiness and space gained vs man / zone

    python -m src.analysis
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.paths import OUTPUTS

METRICS_FILE = OUTPUTS / "route_metrics.csv"
EFFECT_FILE = OUTPUTS / "coverage_effect.csv"
REGRESSION_FILE = OUTPUTS / "regression_summary.csv"
LEADERBOARD_FILE = OUTPUTS / "leaderboard.csv"

# Leaderboard eligibility: enough routes overall, and enough against man for
# the man number to mean something.
MIN_ROUTES = 50
MIN_MAN_ROUTES = 20

POSITIONS = ("WR", "TE", "RB")
CONTROLS = ["sep_before", "break_time_s", "route_depth", "time_to_throw"]

# Cut-angle bins in degrees: coaches read degrees more easily than a score.
# 60°+ is one bin: split further, TE/RB bins fall below 30 routes.
ANGLE_EDGES = [0, 15, 30, 60, 360]
ANGLE_LABELS = ["<15°", "15–30°", "30–60°", "60°+"]


def load_metrics() -> pd.DataFrame:
    df = pd.read_csv(METRICS_FILE)
    df = df.dropna(subset=["sep_gain", *CONTROLS])
    df["is_man"] = df["coverage"].eq("Man").astype(float)
    df["angle_bin"] = pd.cut(df["break_angle"], ANGLE_EDGES, labels=ANGLE_LABELS,
                             right=False)
    return df


# --------------------------------------------------------------------------- #
# Least squares with robust standard errors (no statsmodels dependency)
# --------------------------------------------------------------------------- #
def ols(y: np.ndarray, X: np.ndarray) -> tuple[np.ndarray, np.ndarray, float]:
    """OLS coefficients, HC1 robust standard errors, and R²."""
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    n, k = X.shape
    xtx_inv = np.linalg.inv(X.T @ X)
    meat = (X * resid[:, None] ** 2).T @ X
    cov = xtx_inv @ meat @ xtx_inv * n / (n - k)
    r2 = 1 - (resid ** 2).sum() / ((y - y.mean()) ** 2).sum()
    return beta, np.sqrt(np.diag(cov)), float(r2)


def zscore(s: pd.Series) -> pd.Series:
    return (s - s.mean()) / s.std()


# --------------------------------------------------------------------------- #
# 1. Adjusted space gained, binned by cut angle (feeds the main chart)
# --------------------------------------------------------------------------- #
def adjust_for_controls(df: pd.DataFrame) -> pd.Series:
    """Remove the part of sep_gain explained by the controls, per position.

    Coverage is deliberately NOT in this model, so the man-vs-zone gap is left
    intact in the adjusted values. The position mean is added back so the
    numbers stay in yards.
    """
    adjusted = pd.Series(np.nan, index=df.index)
    for _, grp in df.groupby("position"):
        X = np.column_stack([np.ones(len(grp)), grp[CONTROLS].to_numpy(float)])
        y = grp["sep_gain"].to_numpy(float)
        beta, *_ = np.linalg.lstsq(X, y, rcond=None)
        adjusted.loc[grp.index] = y - X @ beta + y.mean()
    return adjusted


def coverage_by_angle(df: pd.DataFrame) -> pd.DataFrame:
    out = (
        df.groupby(["position", "angle_bin", "coverage"], observed=True)["adj_gain"]
        .agg(mean="mean", sem="sem", routes="size")
        .reset_index()
    )
    out["ci95"] = 1.96 * out["sem"]
    out["position"] = pd.Categorical(out["position"], POSITIONS, ordered=True)
    return out.sort_values(["position", "angle_bin", "coverage"]).drop(columns="sem")


# --------------------------------------------------------------------------- #
# 2. The model behind the headline
# --------------------------------------------------------------------------- #
def coverage_model(df: pd.DataFrame) -> pd.DataFrame:
    """sep_gain ~ man + angle + speed kept + man x angle + man x speed kept + controls.

    Continuous terms are z-scored within position, so `man` reads as yards of
    space lost against man for an average cut, and `man_x_angle` says whether
    sharper cuts help MORE against man (the coaching belief: positive).
    """
    rows = []
    for pos in POSITIONS:
        g = df.loc[df["position"].eq(pos)].copy()
        g["angle"] = zscore(g["break_angle"])
        g["speed_kept"] = zscore(g["speed_retention"])
        g["man_x_angle"] = g["is_man"] * g["angle"]
        g["man_x_speed_kept"] = g["is_man"] * g["speed_kept"]
        for c in CONTROLS:
            g[c] = zscore(g[c])

        terms = ["is_man", "angle", "speed_kept", "man_x_angle", "man_x_speed_kept", *CONTROLS]
        X = np.column_stack([np.ones(len(g)), g[terms].to_numpy(float)])
        beta, se, r2 = ols(g["sep_gain"].to_numpy(float), X)
        for name, b, s in zip(["intercept", *terms], beta, se):
            rows.append({"position": pos, "term": name, "coef_yd": b, "se": s,
                         "t": b / s, "routes": len(g), "r2": r2})
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- #
# 3. Player leaderboard: who is shiftiest, and does it pay off against man?
# --------------------------------------------------------------------------- #
def leaderboard(df: pd.DataFrame) -> pd.DataFrame:
    """One row per eligible player, ranked by shiftiness within position.

    shiftiness = mean Break Sharpness over all routes. Space gained uses the
    adjusted values, so players are compared on equal footing.
    """
    by_cov = (
        df.pivot_table(index="nflId", columns="coverage", values="adj_gain",
                       aggfunc=["mean", "size"])
    )
    by_cov.columns = [f"{'gain' if a == 'mean' else 'routes'}_{b.lower()}"
                      for a, b in by_cov.columns]

    players = (
        df.groupby(["nflId", "displayName", "position"])
        .agg(routes=("sharpness", "size"),
             shiftiness=("sharpness", "mean"),
             avg_cut_angle=("break_angle", "mean"),
             real_cut_rate=("break_angle", lambda a: (a >= 30).mean()))
        .reset_index()
        .join(by_cov, on="nflId")
    )
    players = players.loc[players["routes"].ge(MIN_ROUTES)
                          & players["routes_man"].ge(MIN_MAN_ROUTES)].copy()
    players["man_minus_zone"] = players["gain_man"] - players["gain_zone"]
    players["shiftiness_rank"] = (
        players.groupby("position")["shiftiness"].rank(ascending=False, method="min")
        .astype(int)
    )
    players["position"] = pd.Categorical(players["position"], POSITIONS, ordered=True)
    cols = ["position", "shiftiness_rank", "displayName", "nflId", "routes",
            "routes_man", "routes_zone", "shiftiness", "avg_cut_angle",
            "real_cut_rate", "gain_man", "gain_zone", "man_minus_zone"]
    return players.sort_values(["position", "shiftiness_rank"])[cols]


def main() -> None:
    df = load_metrics()
    df["adj_gain"] = adjust_for_controls(df)

    effect = coverage_by_angle(df)
    effect.to_csv(EFFECT_FILE, index=False, float_format="%.4f")
    model = coverage_model(df)
    model.to_csv(REGRESSION_FILE, index=False, float_format="%.4f")
    board = leaderboard(df)
    board.to_csv(LEADERBOARD_FILE, index=False, float_format="%.3f")

    print(f"Routes: {len(df):,}")
    print("\nAdjusted space gained (yd) by cut angle, Man vs Zone:")
    wide = effect.pivot_table(index=["position", "angle_bin"], columns="coverage",
                              values="mean", observed=True)
    wide["man_minus_zone"] = wide["Man"] - wide["Zone"]
    print(wide.round(2).to_string())

    print("\nModel terms that answer the question (yards; t in brackets):")
    key = model.loc[model["term"].isin(["is_man", "man_x_angle", "angle", "speed_kept"])]
    print(key.pivot(index="term", columns="position", values="coef_yd")
          .reindex(columns=list(POSITIONS)).round(3).to_string())
    print(key.pivot(index="term", columns="position", values="t")
          .reindex(columns=list(POSITIONS)).round(1).to_string())

    wr = model.loc[model["position"].eq("WR")].set_index("term")
    print(f"\nHEADLINE (WR): against man, a cut gains {wr.loc['is_man', 'coef_yd']:+.2f} yd "
          f"vs zone (t={wr.loc['is_man', 't']:.1f}); sharper cuts help more vs man? "
          f"man_x_angle = {wr.loc['man_x_angle', 'coef_yd']:+.3f} (t={wr.loc['man_x_angle', 't']:.1f})")
    print(f"\nLeaderboard: {len(board)} players "
          f"(>= {MIN_ROUTES} routes, >= {MIN_MAN_ROUTES} vs man)")
    for pos in POSITIONS:
        top = board.loc[board["position"].eq(pos)].head(5)
        print(f"\n  Shiftiest {pos}:")
        print(top[["shiftiness_rank", "displayName", "routes", "shiftiness",
                   "gain_man", "gain_zone"]].round(2).to_string(index=False))
    pos_board = board.loc[board["position"].eq("WR")]
    rho = pos_board["shiftiness"].rank().corr(pos_board["gain_man"].rank())
    print(f"\n  WR: rank correlation, shiftiness vs space gained vs man = {rho:+.2f}")

    print(f"\nsaved {EFFECT_FILE.relative_to(OUTPUTS.parent)}, "
          f"{REGRESSION_FILE.relative_to(OUTPUTS.parent)}, "
          f"{LEADERBOARD_FILE.relative_to(OUTPUTS.parent)}")


if __name__ == "__main__":
    main()
