# Pareto 2v3 — Methodology & Decisions Notes

Working notes on scope and methodology decisions made so far, kept here so
they're easy to pull into the final write-up (the "Synthesis & Strategy"
report) later. Organized by topic, not by session. (For the full
session-by-session history — including things that were tried and
abandoned, like the stats.nba.com pull below — see the project's
decisions log.)

## Project scope

The Efficient Frontier of Sports (Pareto 2v3) treats the basketball court
as a portfolio of "assets": each shot zone (or each shot-selection choice)
has a return — expected points — and a risk — the variance of that
outcome. The project finds the Pareto-efficient frontier of that
return/risk tradeoff, and translates it into a practical break-even
threshold between 2-point and 3-point shooting.

Four workstreams, per the project's Notion spec:

1. **Efficient Zones + Players** — which court zones are Pareto-efficient,
   for the league-average player and 5 favorite players. Heatmaps: gold
   for efficient zones, red for sub-optimal. **Done.**
2. **Mega Graph + The Efficiency Gap** — population-level scatter of
   EV-from-3 vs. EV-from-2, plus a script scoring how far a player's
   actual shot selection sits from their Pareto-optimal one. **Done.**
3. **2 vs 3** — the core scatter: expected points per 100 possessions from
   2s (x-axis) vs. from 3s (y-axis), with an "iso-efficiency" line where
   the two are equal. Anyone above the line should, statistically, be
   shooting more 3s.
4. **Synthesis & Strategy** — translate the math into a coaching
   conclusion: the break-even FG% where mid-range stops being worth it
   vs. hunting 3s, and how the frontier has moved outward across eras.
   **Done.**

Workstreams 1 and 3 were reviewed against the original Notion spec and
confirmed as already correctly scoped — no changes made there.

## Workstream 2 ("Mega Graph") — what we built

Two scatter plots, both plotting the same "2 vs 3" metric (expected
points per 100 possessions from 2s vs. from 3s) defined in workstream 3,
built from per-player **season box-score totals** rather than zone-level
shot-chart data. Zone-level shot location data is only reliably available
back to 1996-97; season box-score 2PT/3PT splits go back much further —
though as it turned out, our actual possessions data only goes back to
1996-97 too, for a different reason (see below).

**Plot 1 — current era.** 90 randomly-sampled players from the 2025-26
season (the most recently completed season) plus that season's 10 highest
total scorers, highlighted and labeled separately.
- Eligibility for the random sample: a minimum-attempts floor (200 field
  goal attempts on the season), so the sample isn't dominated by
  end-of-bench players with a handful of shots.
- "Highest scorers" ranked by total season points (not points per game).

**Plot 2 — historic.** The 100 highest-scoring individual player-seasons
of all time, pool starting at **1996-97** (originally planned as 1979-80,
the first season with a 3-point line — shrunk once the data source's real
possessions coverage turned out not to reach that far back; see below),
colored by season to visualize how the frontier has drifted across eras.

Both plots carry the iso-efficiency line (EV-from-2 = EV-from-3) from the
"2 vs 3" spec. Each exists in two forms: a static PNG, and a self-contained
interactive HTML page where every player is a small hoverable headshot
(name/season/points/EV/shooting splits on hover), with a plain colored dot
as the fallback for anyone without a usable real photo.

### Data source: a static Kaggle dataset, not a live stats.nba.com pull

The original plan was to pull season box scores live from the NBA's own
stats API (`stats.nba.com/stats/leaguedashplayerstats`). That turned out to
be a dead end: the `stats.nba.com` subdomain specifically is unreachable
from this project's network (a geo-blocking issue, confirmed by testing
directly in a browser — the rest of nba.com loads fine). `season_totals.py`
is the script that implements that abandoned approach; it's kept in the
repo as a record of what was tried, but **it is not part of the current
pipeline** — don't run it expecting current data.

