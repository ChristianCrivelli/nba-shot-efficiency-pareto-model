"""
build_breakeven_trend.py

Workstream 4 ("Synthesis & Strategy") — the era-comparison half of the
spec: "how the frontier has moved outward across eras." Aggregates
data/season_totals_all.csv (the same file workstream 2 uses) up to the
LEAGUE level per season and compares actual league-wide 2PT FG% against
the break-even 2PT FG% implied by that season's actual league-wide 3PT
FG% -- the same EV(2)=EV(3) relation from the "2 vs 3" spec (workstream
3), just solved for the break-even shooting percentage instead of
expected points:

    EV(2) = EV(3)
    2 * FG2_PCT = 3 * FG3_PCT
    FG2_PCT_BREAKEVEN = 1.5 * FG3_PCT

When actual league FG2% is BELOW this line, the league is (in aggregate)
scoring more efficiently from 3s than from 2s -- i.e. the average 2-point
shot being taken is a worse bet than the average 3-point shot, even
before accounting for the extra point on makes. Above the line, the
reverse.

Two panels, sharing the season x-axis (never a dual-axis single chart --
each panel has exactly one y-axis, per the dataviz skill's non-negotiable
rule):

  Top    -- actual league FG2% vs. the break-even FG2% line, with the
            region where actual > break-even shaded to mark the seasons
            where 2-point shots were, on aggregate, "worth it."
  Bottom -- league-wide 3-point attempt rate (FG3A / total FGA) over the
            same seasons, for context: this is the volume side of the
            same story -- teams shot more 3s every single season in this
            span even while the accuracy side (top panel) didn't
            consistently favor doing so until the last few years.

Caveat carried into the write-up, not hidden here: this is a LEAGUE
AVERAGE. It says nothing about any single shot, shooter, or matchup --
see synthesis_and_strategy.md for the full caveat list.

Usage:
    python build_breakeven_trend.py
"""

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

COMBINED_PATH = Path("data/season_totals_all.csv")
OUT_PATH = Path("breakeven_trend.png")

# -- palette: same chart chrome as build_2v3_plots.py / build_zone_heatmaps.py --
SURFACE = "#fcfcfb"
INK_PRIMARY = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRIDLINE = "#e1e0d9"
BASELINE = "#c3c2b7"
BLUE = "#2a78d6"     # actual FG2%
ORANGE = "#eb6834"   # break-even FG2% threshold
GOOD_FILL = "#0ca30c"  # dataviz skill's "good" status color, used sparingly
                        # as a light wash, not a solid fill -- marks the
                        # seasons where actual FG2% cleared the break-even line


def _style_axes(ax):
    ax.set_facecolor(SURFACE)
    ax.figure.set_facecolor(SURFACE)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    for spine in ("left", "bottom"):
        ax.spines[spine].set_color(BASELINE)
    ax.tick_params(colors=INK_MUTED, labelsize=8.5)
    ax.grid(True, axis="y", color=GRIDLINE, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)


