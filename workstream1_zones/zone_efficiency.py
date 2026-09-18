"""
zone_efficiency.py

Workstream 1 ("Efficient Zones + Players"): computes the zone-level
Pareto-efficient frontier -- which court zones give the best
expected-points-per-shot for the least risk -- for the league average and
for a handful of named players, from real shot-location data.

Data source: data/shot_log_2023_24.csv (2023-24 regular-season shot log,
one row per shot, with the standard stats.nba.com shot-chart zone taxonomy:
SHOT_ZONE_BASIC x SHOT_ZONE_AREA). This is a SEASON EARLIER than the
2025-26 season used elsewhere in the project (workstream 2's "current era"
plot) -- it's the shot-location file the repo already had on hand, and
zone-level shot-location data isn't part of the Kaggle season-totals
pipeline built for workstream 2. Flagged, not silently glossed over: if a
2025-26 (or newer) shot log becomes available, swap SHOT_LOG_PATH and
re-run -- nothing else in this module is season-specific.

Methodology (decided collaboratively -- see the project's decisions log
for the full discussion of each):

  - Risk = points-per-shot variance, not raw make/miss (Bernoulli)
    variance. For a shot worth `value` points made with probability p,
    the per-attempt point outcome is 0 (miss) or `value` (make), so
    Var(points) = E[points^2] - E[points]^2. This is computed directly
    from each shot's actual made-flag x actual value rather than assuming
    a single fixed value per zone (see next point), and reduces to the
    familiar p(1-p)*value^2 in the single-value case.

  - A small number of shots (76,240 of 218,700, concentrated in "Above
    the Break 3" and "Mid-Range") have a SHOT_VALUE that doesn't match
    the zone's typical value -- e.g. a handful of "Above the Break 3"
    zone shots (by location bucket) that were actually 2-point makes
    (foot on the line at the moment of the shot). These are boundary
    cases in the real data, not errors -- a shot's zone is assigned by
    location, but its point value is determined by exact foot position,
    and the two occasionally disagree right at a zone edge. The
    points-per-shot formula above handles this correctly without needing
    to drop or reclassify anything, since it uses each shot's own actual
    value rather than one nominal value per zone.

  - Zone granularity: SHOT_ZONE_BASIC x SHOT_ZONE_AREA (~14 populated
    zones), not the coarser SHOT_ZONE_BASIC alone (7 zones) -- reads more
    like an actual shot chart, at the cost of noisier per-player numbers
    in low-volume zones. Zones with fewer than LOW_SAMPLE_THRESHOLD
    attempts for a given entity are flagged (LOW_SAMPLE=True), not
    dropped -- shown with a caution flag rather than hidden.

  - Desperation heaves are EXCLUDED from both Pareto calculations
    entirely, not just hidden after the fact -- identified as every zone
    with SHOT_ZONE_AREA == "Back Court(BC)". That's two zone keys in the
    real data: SHOT_ZONE_BASIC == "Backcourt" (433 shots, ~2% league FG%)
    and, less obviously, 32 shots the data provider buckets under
    SHOT_ZONE_BASIC == "Above the Break 3" but which are still
    near-halfcourt heaves by shot distance -- both share the same
    "Back Court(BC)" area tag, which is what actually identifies them as
    heaves rather than the basic-zone label. Left in naively, zones like
    this show up as trivially "Pareto-efficient" purely because a
    low-make-rate zone has near-zero variance -- a statistical artifact,
    not a real shot-selection insight, since a heave at the buzzer isn't a
    selectable option in a normal offensive possession. They're still
    computed and kept in the raw per-zone stats table for completeness.

    NOTE (flagged 2026-09-16, not yet acted on): this same low-sample/
    near-zero-variance artifact can recur outside the heave zones too --
    e.g. a player's 0-for-3 zone has RISK_VAR=0 by construction, which can
    make it read as "Pareto-efficient" purely for lack of data to
    dominate it, not because it's a good shot. LOW_SAMPLE already flags
    these cells; see the comprehensive project report for specific
    examples if this needs a closer look.

  - Two frontiers are computed per entity, per the "show both" decision:
      EFF_FULL   -- Pareto-efficient among all zones except Backcourt.
                    Restricted Area / dunks-and-layups predictably
                    dominate here -- mathematically complete, but not the
                    live decision a coach faces once a shot at the rim
                    isn't available.
      EFF_NONRA  -- Pareto-efficient among all zones except Backcourt
                    AND Restricted Area -- isolates the actual jump-shot
                    tradeoff (mid-range vs. corner 3 vs. above-the-break
                    3) a coach cares about on most possessions.
    A zone excluded from a given frontier (Backcourt from both;
    Restricted Area from EFF_NONRA only) gets NaN there, not False --
    "not evaluated," distinct from "evaluated and dominated."

Entities: "League Average" (every shot in the log) plus 5 named players,
chosen by the user: LeBron James, Luka Doncic, Stephen Curry, Nikola
Jokic, Giannis Antetokounmpo -- all confirmed present in the 2023-24 log
with a real season's worth of attempts (1,269-1,652 shots each).

Output: data/zone_efficiency.csv, one row per (entity, zone) -- the full
underlying numbers table, not gated behind the heatmap visualization
(see build_zone_heatmaps.py, in this same folder).

Repo layout (as of the 2026-09-17 reorganization): this script lives in
workstream1_zones/ alongside court_viz.py and build_zone_heatmaps.py.
Paths below are resolved relative to the repo root (via REPO_ROOT), not
the current working directory, so this can be run either as
`python workstream1_zones/zone_efficiency.py` from the repo root or as
`python zone_efficiency.py` from inside workstream1_zones/ -- either way
it reads/writes the same repo-root-level data/ folder.

Usage:
    python zone_efficiency.py
"""