The actual data source is a static, pre-downloaded Kaggle dataset:
`eoinamoore/historical-nba-data-and-player-box-scores` ("NBA Dataset: Box
Scores and Stats, 1947-Today"), confirmed current through the actual
2025-26 NBA Finals. Basketball-Reference was considered and ruled out as a
live-scraping alternative — they deployed active CDN-level bot filtering
in 2022 specifically to block scrapers, on top of a ToS prohibition. Both
of the dataset's large per-game CSVs live under `data/515/` and are too
large to hand to an AI coding assistant's cloud sandbox directly (389MB
and 453MB) — the aggregation step below has to run locally.

### Possessions: the NBA's own per-game figure, not a reconstructed estimate

Originally planned as an estimate — `POSS_EST = FGA − OREB + TOV + 0.44 ×
FTA` (the formula Basketball-Reference uses for pace/usage) — since that
was expected to be the only option available. It turned out the Kaggle
dataset's `PlayerStatisticsExtended.csv` file carries a genuine per-game
`possessions` column (the NBA's own figure), so the pipeline uses that
directly instead, summed to the season level as `POSS_ACTUAL`. Better
number, no extra cost, since the file's already downloaded either way.

The catch: this real `possessions` figure only exists in the "Extended"
(advanced-stats) file, and that file's coverage only reaches back to
1996-97 — the NBA's advanced-stats era has always started there, on
stats.nba.com too, it's not specific to this dataset. That's the actual
reason the historic plot's pool starts at 1996-97 rather than 1979-80: it
was a deliberate trade of historical depth for having every single point
on every plot use the same real, measured number rather than mixing in an
estimate for the older seasons. If a full-depth version back to 1979-80
is wanted later, the base `PlayerStatistics.csv` file (not Extended)
likely covers that range, at the cost of falling back to the `POSS_EST`
formula for pre-1996-97 seasons specifically.

### Headshots

Player headshot markers come from the NBA's own CDN
(`cdn.nba.com/headshots/nba/latest/1040x760/{player_id}.png`). Two
non-obvious things worth knowing if this is ever touched again:

- The CDN does **not** 404 for an invalid player ID — it returns a
  generic gray silhouette placeholder with an HTTP 200, same as a real
  photo would. `looks_like_placeholder()` (in `player_headshots.py`)
  detects this by compositing the image onto white first (see next point)
  and checking for near-zero color saturation plus a very low unique-color
  count — both together, so a genuinely black-and-white archival photo
  (low saturation, but hundreds of real gray shades) doesn't get
  misflagged.
- These CDN images carry real alpha transparency (~60% of each image).
  Naively converting to RGB drops that to solid black instead of leaving
  it see-through — would have stamped every plot marker with an ugly
  black halo. Fixed by keeping the source alpha channel throughout.

Validated against real players: LeBron James and Kareem Abdul-Jabbar both
returned genuine photos; a deliberately bogus player ID correctly came
back as a detected placeholder. On the real historic-plot population
(1996-97+), 96 of 100 player-seasons got real photos; the current-era
population got 100/100.

### Data pipeline (current)

Two-stage, both stages run **locally** (not in a cloud sandbox — no
network access to cdn.nba.com/kaggle, and the raw files are too large to
move):

1. `load_kaggle_season_totals.py` — reads the ~450MB
   `data/515/PlayerStatisticsExtended.csv`, filters to
   `gameType == "Regular Season"`, aggregates per-game rows to one row per
   player-season, and writes the small `data/season_totals_all.csv` (the
   only output that needs to travel anywhere).
2. `build_2v3_plots.py` (static PNGs) and/or `build_2v3_interactive.py`
   (interactive HTML, needs live internet to fetch headshots) — both read
   `data/season_totals_all.csv` and produce the actual deliverables.

`season_totals.py` (the abandoned stats.nba.com puller) and its
`POSS_EST` formula are **not** part of this pipeline — see above.

## Workstream 1 ("Efficient Zones + Players") — what we built

Zone-level Pareto-efficiency heatmaps: for the league average and 5 named
players (LeBron James, Luka Doncic, Stephen Curry, Nikola Jokic, Giannis
Antetokounmpo — chosen by the user), which of the ~14 real NBA shot-chart
zones give the best expected points per shot for their risk, per the
original spec's gold-efficient / red-sub-optimal heatmap framing.

### Data source: 2023-24 shot-location log, not the Kaggle season totals

Unlike workstream 2, this workstream needs actual shot **location** data
(which zone each shot came from), not just season-level 2PT/3PT splits —
the Kaggle pipeline built for workstream 2 doesn't carry that. The repo
already had `data/shot_log_2023_24.csv`, a real per-shot log with the
standard stats.nba.com zone taxonomy (`SHOT_ZONE_BASIC` x
`SHOT_ZONE_AREA`, ~14 populated zones), 218,700 shots, 568 players — used
as-is rather than re-sourcing new data. **This means workstream 1 runs on
the 2023-24 season while workstream 2 runs on 2025-26** — a real, known
mismatch between the two workstreams, not an oversight; flagged here so
nobody assumes both are looking at the same year. If a matching shot log
for a more recent season becomes available, `zone_efficiency.py`'s
`SHOT_LOG_PATH` is the only thing that needs to change.

### Risk: points-per-shot variance, computed per-shot (not per-zone)

Risk means variance of the actual **points** outcome (0 on a miss,
the shot's value on a make), not the raw make/miss (Bernoulli) variance —
these disagree on which shots are "risky." A 3-pointer at 35% and a
2-pointer at 50% have nearly identical raw make-miss variance (~0.23 vs.
0.25), but the 3-pointer's *point* variance is nearly double (2.05 vs.
1.00), because missing forfeits a bigger potential payoff. Points-per-shot
variance is the one that's actually consistent with treating expected
points as the "return" being optimized.

Computed per-shot rather than assuming one fixed point value per zone,
because the real data has a genuine wrinkle: 76,240 of 218,700 shots sit
in zones ("Above the Break 3", "Mid-Range") where a small minority of
shots (as few as 1-9 per zone) have a different point value than the
zone's typical one — boundary cases where a shot's zone (assigned by
location) and its actual value (determined by exact foot position at the
moment of the shot) disagree right at a zone edge. Using each shot's own
`made x value` and building EV/variance from that (`E[X]`, `E[X^2] -
E[X]^2`) handles this correctly with no need to drop or reclassify
anything.

### Restricted Area: shown both ways, not defaulted

Including the Restricted Area, layups/dunks trivially dominate every
jump shot (highest EV, lowest risk) — mathematically correct, but not the
live decision a coach faces once a shot at the rim isn't available. Rather
than picking one framing, both are built:
- **Full frontier** (`zone_efficiency_full.png`) — every zone. RA (and
  usually one or two others) shows gold; almost everything else is red.
- **Non-RA cut** (`zone_efficiency_nonra.png`) — Restricted Area excluded
  (grayed on the diagram, not scored), isolating the real jump-shot
  tradeoff among mid-range, corner-3, and above-the-break-3 zones.

Desperation heaves are excluded from **both** frontiers entirely (not
merely shown as "dominated"): a ~2%-make-rate, near-halfcourt shot has
near-zero point variance, so left in naively it shows up as trivially
"Pareto-efficient" — a statistical artifact, not a shot-selection insight,
since a buzzer heave isn't a selectable option in a normal possession.
Identified by `SHOT_ZONE_AREA == "Back Court(BC)"` (not by
`SHOT_ZONE_BASIC`) since the data provider buckets a handful of these
heaves under "Above the Break 3" rather than "Backcourt" by location —
both share the "Back Court(BC)" area tag, which is what actually marks
them as heaves.

### Zone granularity: ~14 zones (SHOT_ZONE_BASIC x SHOT_ZONE_AREA)

The finer split (e.g. "Mid-Range, Left Side" vs. "Mid-Range, Right Side
Center") rather than the coarser 7-zone SHOT_ZONE_BASIC alone — reads more
like an actual shot chart. The cost: some zones are thin per-player (a
single player can have under 20 shots in a given zone-side combination all
season) — flagged with a cross-hatch and an attempt count on the heatmap
rather than hidden, so a thin sample is visible, not silently trusted the
same as a stable one.

### Zone shapes on the heatmap are analytic approximations, not exact geometry

The half-court diagram (`court_viz.py`) draws each zone as a wedge or
rectangle sized from standard, real-data-cross-checked constants
(restricted-area radius 4ft, lane depth 14ft, 3PT arc at 23.75ft with the
22ft corner line) — not the shot-chart provider's exact pixel-level
boundary logic. Every shot is still correctly assigned to its real zone
upstream in the data; this only affects where a zone's boundary is *drawn*
on the picture, not which numbers go with which zone.

Output: `data/zone_efficiency.csv` (the full per-entity, per-zone numbers
table — FG%, EV, risk variance, sample size, both frontier flags — never
gated behind the heatmap image) plus the two PNGs above. Pipeline:
`zone_efficiency.py` (computes the table) then `build_zone_heatmaps.py`
(renders the heatmaps); both run locally or in a sandbox, no network
needed — `data/shot_log_2023_24.csv` was already in the repo.

## Workstream 4 ("Synthesis & Strategy") — what we built

The coaching-facing write-up, `synthesis_and_strategy.md`, pulling
together workstreams 1-3 into three findings rather than introducing new
methodology of its own:

- **Era trend** (`build_breakeven_trend.py` → `breakeven_trend.png`,
  `data/breakeven_trend.csv`): league-wide FG2% vs. the break-even FG2%
  implied by that season's league-wide FG3% (`1.5 x FG3_PCT`, the same
  relation as workstream 3), summed from `data/season_totals_all.csv`
  (the same file workstream 2 uses) across all 47 seasons back to
  1996-97. The finding: league FG3% has been flat (34-37%) for three
  decades — the break-even target barely moved — and league FG2% didn't
  clear its own break-even line until **2021-22**, driven by better shot
  quality at the rim rather than a moving target.
- **Zone-level nuance**: reusing workstream 1's `data/zone_efficiency.csv`
  to make the point that "Pareto-efficient" isn't the same as "a good
  shot" — mid-range zones are efficient 20 of 30 times on the non-RA cut
  (as the low-risk anchor, not because they're a good bet), while
  Above-the-Break-3 is never efficient once the rim is in play (0 of 18).
  Corner-3 is the strongest non-rim zone league-wide, but splits hard by
  player.
- **Per-player findings**: each of the 5 named players gets a short
  paragraph pulled from the same CSV — every specific number in it
  (EV, FG%, attempt counts) was checked directly against the CSV before
  publishing, not written from memory of an earlier printed table. This
  caught two real errors during drafting (a wrong claim about which of
  Curry's zones was his lowest-value efficient one, and a wrong claim
  that one of Luka's 3-point zones out-values his own Restricted Area)
  and one imprecise phrasing (Giannis's 3-point profile described as
  "near-empty" when he actually takes real above-the-break volume that's
  simply all inefficient — his corners are the part that's genuinely
  near-empty) — all fixed before delivery. See the decisions log for the
  session this was built in.

Caveats specific to this workstream (full list is in the document
itself): the era trend is a league average and says nothing about any
one team or player; it also uses a different season (1996-97 through
2025-26 season totals) than the zone-level findings (2023-24 shot log
only) — the season-mismatch caveat below applies here directly, not just
as a note for later.

## Still open / not yet addressed

- **Season mismatch** — workstream 1 runs on 2023-24 shot-location data,
  workstream 2 on 2025-26 season totals (see above). Not a blocker for
  either workstream individually, but worth resolving (e.g. sourcing a
  2025-26 shot log) before any write-up that directly compares numbers
  across the two.
- **Marker crowding** on workstream 2's interactive plots (dense headshot
  overlap) — cosmetic, not yet requested as a fix (see the decisions log).
