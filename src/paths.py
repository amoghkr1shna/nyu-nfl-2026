"""Shared paths and loaders for the Break Sharpness analysis."""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "nfl-big-data-bowl-regional-event-data" / "data"
TRACKING = DATA / "tracking"
OUTPUTS = ROOT / "outputs"
FIGURES = OUTPUTS / "figures"

# Tracking field is 120 x 53.3 yards (includes both 10-yard endzones).
FIELD_LENGTH = 120.0
FIELD_WIDTH = 53.3

ROUTE_POSITIONS = ("WR", "TE", "RB")


def load_games() -> pd.DataFrame:
    return pd.read_csv(DATA / "games.csv")


def load_players() -> pd.DataFrame:
    return pd.read_csv(DATA / "players.csv")


def load_plays() -> pd.DataFrame:
    return pd.read_csv(DATA / "plays.csv")


def load_pff() -> pd.DataFrame:
    return pd.read_csv(DATA / "pffScoutingData.csv")


def tracking_files() -> list[Path]:
    return sorted(TRACKING.glob("tracking_*.csv"))


def load_tracking(game_id: int) -> pd.DataFrame:
    return pd.read_csv(TRACKING / f"tracking_{game_id}.csv")


def normalize_tracking(df: pd.DataFrame) -> pd.DataFrame:
    """Flip every play so the offense always moves toward +x.

    Mirrors x and y, then rotates the angular columns (`o`, `dir`) by 180
    degrees for plays running left. Angles stay in [0, 360).
    """
    df = df.copy()
    left = df["playDirection"].eq("left")
    df.loc[left, "x"] = FIELD_LENGTH - df.loc[left, "x"]
    df.loc[left, "y"] = FIELD_WIDTH - df.loc[left, "y"]
    for col in ("o", "dir"):
        if col in df.columns:
            df.loc[left, col] = (df.loc[left, col] + 180.0) % 360.0
    return df