from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]

SHOT_LOG_PATH = REPO_ROOT / "data" / "shot_log_2023_24.csv"
OUT_PATH = REPO_ROOT / "data" / "zone_efficiency.csv"

LOW_SAMPLE_THRESHOLD = 20  # fewer attempts than this -> flagged, not dropped

PLAYERS = {
    2544: "LeBron James",
    1629029: "Luka Doncic",
    201939: "Stephen Curry",
    203999: "Nikola Jokic",
    203507: "Giannis Antetokounmpo",
}

# Additionally excluded from the "non-RA / jump shots only" frontier.
EXCLUDED_NONRA_ONLY = {"Restricted Area"}


def _is_heave(stats: pd.DataFrame) -> pd.Series:
    """Desperation heaves -- excluded from BOTH frontiers entirely (see module docstring).
    Identified by SHOT_ZONE_AREA, not SHOT_ZONE_BASIC: the data provider buckets a
    handful of near-halfcourt heaves under "Above the Break 3" rather than "Backcourt",
    but they all share the "Back Court(BC)" area tag."""
    return stats["SHOT_ZONE_AREA"] == "Back Court(BC)"


def compute_zone_stats(shots: pd.DataFrame) -> pd.DataFrame:
    """Per-(SHOT_ZONE_BASIC, SHOT_ZONE_AREA) attempts/makes/EV/risk for one entity's shots."""
    shots = shots.copy()
    shots["POINTS_EARNED"] = shots["SHOT_MADE_FLAG"] * shots["SHOT_VALUE"]

    g = shots.groupby(["SHOT_ZONE_BASIC", "SHOT_ZONE_AREA"])
    out = g.agg(
        N_ATTEMPTS=("SHOT_MADE_FLAG", "size"),
        N_MADE=("SHOT_MADE_FLAG", "sum"),
        POINTS=("POINTS_EARNED", "sum"),
        MEAN_SQ_POINTS=("POINTS_EARNED", lambda s: (s ** 2).mean()),
        TYPICAL_VALUE=("SHOT_VALUE", lambda s: s.mode().iloc[0]),
    ).reset_index()

    out["FG_PCT"] = out["N_MADE"] / out["N_ATTEMPTS"]
    out["EV"] = out["POINTS"] / out["N_ATTEMPTS"]
    out["RISK_VAR"] = out["MEAN_SQ_POINTS"] - out["EV"] ** 2
    out["LOW_SAMPLE"] = out["N_ATTEMPTS"] < LOW_SAMPLE_THRESHOLD
    return out.drop(columns=["POINTS", "MEAN_SQ_POINTS"])


