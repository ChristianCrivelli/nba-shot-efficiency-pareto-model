# Pareto 2v3 — Methodology & Decisions Notes

Working notes on scope and methodology decisions made so far, kept here so
they're easy to pull into the final write-up (the "Synthesis & Strategy"
report) later. Organized by topic, not by session.

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
   for efficient zones, red for sub-optimal.
2. **Mega Graph + The Efficiency Gap** — population-level scatter of
   EV-from-3 vs. EV-from-2, plus a script scoring how far a player's
   actual shot selection sits from their Pareto-optimal one.
3. **2 vs 3** — the core scatter: expected points per 100 possessions from
   2s (x-axis) vs. from 3s (y-axis), with an "iso-efficiency" line where
   the two are equal. Anyone above the line should, statistically, be
   shooting more 3s.
4. **Synthesis & Strategy** — translate the math into a coaching
   conclusion: the break-even FG% where mid-range stops being worth it
   vs. hunting 3s, and how the frontier has moved outward across eras.
   *(Not started yet.)*

Workstreams 1 and 3 were reviewed against the original Notion spec and
confirmed as already correctly scoped — no changes made there.

## Workstream 2 ("Mega Graph") — what we built

Two scatter plots, both plotting the same "2 vs 3" metric (expected
points per 100 possessions from 2s vs. from 3s) defined in workstream 3,
built from per-player **season box-score totals** rather than zone-level
shot-chart data. Zone-level shot location data is only reliably available
back to 1996-97; season box-score 2PT/3PT splits are available for the
entire span the 3-point line has existed (1979-80–present), which is what
this workstream actually needs.

**Plot 1 — current era.** 90 randomly-sampled players from the 2025-26
season (the most recently completed season) plus that season's 10 highest
total scorers, highlighted and labeled separately.
- Eligibility for the random sample: a minimum-attempts floor (200 field
  goal attempts on the season), so the sample isn't dominated by
  end-of-bench players with a handful of shots.
- "Highest scorers" ranked by total season points (not points per game).

**Plot 2 — historic.** The 100 highest-scoring individual player-seasons
of all time, pool starting at **1979-80** (the first season with a
3-point line), colored by season to visualize how the frontier has
drifted across eras.

Both plots carry the iso-efficiency line (EV-from-2 = EV-from-3) from the
"2 vs 3" spec.

### Possessions: estimated formula, not the NBA's official "Advanced" stat

Possessions are computed with the standard individual-possessions
estimate — `FGA − OREB + TOV + 0.44 × FTA` (the formula
Basketball-Reference uses for pace/usage) — rather than pulling the NBA
stats API's "Advanced" measure type, which carries an official POSS
number.

Rationale: the Advanced measure is a second API call per season on top of
the Base box-score call, and its historical coverage for older seasons is
less certain than the Base box score, which the NBA has for its entire
tracked history. Using the estimate keeps the pull to one call per season
and covers the full historic range consistently. This can be revisited
and swapped to the official NBA stat later if the estimate's accuracy
turns out to matter more than the extra API call.

### Data pipeline notes

- The data pull (`season_totals.py`) has to run on a machine with normal
  internet access — it can't run inside the Claude cloud sandbox, which
  doesn't have network access to stats.nba.com.
- Very old seasons can time out / hang against the NBA stats API rather
  than fail cleanly. The pipeline treats a season that fails after retries
  as skippable rather than fatal, so one stubborn season doesn't block the
  rest of a 47-season pull. Skipped seasons are logged for a targeted
  retry. Whether 1979-80-era seasons are reliably fetchable at all is
  still an open question pending more runs.

## Still open / not yet addressed

- **Workstream 4 (Synthesis & Strategy)** — the break-even FG% conclusion
  and the era-comparison write-up. Not started.
- **Risk definition for workstream 1** — points-per-shot variance vs.
  Bernoulli make-percentage variance give different Pareto frontiers;
  which one "risk" should mean hasn't been settled.
- **Restricted Area dominance** — in the zone-level frontier, layups/dunks
  trivially dominate every jump shot (highest EV, lowest variance), which
  is mathematically correct but not the live shot-selection decision a
  coach actually faces. Needs a deliberate call on how to handle this
  (e.g. excluding RA/backcourt for a "jump shots only" cut) rather than
  defaulting to it.
- **Zone granularity** — coarser zones are more sample-stable; finer zones
  read more like an actual shot chart but get noisy fast, especially
  per-player. Not yet decided.
