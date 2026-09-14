"""
build_2v3_plots.py

The "Mega Graph" workstream: two scatter plots of expected points per 100
possessions from 2s (x) vs. from 3s (y), both built on top of
data/season_totals_all.csv (produced by season_totals.py).

  Plot 1 -- "current era": 90 randomly-sampled 2025-26 players (minimum
  attempts floor applied so we're not sampling end-of-bench noise) plus
  that season's 10 highest total scorers, highlighted and labeled.

  Plot 2 -- "historic": the 100 highest-scoring individual player-seasons
  since 1996-97+, colored by season to show how the frontier has drifted
  over eras. (Originally scoped to start at 1979-80, when the 3-point line
  began -- shrunk to 1996-97 on 2026-09-07 because that's as far back as
  our data source's real `possessions` figure goes; see the decisions log.)

Both share an "iso-efficiency" diagonal (EV100_FROM_2 == EV100_FROM_3):
anyone above the line is, on this metric, statistically better off hunting
more 3s; anyone below is better off leaning on 2s.

Optional --headshots flag (see player_headshots.py / GitHub issue "Add
player headshots to 2v3 scatter plots"): stamps each HIGHLIGHTED point's
face on top of its dot -- the 10 highest scorers in Plot 1, the two
labeled points in Plot 2 -- not the full random-90/other-99 population,
to avoid overplotting. The colored dot is always drawn underneath as a
fallback layer, so a player with no available headshot (old players,
fetch failure) just shows the plain dot instead, same as without the flag.
NOT YET VALIDATED against real headshots -- run test_headshots_smoke.py
first (see player_headshots.py's module docstring).

Usage:
    python build_2v3_plots.py
    python build_2v3_plots.py --season 2025-26 --min-fga 200 --sample-seed 42
    python build_2v3_plots.py --headshots   # stamp faces on highlighted points
"""

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.lines import Line2D

COMBINED_PATH = Path("data/season_totals_all.csv")
OUT_DIR = Path(".")

# -- palette (validated via the dataviz skill's contrast/CVD checker) ------
SURFACE = "#fcfcfb"
INK_PRIMARY = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRIDLINE = "#e1e0d9"
BASELINE = "#c3c2b7"
BLUE = "#2a78d6"      # categorical slot 1 -- "the field"
ORANGE = "#eb6834"    # categorical slot 2 -- "the highlighted group"
SEQ_LIGHT = "#cde2fb"  # sequential ramp, oldest era
SEQ_DARK = "#0d366b"   # sequential ramp, most recent era


def _style_axes(ax):
    ax.set_facecolor(SURFACE)
    ax.figure.set_facecolor(SURFACE)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    for spine in ("left", "bottom"):
        ax.spines[spine].set_color(BASELINE)
    ax.tick_params(colors=INK_MUTED, labelsize=9)
    ax.grid(True, color=GRIDLINE, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)


def _iso_efficiency_line(ax, lo, hi):
    ax.plot([lo, hi], [lo, hi], color=BASELINE, linewidth=1.5, linestyle="--", zorder=1)
    # Anchored a bit short of the top-right corner and right-aligned so the
    # label hugs the line from below/left instead of extending INTO the
    # corner -- on plots with a colorbar (e.g. plot_historic), the colorbar
    # sits right at that corner and a left-aligned label placed at (hi, hi)
    # runs straight into its tick labels.
    label_pos = lo + 0.94 * (hi - lo)
    ax.text(label_pos, label_pos, "EV(3) = EV(2)  ", color=INK_MUTED, fontsize=8.5,
            ha="right", va="bottom", rotation=0)


