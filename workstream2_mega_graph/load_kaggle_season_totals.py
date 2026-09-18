"""
load_kaggle_season_totals.py

Aggregates the Kaggle "historical-nba-data-and-player-box-scores" dataset
(data/515/PlayerStatisticsExtended.csv) from per-game rows up to
per-player, per-season totals, in the schema build_2v3_plots.py already
expects (data/season_totals_all.csv). Replaces legacy/season_totals.py,
which pulled the same shape of data live from stats.nba.com -- before we
found stats.nba.com is unreachable from this network (see the project
decisions log for the full story).

Run this LOCALLY -- PlayerStatisticsExtended.csv is 450MB+, not something
to push through the Claude session. This script's OUTPUT
(data/season_totals_all.csv) is small (one row per player-season) and is
what gets shared back.

Bonus over the original stats.nba.com plan: PlayerStatisticsExtended.csv
carries a real per-game `possessions` figure (the NBA's own estimate, not
a formula reconstructed from FGA/OREB/TOV/FTA), so this uses the genuine
number, summed to the season level, instead of the
POSS_EST = FGA - OREB + TOV + 0.44*FTA approximation -- at zero extra
cost, since the file's already downloaded. Output column is POSS_ACTUAL,
not the old POSS_EST -- build_2v3_plots.py doesn't reference that column
name directly (it only reads the pre-computed EV100_FROM_2/3 columns), so
no changes needed there.

Note (2026-09-07): PlayerStatisticsExtended.csv's real `possessions` figure
only goes back to 1996-97 (734,869 Regular Season rows spanning 1996-97 ..
2025-26 on the first real run), not the full "1947-Today" the Kaggle
dataset advertises -- that claim holds for the base PlayerStatistics.csv,
not the Extended/advanced-stats file. This pushed the historic top-100
plot's start season from the originally-planned 1979-80 up to 1996-97 (see
decisions log) so every dot on every plot uses the same real POSS_ACTUAL
figure rather than mixing it with an estimated one.

Repo layout (as of the 2026-09-17 reorganization): this script lives in
workstream2_mega_graph/ alongside build_2v3_plots.py and
build_2v3_interactive.py. Paths below are resolved relative to the repo
root (via REPO_ROOT), not the current working directory, so this can be
run either as `python workstream2_mega_graph/load_kaggle_season_totals.py`
from the repo root or as `python load_kaggle_season_totals.py` from inside
workstream2_mega_graph/.

Usage:
    python load_kaggle_season_totals.py
"""

import logging
from pathlib import Path

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-7s  %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[1]

RAW_PATH = REPO_ROOT / "data" / "515" / "PlayerStatisticsExtended.csv"
OUT_PATH = REPO_ROOT / "data" / "season_totals_all.csv"

# Only pull the ~15 columns we need out of this ~100-column file -- keeps
# memory and load time down a lot on a 450MB+ CSV.
USECOLS = [
    "personId", "firstName", "lastName", "gameDateTimeEst", "gameType",
    "points", "fieldGoalsMade", "fieldGoalsAttempted",
    "threePointersMade", "threePointersAttempted",
    "freeThrowsMade", "freeThrowsAttempted",
    "reboundsOffensive", "turnovers", "possessions", "numMinutes",
]


def season_from_date(dt: pd.Series) -> pd.Series:
    """NBA season label from a game date: an Aug-Dec game belongs to the
    season starting that calendar year; a Jan-Jul game belongs to the
    season that started the PREVIOUS calendar year. August is a safe
    cutoff -- no NBA regular-season game has ever tipped off in August."""
    year = dt.dt.year
    month = dt.dt.month
    start_year = pd.Series(np.where(month >= 8, year, year - 1), index=dt.index)
    return start_year.astype(str) + "-" + (start_year + 1).astype(str).str[-2:]


