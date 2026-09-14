"""
build_zone_heatmaps.py

Workstream 1 ("Efficient Zones + Players"): renders the zone-level
Pareto-efficiency heatmaps -- gold for efficient zones, red for
sub-optimal, per the original Notion spec -- for the league average and
5 named players, reading data/zone_efficiency.csv (produced by
zone_efficiency.py).

Two figures, matching the "show both" decision on Restricted-Area
dominance (see zone_efficiency.py / the project decisions log):

  zone_efficiency_full.png    -- every zone including Restricted Area.
                                  RA predictably shows gold (highest EV,
                                  lowest risk) and dominates everything
                                  else, which is mathematically correct
                                  but not the live decision a coach faces
                                  once a shot at the rim isn't open.
  zone_efficiency_nonra.png   -- Restricted Area and Backcourt grayed out
                                  (excluded from this frontier), isolating
                                  the actual jump-shot tradeoff.

Each panel is a half-court diagram, one per entity (League Average + the
5 players), laid out as a 2x3 grid. Zone shapes are analytic
approximations built in court_viz.py, not exact shot-by-shot boundaries
-- see that module's docstring. Backcourt (and the "Above the Break 3"/
Back Court(BC) heave anomaly) is always shown as a single grayed,
hatched band regardless of view: it's excluded from both frontiers
entirely, not merely "dominated."

Every zone's fill carries a text label (FG%, points per shot) so the read
never depends on color alone, and a zone with fewer than
zone_efficiency.LOW_SAMPLE_THRESHOLD attempts for that entity is
cross-hatched ("xx") with an "n=" attempt count added to its label --
small samples get flagged, not hidden or dropped. A zone with literally
zero shots for that entity gets a distinct dotted-gray "no shots" tile,
separate from the "excluded from this frontier" treatment used for
Restricted Area (in the non-RA view) and the heave band.

Usage:
    python zone_efficiency.py        # writes data/zone_efficiency.csv first
    python build_zone_heatmaps.py
"""

import io
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from PIL import Image

from court_viz import (BACKCOURT_LABEL_XY, HALFCOURT_Y, ZONE_SHAPES,
                        draw_backcourt_band, draw_court_lines,
                        setup_half_court_axes, zone_patch)

PANEL_XLIM = (-29, 29)
PANEL_YLIM = (-8, HALFCOURT_Y + 13)
PANEL_DPI = 170

ZONE_EFFICIENCY_PATH = Path("data/zone_efficiency.csv")
OUT_DIR = Path(".")

# -- palette: reuses the project's existing chart chrome (build_2v3_plots.py),
# plus a gold/red status pair for efficient/dominated, validated with the
# dataviz skill's palette checker (CVD ΔE 10.2, normal-vision ΔE 16.9 --
# both clear their floors; gold's surface contrast is a touch under 3:1,
# mitigated here the way the skill requires: every zone always carries a
# visible text label, never color alone).
SURFACE = "#fcfcfb"
INK_PRIMARY = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GOLD = "#c98500"
RED = "#d03b3b"
EXCLUDED_GRAY = "#dedcd3"

ENTITY_ORDER = ["League Average", "LeBron James", "Luka Doncic",
                "Stephen Curry", "Nikola Jokic", "Giannis Antetokounmpo"]


def _label_color(facecolor: str) -> str:
    return "white" if facecolor in (GOLD, RED) else INK_SECONDARY


def _fig_to_pil(fig) -> Image.Image:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    return Image.open(buf).convert("RGB")


def draw_entity_panel(ax, entity_rows: pd.DataFrame, frontier_col: str):
    draw_court_lines(ax)
    draw_backcourt_band(ax)
    ax.text(*BACKCOURT_LABEL_XY, "excluded (heaves)", ha="center", va="bottom",
             fontsize=6.5, color=INK_MUTED)

    by_zone = {(r.SHOT_ZONE_BASIC, r.SHOT_ZONE_AREA): r for r in entity_rows.itertuples()}

    for zone_key in ZONE_SHAPES:
        row = by_zone.get(zone_key)
        shape = ZONE_SHAPES[zone_key]
        hatch = None
        if row is None:
            facecolor, label = EXCLUDED_GRAY, "no shots"
            hatch = ".."
        else:
            eff = getattr(row, frontier_col)
            facecolor = EXCLUDED_GRAY if pd.isna(eff) else (GOLD if eff else RED)
            label = f"{row.FG_PCT:.0%}\n{row.EV:.2f}"
            if row.LOW_SAMPLE:
                label += f"\nn={int(row.N_ATTEMPTS)}"
                hatch = "xx"

        ax.add_patch(zone_patch(zone_key, facecolor=facecolor, hatch=hatch))

        # Corner-3 rectangles are only 3ft wide but 14ft tall -- a 3-line
        # label at any readable font overflows that width, so those get
        # rotated 90 degrees to run along the long (tall) dimension
        # instead of the short one. Everything else (paint thirds, the
        # wide angular wedges) has enough width at the default size/angle.
        is_narrow_rect = shape.kind == "rect" and shape.params.get("width", 99) <= 3.5
        fontsize = 6.3 if is_narrow_rect else 5.8
        rotation = 90 if is_narrow_rect else 0
        display_label = label.replace("\n", "   ") if is_narrow_rect else label

        lx, ly = shape.label_xy
        ax.text(lx, ly, display_label, ha="center", va="center", fontsize=fontsize,
                color=_label_color(facecolor), zorder=4, linespacing=1.2, rotation=rotation)

    setup_half_court_axes(ax, SURFACE)