def plot_current_era(df: pd.DataFrame, season: str, min_fga: int, seed: int,
                      headshots_cache_dir: Path | None = None) -> Path:
    pool = df[(df["SEASON"] == season) & (df["FGA"] >= min_fga)].copy()
    if pool.empty:
        raise ValueError(f"No {season} players with FGA >= {min_fga} -- check season_totals_all.csv")

    n_random = min(90, len(pool))
    rng = np.random.default_rng(seed)
    random_90 = pool.sample(n=n_random, random_state=rng)

    top_10 = pool.sort_values("PTS", ascending=False).head(10)

    fig, ax = plt.subplots(figsize=(9, 7.5), dpi=150)
    _style_axes(ax)

    ax.scatter(random_90["EV100_FROM_2"], random_90["EV100_FROM_3"],
               s=42, color=BLUE, alpha=0.55, edgecolor="none",
               label=f"Random {n_random} players (≥{min_fga} FGA)", zorder=2)
    ax.scatter(top_10["EV100_FROM_2"], top_10["EV100_FROM_3"],
               s=90, color=ORANGE, alpha=0.95, edgecolor=SURFACE, linewidth=1.2,
               label="10 highest scorers", zorder=3)

    if headshots_cache_dir is not None:
        from player_headshots import get_player_thumbnail, add_headshot_marker

    for _, row in top_10.iterrows():
        last_name = str(row["PLAYER_NAME"]).split(" ")[-1]
        ax.annotate(last_name, (row["EV100_FROM_2"], row["EV100_FROM_3"]),
                    textcoords="offset points", xytext=(6, 4),
                    fontsize=8.5, color=INK_SECONDARY)
        # The orange dot above is always drawn as the fallback layer; a
        # headshot, when available, is stamped on top of it -- a player
        # with no usable photo just keeps showing the plain dot.
        if headshots_cache_dir is not None and "PLAYER_ID" in row:
            thumb = get_player_thumbnail(int(row["PLAYER_ID"]), cache_dir=headshots_cache_dir, size_px=90)
            if thumb is not None:
                add_headshot_marker(ax, row["EV100_FROM_2"], row["EV100_FROM_3"], thumb, zoom=0.45)

    lo = min(pool["EV100_FROM_2"].min(), pool["EV100_FROM_3"].min()) - 2
    hi = max(pool["EV100_FROM_2"].max(), pool["EV100_FROM_3"].max()) + 2
    _iso_efficiency_line(ax, lo, hi)
    ax.set_xlim(lo, hi)
    ax.set_ylim(lo, hi)

    ax.set_xlabel("Expected points per 100 possessions, from 2s", color=INK_SECONDARY, fontsize=10)
    ax.set_ylabel("Expected points per 100 possessions, from 3s", color=INK_SECONDARY, fontsize=10)
    ax.set_title(f"2 vs 3 — {season}: {n_random} random players + the 10 highest scorers",
                 color=INK_PRIMARY, fontsize=13, fontweight="bold", loc="left", pad=14)

    # Upper-left is reliably the empty corner for this metric (very few
    # players are high-3PT-output/near-zero-2PT-output), so the legend
    # doesn't collide with data or the highlighted-player labels.
    legend = ax.legend(loc="upper left", frameon=False, fontsize=9, labelcolor=INK_SECONDARY)
    for handle in legend.legend_handles:
        handle.set_alpha(0.9)

    out_path = OUT_DIR / f"two_vs_three_{season.replace('-', '_')}.png"
    fig.tight_layout()
    fig.savefig(out_path, facecolor=SURFACE)
    plt.close(fig)
    return out_path


