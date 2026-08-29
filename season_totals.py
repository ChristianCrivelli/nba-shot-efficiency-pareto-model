"""
season_totals.py

Pulls per-player, per-season regular-season box score totals from the NBA
stats API for every season from 1979-80 (the first season with the
3-point line) through the most recent completed season (2025-26 by
default).

IMPORTANT: run this on a machine with normal internet access. The cloud
sandbox that built this script cannot reach stats.nba.com (its outbound
network is allowlisted to package registries only), so the pull has to
happen locally -- e.g. on this computer, from this repo folder.

For each season, pulls one "Base" / "Totals" call to leaguedashplayerstats
(PTS, FGM, FGA, FG3M, FG3A, FTA, OREB, TOV, GP, MIN per player) and derives:

    FG2M, FG2A              -- 2-point makes/attempts (FGM/FGA minus the 3s)
    PTS_FROM_2, PTS_FROM_3
    POSS_EST                -- estimated possessions, standard formula:
                                FGA - OREB + TOV + 0.44 * FTA
                                (this is an ESTIMATE, not the NBA's own
                                "Advanced" POSS stat -- see note below)
    EV100_FROM_2, EV100_FROM_3   -- points per 100 estimated possessions
                                     from 2s and 3s respectively

Why an estimated-possessions formula instead of the NBA's own "Advanced"
POSS stat: the Advanced measure type is a second API call per season, and
its historical coverage for very old seasons is less certain than the Base
box score, which the NBA has for its entire tracked history. The formula
above is the standard individual-possessions estimate (used e.g. by
Basketball-Reference for pace/usage calculations). If you'd rather use the
NBA's own Advanced POSS number where it's available, that's a one-line
swap -- flag it and we'll add it.

Saves one CSV per season to data/season_totals/{season}.csv and a combined
data/season_totals_all.csv with a SEASON column, so a later run only
needs to (re-)pull seasons that are missing or that you explicitly ask
for with --start/--end.

Usage:
    pip install requests pandas
    python season_totals.py                          # all seasons 1979-80..2025-26
    python season_totals.py --start 2023-24 --end 2025-26   # subset, e.g. to test first
    python season_totals.py --start 2025-26 --end 2025-26   # just the current-plot season
"""

import argparse
import logging
import time
from pathlib import Path

import pandas as pd
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-7s  %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

DATA_DIR = Path("data/season_totals")
COMBINED_PATH = Path("data/season_totals_all.csv")
REQUEST_DELAY = 1.5  # seconds between calls -- be polite to stats.nba.com
MAX_RETRIES = 4

NBA_STATS_URL = "https://stats.nba.com/stats/leaguedashplayerstats"
HEADERS = {
    "Host": "stats.nba.com",
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "x-nba-stats-origin": "stats",
    "x-nba-stats-token": "true",
    "Connection": "keep-alive",
    "Referer": "https://www.nba.com/",
    "Origin": "https://www.nba.com",
}

BASE_PARAMS = {
    "College": "", "Conference": "", "Country": "", "DateFrom": "", "DateTo": "",
    "Division": "", "DraftPick": "", "DraftYear": "", "GameScope": "",
    "GameSegment": "", "Height": "", "ISTRound": "", "LastNGames": 0,
    "LeagueID": "00", "Location": "", "MeasureType": "Base", "Month": 0,
    "OpponentTeamID": 0, "Outcome": "", "PORound": 0, "PaceAdjust": "N",
    "PerMode": "Totals", "Period": 0, "PlayerExperience": "", "PlayerPosition": "",
    "PlusMinus": "N", "Rank": "N", "SeasonSegment": "", "SeasonType": "Regular Season",
    "ShotClockRange": "", "StarterBench": "", "TeamID": 0, "TwoWay": 0,
    "VsConference": "", "VsDivision": "", "Weight": "",
}


def season_list(start: str, end: str) -> list[str]:
    """e.g. season_list('1979-80', '2025-26') -> ['1979-80', '1980-81', ..., '2025-26']"""
    start_year = int(start[:4])
    end_year = int(end[:4])
    return [f"{y}-{str(y + 1)[-2:]}" for y in range(start_year, end_year + 1)]


def fetch_season(season: str) -> pd.DataFrame:
    params = dict(BASE_PARAMS, Season=season)
    last_err = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(NBA_STATS_URL, headers=HEADERS, params=params, timeout=30)
            resp.raise_for_status()
            payload = resp.json()
            result_set = payload["resultSets"][0]
            df = pd.DataFrame(result_set["rowSet"], columns=result_set["headers"])
            return df
        except Exception as e:  # noqa: BLE001 -- want to retry on anything transient
            last_err = e
            log.warning("  season %s attempt %d/%d failed: %s", season, attempt, MAX_RETRIES, e)
            time.sleep(REQUEST_DELAY * attempt)
    raise RuntimeError(f"Failed to fetch {season} after {MAX_RETRIES} attempts") from last_err


def derive_columns(df: pd.DataFrame, season: str) -> pd.DataFrame:
    df = df.copy()
    df["SEASON"] = season

    keep = ["SEASON", "PLAYER_ID", "PLAYER_NAME", "TEAM_ABBREVIATION", "GP", "MIN",
            "FGM", "FGA", "FG3M", "FG3A", "FTA", "OREB", "TOV", "PTS"]
    df = df[[c for c in keep if c in df.columns]]

    df["FG2M"] = df["FGM"] - df["FG3M"]
    df["FG2A"] = df["FGA"] - df["FG3A"]
    df["PTS_FROM_2"] = df["FG2M"] * 2
    df["PTS_FROM_3"] = df["FG3M"] * 3

    # Standard individual possessions estimate (see module docstring).
    df["POSS_EST"] = df["FGA"] - df["OREB"] + df["TOV"] + 0.44 * df["FTA"]
    df["POSS_EST"] = df["POSS_EST"].clip(lower=1)  # guard div-by-zero for 0-possession rows

    df["EV100_FROM_2"] = df["PTS_FROM_2"] / df["POSS_EST"] * 100
    df["EV100_FROM_3"] = df["PTS_FROM_3"] / df["POSS_EST"] * 100

    return df


def main():
    parser = argparse.ArgumentParser(description="Pull per-player season totals for the 2v3 project.")
    parser.add_argument("--start", default="1979-80", help="first season, e.g. 1979-80")
    parser.add_argument("--end", default="2025-26", help="last season, e.g. 2025-26")
    parser.add_argument("--force", action="store_true", help="re-pull seasons even if a cached CSV already exists")
    args = parser.parse_args()

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    seasons = season_list(args.start, args.end)
    log.info("Pulling %d season(s): %s .. %s", len(seasons), seasons[0], seasons[-1])

    all_frames = []
    for i, season in enumerate(seasons, 1):
        out_path = DATA_DIR / f"{season}.csv"
        if out_path.exists() and not args.force:
            log.info("[%d/%d] %s already cached, loading from disk", i, len(seasons), season)
            frame = pd.read_csv(out_path)
        else:
            log.info("[%d/%d] Fetching %s from stats.nba.com...", i, len(seasons), season)
            raw = fetch_season(season)
            frame = derive_columns(raw, season)
            frame.to_csv(out_path, index=False)
            log.info("  -> %d players, saved to %s", len(frame), out_path)
            time.sleep(REQUEST_DELAY)
        all_frames.append(frame)

    combined = pd.concat(all_frames, ignore_index=True)
    combined.to_csv(COMBINED_PATH, index=False)
    log.info("Saved combined file: %s (%d rows across %d seasons)", COMBINED_PATH, len(combined), len(seasons))


if __name__ == "__main__":
    main()
