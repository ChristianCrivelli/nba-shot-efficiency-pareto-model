# Synthesis & Strategy — The 2-vs-3 Break-Even Frontier

This is the project's final write-up (workstream 4), pulling together the
break-even math from workstream 3, the population-level "Mega Graph" from
workstream 2, and the zone-level frontiers from workstream 1 into one
coaching-facing conclusion. Working notes and methodology detail for all
four workstreams live in `docs/report.md` and the project's decisions log;
this document states the findings, not how they were built.

## The core relationship

A 2-point shot made at rate `p2` and a 3-point shot made at rate `p3`
produce the same expected points when `2 * p2 = 3 * p3` — so the
break-even 2-point percentage, for any given 3-point percentage, is:

    FG2%_break-even = 1.5 × FG3%

Below that line, the average 2 is a worse bet than the average 3, points
per shot. Above it, the reverse. This single relationship is the thread
running through all three findings below.

## Finding 1 — The league didn't clear its own break-even line until 2021-22

Applying the formula above to actual league-wide shooting each season
(`data/breakeven_trend.csv`, `outputs/breakeven_trend.png`) turns up a
specific, countable answer to the spec's question of "how the frontier
has moved outward across eras" — and it's not the answer the modern
"Moreyball" narrative would suggest.

League-wide 3-point percentage has been remarkably flat for three
decades: 34-37% every single season from 1996-97 through 2025-26, no
real trend up or down. What moved was the volume (3-point attempts rose
from 21% of all field goal attempts in 1996-97 to 41-42% in the most
recent two seasons — teams shooting roughly twice as many 3s per shot
attempt as they did at the start of this dataset) and, more
consequentially for this specific question, league-wide 2-point
percentage: it climbed steadily, from 46-48% in the late 1990s to 54-55%
in 2022-2026, as the long, contested mid-range jumper — the shot the
"Moreyball" case was actually built against — was phased out of the
league's shot diet in favor of shots at the rim.

The two lines (actual 2PT%, and 1.5x that season's 3PT%) don't cross
until **2021-22**. For every season from 1996-97 through 2020-21, the
league's actual 2-point percentage sat *below* its own break-even line —
meaning that, in aggregate, the league would have scored more efficiently
by taking more 3s and fewer 2s for essentially this entire span, even as
teams were visibly moving in that direction the whole time. Only in the
last handful of seasons has 2-point shooting improved enough, in
aggregate, to actually justify the volume of 2s still being taken — and
even then narrowly and not every season (2023-24 dipped back 0.2 points
below the line).

The practical read: the league-wide shift toward 3-point volume over the
last 15 years wasn't chasing a moving break-even target — the target
barely moved, because 3-point percentage itself barely moved. It was
teams improving the *quality* of the 2s they still took (fewer long twos,
more rim shots) that eventually caught the break-even line up to where
3-point volume already was.

## Finding 2 — "Pareto-efficient" is not the same as "a good shot"

Workstream 1's zone-level frontiers (`outputs/zone_efficiency_full.png`,
`outputs/zone_efficiency_nonra.png`, `data/zone_efficiency.csv`) are the
natural zone-level counterpart to Finding 1, and they surface a
distinction worth stating plainly before drawing any coaching conclusion
from them: a zone is "Pareto-efficient" here because *no other zone
beats it on both expected points and risk at once* — not because it's a
high-value shot in absolute terms. A low-risk, low-return zone can sit on
the frontier perfectly legitimately, as the anchor at the safe end,
without being a shot anyone should actually want more of.

That distinction matters because it's exactly what shows up in the
non-RA ("jump shots only") cut: **mid-range zones are Pareto-efficient
20 of 30 times** across the league average and the 5 named players —
a surprisingly high rate, given the mid-range shot's reputation as the
analytics era's designated inefficient shot. They're on the frontier
because they're often the *lowest-risk* jump shot available, not because
they're a good bet — every mid-range zone in this dataset has a lower
expected value than the best available 3-point zone for that same player.
The frontier includes them at the low-risk end the same way it includes
Restricted Area at the low-risk end of the full frontier.

Two findings that *do* translate directly into "take more / fewer of
these":

- **"Above the Break 3" is never independently efficient once
  Restricted Area is in play** (0 of 18 full-frontier cells, across
  every entity) — it's always dominated by the rim. That's expected and
  not actionable on its own; it's the "duh, layups are good" restatement
  of the whole exercise.
- **Corner-3 is the strongest non-rim option, but only for shooters who
  can actually hit it.** League-wide, both corners sit on the non-RA
  frontier with the highest expected value of any jump-shot zone. Per
  player, though, this splits hard: Stephen Curry's corner-3 numbers
  (1.57-1.67 points/shot) are elite and clearly worth hunting; Giannis
  Antetokounmpo has essentially no corner-3 shot at all — 3 attempts
  (all missed) from the left corner and none from the right in this
  dataset — not "inefficient" so much as "not part of his shot profile,"
  which is itself the finding for a player like him (see below).