def plot_historic(df: pd.DataFrame, start_season: str, headshots_cache_dir: Path | None = None) -> Path:
    pool = df[df["SEASON"] >= start_season].copy()
    top_100 = pool.sort_values("PTS", ascending=False).head(100).copy()
    top_100["SEASON_YEAR"] = top_100["SEASON"].str[:4].astype(int)

    fig, ax = plt.subplots(figsize=(9, 7.5), dpi=150)
    _style_axes(ax)

    cmap = LinearSegmentedColormap.from_list("era", [SEQ_LIGHT, SEQ_DARK])
    norm = plt.Normalize(top_100["SEASON_YEAR"].min(), top_100["SEASON_YEAR"].max())
    sc = ax.scatter(top_100["EV100_FROM_2"], top_100["EV100_FROM_3"],
                     s=70, c=top_100["SEASON_YEAR"], cmap=cmap, norm=norm,
                     edgecolor=INK_PRIMARY, linewidth=0.3, alpha=0.9, zorder=2)

    if headshots_cache_dir is not None:
        from player_headshots import get_player_thumbnail, add_headshot_marker

    def _stamp_headshot(row):
        if headshots_cache_dir is not None and "PLAYER_ID" in row:
            thumb = get_player_thumbnail(int(row["PLAYER_ID"]), cache_dir=headshots_cache_dir, size_px=80)
            if thumb is not None:
                add_headshot_marker(ax, row["EV100_FROM_2"], row["EV100_FROM_3"], thumb, zoom=0.4)

    # Label the single highest-scoring season of all time and the most recent one.
    for _, row in top_100.sort_values("PTS", ascending=False).head(1).iterrows():
        label = f"{str(row['PLAYER_NAME']).split(' ')[-1]} {row['SEASON']} ({int(row['PTS'])} pts)"
        ax.annotate(label, (row["EV100_FROM_2"], row["EV100_FROM_3"]),
                    textcoords="offset points", xytext=(6, 6), fontsize=8.5, color=INK_SECONDARY)
        _stamp_headshot(row)
    most_recent = top_100.sort_values("SEASON_YEAR", ascending=False).iloc[0]
    ax.annotate(f"{str(most_recent['PLAYER_NAME']).split(' ')[-1]} {most_recent['SEASON']}",
                (most_recent["EV100_FROM_2"], most_recent["EV100_FROM_3"]),
                textcoords="offset points", xytext=(6, -10), fontsize=8.5, color=INK_SECONDARY)
    _stamp_headshot(most_recent)

    lo = min(top_100["EV100_FROM_2"].min(), top_100["EV100_FROM_3"].min()) - 2
    hi = max(top_100["EV100_FROM_2"].max(), top_100["EV100_FROM_3"].max()) + 2
    _iso_efficiency_line(ax, lo, hi)
    ax.set_xlim(lo, hi)
    ax.set_ylim(lo, hi)

    ax.set_xlabel("Expected points per 100 possessions, from 2s", color=INK_SECONDARY, fontsize=10)
    ax.set_ylabel("Expected points per 100 possessions, from 3s", color=INK_SECONDARY, fontsize=10)
    ax.set_title(f"2 vs 3 — the 100 highest-scoring player-seasons since {start_season}",
                 color=INK_PRIMARY, fontsize=13, fontweight="bold", loc="left", pad=14)

    cbar = fig.colorbar(sc, ax=ax, pad=0.02)
    cbar.set_label("Season", color=INK_SECONDARY, fontsize=9)
    cbar.ax.tick_params(colors=INK_MUTED, labelsize=8)
    cbar.outline.set_visible(False)

    out_path = OUT_DIR / "two_vs_three_historic_top100.png"
    fig.tight_layout()
    fig.savefig(out_path, facecolor=SURFACE)
    plt.close(fig)
    return out_path


def main():
    parser = argparse.ArgumentParser(description="Build the two 'Mega Graph' 2-vs-3 scatter plots.")
    parser.add_argument("--season", default="2025-26", help="season for the random-90 + top-10 plot")
    parser.add_argument("--min-fga", type=int, default=200,
                         help="minimum field-goal attempts to be eligible for the random-90 sample")
    parser.add_argument("--sample-seed", type=int, default=42, help="random seed for the 90-player sample")
    parser.add_argument("--historic-start", default="1996-97", help="first season eligible for the historic top-100")
    parser.add_argument("--headshots", action="store_true",
                         help="stamp player headshots on highlighted points (needs internet + Pillow; "
                              "see player_headshots.py -- NOT yet validated against real player IDs)")
    parser.add_argument("--headshots-cache-dir", type=Path, default=Path("data/headshots"))
    args = parser.parse_args()

    if not COMBINED_PATH.exists():
        raise SystemExit(f"{COMBINED_PATH} not found -- run season_totals.py first.")

    if args.headshots:
        try:
            import player_headshots  # noqa: F401 -- import check only
        except ImportError as e:
            raise SystemExit(f"--headshots needs player_headshots.py's dependencies (pip install pillow requests): {e}")

    headshots_cache_dir = args.headshots_cache_dir if args.headshots else None

    df = pd.read_csv(COMBINED_PATH)

    p1 = plot_current_era(df, args.season, args.min_fga, args.sample_seed, headshots_cache_dir=headshots_cache_dir)
    print(f"Saved: {p1}")

    p2 = plot_historic(df, args.historic_start, headshots_cache_dir=headshots_cache_dir)
    print(f"Saved: {p2}")


if __name__ == "__main__":
    main()
