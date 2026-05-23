import time
import logging
import pandas as pd
from pathlib import Path
from nba_api.stats.static import teams as nba_teams
from nba_api.stats.endpoints import ShotChartDetail

# ── configuration ────────────────────────────────────────────────────────────
SEASON          = "2023-24" # can I do the most recent season? Or all of them?
SEASON_TYPE     = "Regular Season"   # or "Playoffs" can I not do both?
OUTPUT_DIR      = Path("data")
OUTPUT_FILE     = OUTPUT_DIR / f"shot_log_{SEASON.replace('-','_')}.csv"
REQUEST_DELAY   = 1.5                # seconds between API calls (be polite)

# Pull all teams, or narrow to a subset for faster iteration:
#   TEAM_FILTER = ["BOS", "GSW", "LAL"]   ← abbreviation list
#   TEAM_FILTER = None                     ← all 30 teams
TEAM_FILTER: list[str] | None = None

# ── logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ── helpers ───────────────────────────────────────────────────────────────────

# ShotChartDetail returns 2/3 inside SHOT_TYPE field ("2PT Field Goal" / "3PT…")
# but the cleanest numeric flag comes from LOC_X & LOC_Y + zone name.
# We derive SHOT_VALUE from the official SHOT_TYPE column.
SHOT_VALUE_MAP = {
    "2PT Field Goal": 2,
    "3PT Field Goal": 3,
}

# Columns we care about for the optimisation model
TARGET_COLUMNS = [
    "GAME_ID",
    "GAME_EVENT_ID",
    "PLAYER_ID",
    "PLAYER_NAME",
    "TEAM_ID",
    "TEAM_NAME",
    "PERIOD",
    "MINUTES_REMAINING",
    "SECONDS_REMAINING",
    "EVENT_TYPE",         # "Made Shot" | "Missed Shot"
    "ACTION_TYPE",        # e.g. "Jump Shot", "Layup Shot"
    "SHOT_TYPE",          # "2PT Field Goal" | "3PT Field Goal"
    "SHOT_ZONE_BASIC",    # Mid-Range, Restricted Area, Corner 3, etc.
    "SHOT_ZONE_AREA",     # Left Side, Right Side, Center, Back Court
    "SHOT_ZONE_RANGE",    # < 8 ft, 8-16 ft, 16-24 ft, 24+ ft
    "SHOT_DISTANCE",      # feet from basket
    "LOC_X",              # court x coordinate (tenths of a foot)
    "LOC_Y",              # court y coordinate (tenths of a foot)
    "SHOT_MADE_FLAG",     # 1 = made, 0 = missed
]


def fetch_team_shots(team_id: int, team_abbr: str) -> pd.DataFrame:
    """
    Pull all shot attempts for *team_id* in the configured season.

    Returns a tidy DataFrame with TARGET_COLUMNS + SHOT_VALUE.
    Returns an empty DataFrame on failure (error is logged, not raised,
    so the outer loop keeps running for the other 29 teams).
    """
    log.info("Fetching  %-4s  (team_id=%d)", team_abbr, team_id)
    try:
        endpoint = ShotChartDetail(
            team_id=team_id,
            player_id=0,                       # 0 = all players on team
            season_nullable=SEASON,
            season_type_all_star=SEASON_TYPE,
            context_measure_simple="FGA",      # Field Goal Attempts
            timeout=30,
        )
        df = endpoint.get_data_frames()[0]
    except Exception as exc:
        log.error("  %-4s  request failed: %s", team_abbr, exc)
        return pd.DataFrame()

    if df.empty:
        log.warning("  %-4s  returned 0 rows", team_abbr)
        return df

    # ── keep only columns we need ────────────────────────────────────────────
    available = [c for c in TARGET_COLUMNS if c in df.columns]
    missing   = [c for c in TARGET_COLUMNS if c not in df.columns]
    if missing:
        log.warning("  %-4s  missing expected columns: %s", team_abbr, missing)
    df = df[available].copy()

    # ── derive SHOT_VALUE (2 or 3) ───────────────────────────────────────────
    df["SHOT_VALUE"] = df["SHOT_TYPE"].map(SHOT_VALUE_MAP)

    log.info("  %-4s  %d attempts pulled", team_abbr, len(df))
    return df