def render_panel_image(entity: str, rows: pd.DataFrame, frontier_col: str) -> Image.Image:
    """Each entity gets its OWN standalone figure -- deliberately not a shared
    subplot grid. matplotlib's tight_layout + equal-aspect handling was
    silently shrinking some panels' effective view range in a shared grid
    (visible as clipped corner-3 labels that varied panel to panel for no
    principled reason) -- rendering one court per figure, at a fixed
    figsize/dpi with the axes filling the whole canvas, and compositing the
    six with PIL below sidesteps that layout interaction entirely."""
    width_data = PANEL_XLIM[1] - PANEL_XLIM[0]
    height_data = PANEL_YLIM[1] - PANEL_YLIM[0]
    fig_w = 4.4
    fig_h = fig_w * height_data / width_data

    fig = plt.figure(figsize=(fig_w, fig_h), dpi=PANEL_DPI)
    fig.patch.set_facecolor(SURFACE)
    ax = fig.add_axes([0.02, 0.02, 0.96, 0.90])  # leave headroom for the title
    draw_entity_panel(ax, rows, frontier_col)
    ax.set_title(entity, color=INK_PRIMARY, fontsize=13, fontweight="bold", pad=6)
    return _fig_to_pil(fig)


def render_header(subtitle: str, width_px: int) -> Image.Image:
    fig = plt.figure(figsize=(width_px / PANEL_DPI, 0.9), dpi=PANEL_DPI)
    fig.patch.set_facecolor(SURFACE)
    fig.text(0.5, 0.72, f"Workstream 1 — Zone efficiency: {subtitle}",
              ha="center", va="center", color=INK_PRIMARY, fontsize=16, fontweight="bold")
    fig.text(0.5, 0.22,
              "Gold = Pareto-efficient (best expected points per shot for its risk)  ·  "
              "Red = dominated by another zone  ·  label = FG% / points per shot  ·  "
              "2023-24 regular season shot log",
              ha="center", va="center", color=INK_MUTED, fontsize=10)
    return _fig_to_pil(fig)


def render_footer_legend(width_px: int) -> Image.Image:
    fig = plt.figure(figsize=(width_px / PANEL_DPI, 0.55), dpi=PANEL_DPI)
    fig.patch.set_facecolor(SURFACE)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.axis("off")
    legend_handles = [
        Patch(facecolor=GOLD, edgecolor="white", label="Pareto-efficient"),
        Patch(facecolor=RED, edgecolor="white", label="Dominated (sub-optimal)"),
        Patch(facecolor=EXCLUDED_GRAY, edgecolor="white", hatch="//", label="Excluded from this frontier"),
        Patch(facecolor=EXCLUDED_GRAY, edgecolor="white", hatch="..", label="No shots in this zone"),
        Line2D([0], [0], marker="none", linestyle="none", label="xx hatch + n= : fewer than 20 attempts"),
    ]
    ax.legend(handles=legend_handles, loc="center", ncol=5, frameon=False,
              fontsize=9.5, labelcolor=INK_SECONDARY)
    return _fig_to_pil(fig)


def build_figure(df: pd.DataFrame, frontier_col: str, subtitle: str, out_path: Path):
    panels = [render_panel_image(e, df[df["ENTITY"] == e], frontier_col) for e in ENTITY_ORDER]
    pw, ph = panels[0].size

    grid = Image.new("RGB", (pw * 3, ph * 2), SURFACE)
    for i, panel in enumerate(panels):
        row, col = divmod(i, 3)
        grid.paste(panel, (col * pw, row * ph))

    header = render_header(subtitle, grid.width)
    header = header.resize((grid.width, header.height))
    footer = render_footer_legend(grid.width)
    footer = footer.resize((grid.width, footer.height))

    out = Image.new("RGB", (grid.width, header.height + grid.height + footer.height), SURFACE)
    out.paste(header, (0, 0))
    out.paste(grid, (0, header.height))
    out.paste(footer, (0, header.height + grid.height))
    out.save(out_path)
    return out_path


def main():
    if not ZONE_EFFICIENCY_PATH.exists():
        raise SystemExit(f"{ZONE_EFFICIENCY_PATH} not found -- run zone_efficiency.py first.")

    df = pd.read_csv(ZONE_EFFICIENCY_PATH)
    missing = set(ENTITY_ORDER) - set(df["ENTITY"].unique())
    if missing:
        raise SystemExit(f"Missing entities in {ZONE_EFFICIENCY_PATH}: {missing}")

    p1 = build_figure(df, "EFF_FULL",
                       "full frontier (Restricted Area included)",
                       OUT_DIR / "zone_efficiency_full.png")
    print(f"Saved: {p1}")

    p2 = build_figure(df, "EFF_NONRA",
                       "non-RA cut — jump shots only",
                       OUT_DIR / "zone_efficiency_nonra.png")
    print(f"Saved: {p2}")


if __name__ == "__main__":
    main()