def compute_league_trend(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby("SEASON").agg(
        FG2M=("FG2M", "sum"), FG2A=("FG2A", "sum"),
        FG3M=("FG3M", "sum"), FG3A=("FG3A", "sum"),
    ).reset_index().sort_values("SEASON")
    g["FG2_PCT"] = g["FG2M"] / g["FG2A"]
    g["FG3_PCT"] = g["FG3M"] / g["FG3A"]
    g["BREAKEVEN_FG2_PCT"] = 1.5 * g["FG3_PCT"]
    g["GAP"] = g["FG2_PCT"] - g["BREAKEVEN_FG2_PCT"]
    g["FG3A_SHARE"] = g["FG3A"] / (g["FG2A"] + g["FG3A"])
    return g


def build_figure(g: pd.DataFrame) -> Path:
    x = range(len(g))
    seasons = g["SEASON"].tolist()

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), dpi=150,
                                    gridspec_kw={"height_ratios": [1.4, 1]})
    fig.patch.set_facecolor(SURFACE)

    # -- top panel: actual vs. break-even FG2% --
    _style_axes(ax1)
    crossed = g["GAP"] >= 0
    first_cross_idx = crossed.idxmax() if crossed.any() else None

    ax1.fill_between(x, g["FG2_PCT"] * 100, g["BREAKEVEN_FG2_PCT"] * 100,
                      where=(g["FG2_PCT"] >= g["BREAKEVEN_FG2_PCT"]),
                      color=GOOD_FILL, alpha=0.12, zorder=1, interpolate=True)

    ax1.plot(x, g["BREAKEVEN_FG2_PCT"] * 100, color=ORANGE, linewidth=1.8,
              linestyle="--", zorder=3, label="Break-even 2PT% (1.5 × league 3PT%)")
    ax1.plot(x, g["FG2_PCT"] * 100, color=BLUE, linewidth=2.2, zorder=4,
              label="Actual league 2PT%", marker="o", markersize=3)

    if first_cross_idx is not None:
        ax1.annotate("2s first \"worth it\"\non aggregate",
                      (first_cross_idx, g.loc[first_cross_idx, "FG2_PCT"] * 100),
                      textcoords="offset points", xytext=(-10, 14), fontsize=8.5,
                      color=INK_SECONDARY, ha="right",
                      arrowprops=dict(arrowstyle="-", color=INK_MUTED, lw=0.8))

    ax1.set_ylabel("Field goal %", color=INK_SECONDARY, fontsize=10)
    ax1.set_title("Has the average 2-point shot been \"worth it\"?",
                   color=INK_PRIMARY, fontsize=13, fontweight="bold", loc="left", pad=10)
    ax1.legend(loc="lower right", frameon=False, fontsize=9, labelcolor=INK_SECONDARY)
    ax1.set_xticks([])

    # -- bottom panel: 3PT attempt rate --
    _style_axes(ax2)
    ax2.plot(x, g["FG3A_SHARE"] * 100, color=BLUE, linewidth=2.2, zorder=3,
              marker="o", markersize=3)
    ax2.set_ylabel("3PT attempts, % of all FGA", color=INK_SECONDARY, fontsize=10)
    ax2.set_title("...while teams kept shooting more 3s every season regardless",
                   color=INK_PRIMARY, fontsize=11, loc="left", pad=8)

    tick_idx = list(range(0, len(seasons), 3))
    ax2.set_xticks(tick_idx)
    ax2.set_xticklabels([seasons[i] for i in tick_idx], rotation=45, ha="right", fontsize=8)

    fig.suptitle("Workstream 4 — The 2-vs-3 break-even line across eras, 1996-97 to 2025-26",
                 color=INK_PRIMARY, fontsize=14, fontweight="bold", y=0.995)
    fig.tight_layout(rect=[0, 0, 1, 0.965])
    fig.savefig(OUT_PATH, facecolor=SURFACE)
    plt.close(fig)
    return OUT_PATH


def main():
    if not COMBINED_PATH.exists():
        raise SystemExit(f"{COMBINED_PATH} not found -- run load_kaggle_season_totals.py first.")

    df = pd.read_csv(COMBINED_PATH)
    g = compute_league_trend(df)

    g.to_csv("data/breakeven_trend.csv", index=False)
    print(f"Saved: data/breakeven_trend.csv ({len(g)} seasons)")

    out = build_figure(g)
    print(f"Saved: {out}")

    first_cross = g[g["GAP"] >= 0]["SEASON"].min()
    print(f"League FG2% first cleared the break-even line in: {first_cross}")
    print(g[["SEASON", "FG2_PCT", "BREAKEVEN_FG2_PCT", "GAP", "FG3A_SHARE"]].round(4).to_string(index=False))


if __name__ == "__main__":
    main()