# ── main pipeline ─────────────────────────────────────────────────────────────

def run_pipeline() -> pd.DataFrame:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Get all 30 NBA teams
    all_teams = nba_teams.get_teams()
    if TEAM_FILTER:
        all_teams = [t for t in all_teams if t["abbreviation"] in TEAM_FILTER]
        log.info("Filtered to %d teams: %s", len(all_teams), TEAM_FILTER)
    else:
        log.info("Pulling all %d teams", len(all_teams))

    frames: list[pd.DataFrame] = []

    for i, team in enumerate(all_teams):
        df = fetch_team_shots(team["id"], team["abbreviation"])
        if not df.empty:
            frames.append(df)

        # Respect rate limits between calls (except after the last one)
        if i < len(all_teams) - 1:
            time.sleep(REQUEST_DELAY)

    if not frames:
        log.error("No data collected. Exiting.")
        return pd.DataFrame()

    combined = pd.concat(frames, ignore_index=True)

    # ── light cleaning ────────────────────────────────────────────────────────
    combined["LOC_X"] = pd.to_numeric(combined["LOC_X"], errors="coerce")
    combined["LOC_Y"] = pd.to_numeric(combined["LOC_Y"], errors="coerce")
    combined["SHOT_DISTANCE"] = pd.to_numeric(combined["SHOT_DISTANCE"], errors="coerce")
    combined["SHOT_MADE_FLAG"] = combined["SHOT_MADE_FLAG"].astype(int)

    # Drop the ~0.01 % of rows with no coordinates
    before = len(combined)
    combined.dropna(subset=["LOC_X", "LOC_Y", "SHOT_VALUE"], inplace=True)
    after = len(combined)
    if before != after:
        log.warning("Dropped %d rows with null coordinates/shot_value", before - after)

    combined.reset_index(drop=True, inplace=True)

    # ── save ──────────────────────────────────────────────────────────────────
    combined.to_csv(OUTPUT_FILE, index=False)
    log.info("Saved %d rows → %s", len(combined), OUTPUT_FILE)

    # ── quick summary ─────────────────────────────────────────────────────────
    print_summary(combined)
    return combined


def print_summary(df: pd.DataFrame) -> None:
    """Print a descriptive summary useful for validating the pull."""
    print("\n" + "="*60)
    print(f"  Shot Log Summary  |  {SEASON}  {SEASON_TYPE}")
    print("="*60)
    print(f"  Total attempts : {len(df):,}")
    print(f"  Made           : {df['SHOT_MADE_FLAG'].sum():,}  "
          f"({df['SHOT_MADE_FLAG'].mean():.1%})")
    print(f"  Players        : {df['PLAYER_NAME'].nunique():,}")
    print(f"  Teams          : {df['TEAM_NAME'].nunique():,}")
    print()
    print("  By shot value:")
    val_grp = (
        df.groupby("SHOT_VALUE")["SHOT_MADE_FLAG"]
        .agg(attempts="count", makes="sum")
        .assign(pct=lambda x: x["makes"] / x["attempts"])
    )
    print(val_grp.to_string())
    print()
    print("  By zone (SHOT_ZONE_BASIC):")
    zone_grp = (
        df.groupby("SHOT_ZONE_BASIC")
        .agg(
            attempts=("SHOT_MADE_FLAG", "count"),
            makes=("SHOT_MADE_FLAG", "sum"),
            avg_distance=("SHOT_DISTANCE", "mean"),
        )
        .assign(
            pct=lambda x: x["makes"] / x["attempts"],
            ev=lambda x: x["pct"] * x.index.map(
                df.groupby("SHOT_ZONE_BASIC")["SHOT_VALUE"].mean()
            ),
        )
        .sort_values("attempts", ascending=False)
    )
    print(zone_grp.round(3).to_string())
    print("="*60 + "\n")


# ── entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    shot_log = run_pipeline()