def main():
    if not RAW_PATH.exists():
        raise SystemExit(f"{RAW_PATH} not found -- check the Kaggle dataset landed at data/515/")

    log.info("Reading %s (large file, may take a minute)...", RAW_PATH)
    # low_memory=False is required here, not just a performance tweak: pandas'
    # C parser has a known bug (raises IndexError inside _concatenate_chunks)
    # when usecols is combined with its default chunked low_memory dtype
    # inference and a dtype-mismatch warning fires on one of the ~85 columns
    # we're NOT reading. Forcing a single non-chunked read sidesteps it.
    df = pd.read_csv(RAW_PATH, usecols=USECOLS, parse_dates=["gameDateTimeEst"], low_memory=False)
    log.info("%d game-rows loaded", len(df))

    log.info("gameType breakdown before filtering:\n%s", df["gameType"].value_counts().to_string())

    reg_season_mask = df["gameType"].astype(str).str.strip().str.lower() == "regular season"
    df = df[reg_season_mask].copy()
    log.info("%d game-rows after filtering to Regular Season", len(df))
    if df.empty:
        raise SystemExit("No rows matched gameType == 'Regular Season' -- check the gameType "
                          "values printed above (case/spelling might differ) and adjust the filter.")

    df["SEASON"] = season_from_date(df["gameDateTimeEst"])
    df["PLAYER_NAME"] = (df["firstName"].fillna("") + " " + df["lastName"].fillna("")).str.strip()

    # Guard against dtype surprises: if any of these columns has even one
    # non-numeric value anywhere in the 450MB+ file (blank, "DNP", etc.),
    # pandas reads the WHOLE column as text, and a later .sum() silently
    # concatenates strings instead of adding numbers (this is exactly what
    # happened to numMinutes on the first real run -- caught via garbled
    # output like "29.038.043.0..." in the MIN column of the sample rows).
    # Coercing explicitly here makes every one of these columns safe to sum.
    numeric_cols = [
        "points", "fieldGoalsMade", "fieldGoalsAttempted",
        "threePointersMade", "threePointersAttempted",
        "freeThrowsMade", "freeThrowsAttempted",
        "reboundsOffensive", "turnovers", "possessions", "numMinutes",
    ]
    for col in numeric_cols:
        coerced = pd.to_numeric(df[col], errors="coerce")
        n_bad = int(coerced.isna().sum() - df[col].isna().sum())
        if n_bad > 0:
            log.warning("%s: %d value(s) could not be parsed as numeric -- treated as 0", col, n_bad)
        df[col] = coerced.fillna(0)

    agg = df.groupby(["SEASON", "personId"]).agg(
        PLAYER_NAME=("PLAYER_NAME", "first"),
        GP=("gameDateTimeEst", "count"),
        MIN=("numMinutes", "sum"),
        FGM=("fieldGoalsMade", "sum"),
        FGA=("fieldGoalsAttempted", "sum"),
        FG3M=("threePointersMade", "sum"),
        FG3A=("threePointersAttempted", "sum"),
        FTM=("freeThrowsMade", "sum"),
        FTA=("freeThrowsAttempted", "sum"),
        OREB=("reboundsOffensive", "sum"),
        TOV=("turnovers", "sum"),
        POSS_ACTUAL=("possessions", "sum"),
        PTS=("points", "sum"),
    ).reset_index().rename(columns={"personId": "PLAYER_ID"})

    agg["FG2M"] = agg["FGM"] - agg["FG3M"]
    agg["FG2A"] = agg["FGA"] - agg["FG3A"]
    agg["PTS_FROM_2"] = agg["FG2M"] * 2
    agg["PTS_FROM_3"] = agg["FG3M"] * 3
    agg["POSS_ACTUAL"] = agg["POSS_ACTUAL"].clip(lower=1)  # guard div-by-zero
    agg["EV100_FROM_2"] = agg["PTS_FROM_2"] / agg["POSS_ACTUAL"] * 100
    agg["EV100_FROM_3"] = agg["PTS_FROM_3"] / agg["POSS_ACTUAL"] * 100

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    agg.to_csv(OUT_PATH, index=False)
    log.info("Saved %s: %d player-seasons across %d season(s)", OUT_PATH, len(agg), agg["SEASON"].nunique())
    log.info("Season range: %s .. %s", agg["SEASON"].min(), agg["SEASON"].max())
    print("\nSample rows:")
    print(agg.sort_values("PTS", ascending=False).head(5).to_string(index=False))


if __name__ == "__main__":
    main()