def _pareto_efficient(ev: np.ndarray, risk: np.ndarray) -> np.ndarray:
    """True where no other index has EV>=this and RISK<=this with >=1 strict inequality."""
    n = len(ev)
    efficient = np.ones(n, dtype=bool)
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            if ev[j] >= ev[i] and risk[j] <= risk[i] and (ev[j] > ev[i] or risk[j] < risk[i]):
                efficient[i] = False
                break
    return efficient


def add_frontiers(stats: pd.DataFrame) -> pd.DataFrame:
    """Adds EFF_FULL and EFF_NONRA columns (bool where evaluated, NaN where excluded)."""
    stats = stats.copy()
    stats["EFF_FULL"] = pd.array([np.nan] * len(stats), dtype="object")
    stats["EFF_NONRA"] = pd.array([np.nan] * len(stats), dtype="object")

    full_mask = ~_is_heave(stats)
    if full_mask.any():
        sub = stats[full_mask]
        stats.loc[full_mask, "EFF_FULL"] = _pareto_efficient(sub["EV"].to_numpy(), sub["RISK_VAR"].to_numpy())

    nonra_mask = full_mask & ~stats["SHOT_ZONE_BASIC"].isin(EXCLUDED_NONRA_ONLY)
    if nonra_mask.any():
        sub = stats[nonra_mask]
        stats.loc[nonra_mask, "EFF_NONRA"] = _pareto_efficient(sub["EV"].to_numpy(), sub["RISK_VAR"].to_numpy())

    return stats


def build_zone_efficiency_table(shots: pd.DataFrame) -> pd.DataFrame:
    rows = []

    league = add_frontiers(compute_zone_stats(shots))
    league.insert(0, "ENTITY", "League Average")
    rows.append(league)

    for player_id, name in PLAYERS.items():
        player_shots = shots[shots["PLAYER_ID"] == player_id]
        if player_shots.empty:
            raise ValueError(f"No shots found for {name} (PLAYER_ID={player_id}) in {SHOT_LOG_PATH}")
        stats = add_frontiers(compute_zone_stats(player_shots))
        stats.insert(0, "ENTITY", name)
        rows.append(stats)

    return pd.concat(rows, ignore_index=True)


def main():
    if not SHOT_LOG_PATH.exists():
        raise SystemExit(f"{SHOT_LOG_PATH} not found.")

    shots = pd.read_csv(SHOT_LOG_PATH)
    result = build_zone_efficiency_table(shots)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(OUT_PATH, index=False)
    print(f"Saved: {OUT_PATH} ({len(result)} rows: "
          f"{result['ENTITY'].nunique()} entities x up to {result.groupby('ENTITY').size().max()} zones)")

    n_eff_full = int(result["EFF_FULL"].sum())
    n_eff_nonra = int(result["EFF_NONRA"].sum())
    print(f"Zones flagged Pareto-efficient: {n_eff_full} (full frontier), {n_eff_nonra} (non-RA cut)")
    n_low = int(result["LOW_SAMPLE"].sum())
    print(f"Entity-zone cells below the {LOW_SAMPLE_THRESHOLD}-attempt low-sample threshold: {n_low} / {len(result)}")


if __name__ == "__main__":
    main()
