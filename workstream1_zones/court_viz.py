"""
court_viz.py

Shared half-court drawing helpers for the workstream-1 zone-efficiency
heatmaps (build_zone_heatmaps.py). Not a standalone script.

Zone shapes are analytic approximations (wedges for the angular zones,
rectangles for the paint/corners), in feet, with the hoop at (0, 0) and
the baseline at y = -5.25 -- the standard stats.nba.com shot-chart
convention. The constants below (restricted-area radius 4ft, lane width
16ft extending to 14ft from the hoop, 3PT arc at 23.75ft with the
corner straight line at 22ft out to y=8.95ft, half-court at y=41.75ft)
were cross-checked against the real shot_log_2023_24.csv's own LOC_X/
LOC_Y/SHOT_DISTANCE ranges per zone (e.g. "In The Paint (Non-RA)" tops
out at 13.8ft in the real data, matching the 14ft lane depth used here;
"Left/Right Corner 3" tops out at y=8.7ft, matching the 8.95ft corner-
to-arc transition computed from the 22ft/23.75ft geometry) -- they are
not exact official court blueprints, just close enough to read as a
real shot chart.

Each of the 7 SHOT_ZONE_BASIC regions is split into its real
SHOT_ZONE_AREA sub-zones by simple angle (for the two arc-shaped zones)
or x-position (for the paint) -- this doesn't perfectly reproduce the
provider's own boundary logic pixel-for-pixel, but every shot is
already correctly assigned to its real zone upstream in the data; this
module only decides where each zone's LABEL sits on the diagram, not
which shots belong to it.

Two zone keys are intentionally never drawn as their own shape here:
Backcourt/"Back Court(BC)" and the ~32-shot "Above the Break 3"/
"Back Court(BC)" anomaly (see zone_efficiency.py's docstring) -- both
are desperation heaves excluded from both Pareto frontiers, and are
represented on the diagram by a single grayed-out backcourt band rather
than a shape that would need its own EV/risk numbers.
"""

from dataclasses import dataclass

import matplotlib.pyplot as plt
from matplotlib.patches import Arc, Circle, Rectangle, Wedge

BASELINE_Y = -5.25
HALFCOURT_Y = 41.75
COURT_LINE_COLOR = "#c3c2b7"


@dataclass
class ZoneShape:
    kind: str  # "wedge" or "rect"
    params: dict
    label_xy: tuple[float, float]


# (SHOT_ZONE_BASIC, SHOT_ZONE_AREA) -> ZoneShape
ZONE_SHAPES: dict[tuple[str, str], ZoneShape] = {
    ("Restricted Area", "Center(C)"): ZoneShape(
        "wedge", dict(center=(0, 0), r=4, theta1=0, theta2=180), (0, 2.3)),

    ("In The Paint (Non-RA)", "Left Side(L)"): ZoneShape(
        "rect", dict(xy=(-8, 0), width=16 / 3, height=14), (-8 + 8 / 3, 9)),
    ("In The Paint (Non-RA)", "Center(C)"): ZoneShape(
        "rect", dict(xy=(-8 + 16 / 3, 0), width=16 / 3, height=14), (0, 9)),
    ("In The Paint (Non-RA)", "Right Side(R)"): ZoneShape(
        "rect", dict(xy=(8 - 16 / 3, 0), width=16 / 3, height=14), (8 - 8 / 3, 9)),

    ("Mid-Range", "Right Side(R)"): ZoneShape(
        "wedge", dict(center=(0, 0), r=23.75, width=23.75 - 8, theta1=0, theta2=25), (14, 3.3)),
    ("Mid-Range", "Right Side Center(RC)"): ZoneShape(
        "wedge", dict(center=(0, 0), r=23.75, width=23.75 - 8, theta1=25, theta2=70), (13.5, 12.5)),
    ("Mid-Range", "Center(C)"): ZoneShape(
        "wedge", dict(center=(0, 0), r=23.75, width=23.75 - 8, theta1=70, theta2=110), (0, 15.5)),
    ("Mid-Range", "Left Side Center(LC)"): ZoneShape(
        "wedge", dict(center=(0, 0), r=23.75, width=23.75 - 8, theta1=110, theta2=155), (-13.5, 12.5)),
    ("Mid-Range", "Left Side(L)"): ZoneShape(
        "wedge", dict(center=(0, 0), r=23.75, width=23.75 - 8, theta1=155, theta2=180), (-14, 3.3)),

    ("Right Corner 3", "Right Side(R)"): ZoneShape(
        "rect", dict(xy=(22, BASELINE_Y), width=3, height=8.95 - BASELINE_Y), (23.5, 1.9)),
    ("Left Corner 3", "Left Side(L)"): ZoneShape(
        "rect", dict(xy=(-25, BASELINE_Y), width=3, height=8.95 - BASELINE_Y), (-23.5, 1.9)),

    ("Above the Break 3", "Right Side Center(RC)"): ZoneShape(
        "wedge", dict(center=(0, 0), r=30, width=30 - 23.75, theta1=22.2, theta2=68), (19, 15)),
    ("Above the Break 3", "Center(C)"): ZoneShape(
        "wedge", dict(center=(0, 0), r=30, width=30 - 23.75, theta1=68, theta2=112), (0, 27)),
    ("Above the Break 3", "Left Side Center(LC)"): ZoneShape(
        "wedge", dict(center=(0, 0), r=30, width=30 - 23.75, theta1=112, theta2=157.8), (-19, 15)),
}