## Finding 3 — the 5 players split into distinct shapes, not one archetype

- **Stephen Curry** is the one player in this group whose non-rim shot
  selection actually matches the league-wide "shoot more 3s" prescription
  at the individual level: his right-corner 3 (1.67 EV) is his single
  most valuable efficient zone, clearing even his own Restricted Area
  number (1.28) — a rarity in this dataset, where the rim usually tops
  every player's frontier outright. His mid-range zones (0.59-0.68) sit
  well below both. For him, the break-even math and his actual shot
  profile are already aligned.
- **LeBron James and Luka Doncic** both still get real value at the rim
  (1.47 and 1.52 EV) but differ from there. LeBron's right-corner 3 (1.70
  EV, 23 attempts) actually *out-values* his own rim number and is
  Pareto-efficient on the full frontier right alongside it — a genuine
  "shoot more of this specific shot" finding. Luka's frontier is
  different: Restricted Area is his *only* full-frontier zone (every one
  of his 3-point zones is dominated once the rim is in the comparison),
  and only once Restricted Area is set aside does a best non-rim option
  emerge — right-side above-the-break 3 (1.24 EV). Two players who both
  finish well at the rim, but only one of them has a 3-point zone that
  stands on its own merits rather than just being "the best of what's
  left."
- **Nikola Jokic** is the outlier finding of the whole workstream: his
  non-restricted-area paint shots (73% FG, 1.47 EV) *beat* his own
  Restricted Area number (70%, 1.40) in this dataset — on only 15
  attempts, flagged accordingly, but a real enough gap to be worth a
  team's own larger-sample follow-up rather than dismissing outright.
- **Giannis Antetokounmpo** is the clearest "one shot, everything else is
  a discount" profile of the five: Restricted Area (1.55 EV) towers over
  every zone he takes, and none of them are close — not because he barely
  shoots 3s (his above-the-break attempts, 120 combined across three
  sub-zones, are real volume) but because none of them work: 0.74-0.95 EV,
  all dominated. His corners are where "near-empty" actually applies — 3
  attempts (all missed) from the left, none at all from the right in this
  dataset. There's no zone-efficiency argument for him to shoot more 3s
  from this data — the argument, if there is one, is about generating more
  shots at the rim in the first place, which is outside what a
  shot-selection frontier can speak to.

## Caveats — read before acting on any of the above

- **League averages mask individual variance.** Finding 1 is a
  league-wide aggregate; it says nothing about whether *your* team's or
  *your* player's 2-point shooting has cleared its own break-even line.
  The same math applies at any level — team, player, even single game —
  but the numbers above are the league only.
- **Season mismatch between workstreams.** Finding 1 uses 1996-97 through
  2025-26 season totals. Finding 2 and Finding 3 use 2023-24
  shot-location data only — the one season with real zone-level data in
  this repo. They're not describing the same year, and shouldn't be read
  as a single unified season snapshot.
- **No defense, shot clock, or shot-creation difficulty in this model.**
  A "Pareto-efficient" zone is efficient conditional on a shot from there
  actually being available on a given possession — it says nothing about
  how hard that shot is to generate, who's guarding it, or what happens
  to these numbers under playoff-level defensive attention.
- **Small samples are flagged, not fixed.** Several of the per-player
  zone numbers above (Jokic's paint-left, LeBron's several
  under-20-attempt zones, both of Giannis's corner-3 splits) rest on
  fewer than 20 shots for that player-zone combination in a single
  season. They're real numbers from real data, not typos or bugs, but
  they carry real sampling uncertainty that a full season-over-season
  average would substantially narrow.
- **The portfolio framing is a simplification.** Treating each shot as an
  independent, one-shot risk/return draw is the framing the whole project
  is built on (see `docs/project_description.md`), and it's a reasonable
  one for this kind of analysis — but it doesn't capture second-order
  effects like offensive rebounding rates by shot type, free-throw
  generation, or how a team's shot profile affects its opponent's
  transition opportunities.

## Where this leaves the four workstreams

| # | Workstream | Status |
|---|---|---|
| 1 | Efficient Zones + Players | Done — `outputs/zone_efficiency_full.png`, `outputs/zone_efficiency_nonra.png` |
| 2 | Mega Graph + Efficiency Gap | Done — `outputs/two_vs_three_2025_26*.png/html`, `outputs/two_vs_three_historic_top100*.png/html` |
| 3 | 2 vs 3 (core scatter + break-even relation) | Done — folded into workstreams 1, 2, and 4 |
| 4 | Synthesis & Strategy | Done — this document |

All four are now built. `docs/report.md` remains the working methodology
notes; the project decisions log has the full session-by-session history
of what was tried, what changed, and why.