BACKCOURT_LABEL_XY = (0, HALFCOURT_Y + 5)


def zone_patch(zone_key: tuple[str, str], facecolor: str, hatch: str | None = None,
               alpha: float = 1.0, edgecolor: str = "white", linewidth: float = 1.0):
    shape = ZONE_SHAPES[zone_key]
    common = dict(facecolor=facecolor, edgecolor=edgecolor, linewidth=linewidth,
                  hatch=hatch, alpha=alpha, zorder=2)
    if shape.kind == "wedge":
        return Wedge(**shape.params, **common)
    return Rectangle(**shape.params, **common)


def draw_court_lines(ax):
    ax.plot([-25, 25], [BASELINE_Y, BASELINE_Y], color=COURT_LINE_COLOR, lw=1.3, zorder=3)
    ax.add_patch(Circle((0, 0), 0.75, fill=False, color=COURT_LINE_COLOR, lw=1.3, zorder=3))
    ax.plot([-3, 3], [-4, -4], color=COURT_LINE_COLOR, lw=1.6, zorder=3)
    ax.add_patch(Rectangle((-8, BASELINE_Y), 16, 14 - BASELINE_Y, fill=False,
                            color=COURT_LINE_COLOR, lw=1.0, zorder=3))
    ax.add_patch(Arc((0, 0), 8, 8, angle=0, theta1=0, theta2=180, color=COURT_LINE_COLOR, lw=1.0, zorder=3))
    ax.add_patch(Arc((0, 0), 47.5, 47.5, angle=0, theta1=22.2, theta2=157.8,
                      color=COURT_LINE_COLOR, lw=1.3, zorder=3))
    ax.plot([-22, -22], [BASELINE_Y, 8.95], color=COURT_LINE_COLOR, lw=1.3, zorder=3)
    ax.plot([22, 22], [BASELINE_Y, 8.95], color=COURT_LINE_COLOR, lw=1.3, zorder=3)
    ax.plot([-25, 25], [HALFCOURT_Y, HALFCOURT_Y], color=COURT_LINE_COLOR, lw=1.0,
             linestyle=":", zorder=3)


def draw_backcourt_band(ax, facecolor: str = "#dedcd3", hatch: str = "//"):
    ax.add_patch(Rectangle((-25, HALFCOURT_Y), 50, 12, facecolor=facecolor, edgecolor="white",
                            hatch=hatch, alpha=0.9, zorder=2))


def setup_half_court_axes(ax, surface: str, xlim=(-29, 29), ylim=(-8, HALFCOURT_Y + 13)):
    ax.set_facecolor(surface)
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    # Each entity is rendered as its OWN standalone figure (see
    # build_zone_heatmaps.render_panel_image) specifically so set_aspect
    # ("equal") is safe here: in an earlier shared-subplot-grid version,
    # equal-aspect's default view-limit re-adjustment interacted badly with
    # tight_layout and silently shrank some panels' effective x-range below
    # what set_xlim asked for, clipping the corner-3 labels nearest the
    # edge. With one axes per figure there's nothing else competing for
    # layout space, so the data view limits are respected exactly.
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)
