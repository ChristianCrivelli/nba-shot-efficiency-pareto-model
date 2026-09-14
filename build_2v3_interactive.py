"""
build_2v3_interactive.py

Interactive counterpart to build_2v3_plots.py: the same two "Mega Graph"
populations (current-era random-90 + top-10, and the historic top-100),
rendered as self-contained HTML pages instead of static PNGs. Every
player is a small circular headshot marker (falling back to a plain
colored dot for anyone without a usable real photo); hovering (or, for
the nearest point, moving the pointer near it) shows a tooltip with name,
season, points, and the EV100_FROM_2/3 + shooting-split numbers. A
collapsible data table underneath carries the same numbers for every
point without needing to hover -- per the project's dataviz skill,
tooltips enhance, they never gate.

Run this LOCALLY -- it needs data/season_totals_all.csv (from
load_kaggle_season_totals.py) AND live internet access to fetch headshots
from cdn.nba.com via player_headshots.py (same network restriction as
everything else that talks to the NBA's servers -- unreachable from the
Claude sandbox that wrote this script). Headshots are cached under
--headshots-cache-dir between runs, same as build_2v3_plots.py.

Output is fully self-contained (headshots embedded as base64 data URIs,
no external JS/CSS/font dependencies) -- the HTML files work by opening
them directly in a browser, no server needed.

Usage:
    python build_2v3_interactive.py
    python build_2v3_interactive.py --season 2025-26 --min-fga 200 --sample-seed 42
"""

import argparse
import base64
import json
import logging
from io import BytesIO
from pathlib import Path

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-7s  %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

COMBINED_PATH = Path("data/season_totals_all.csv")
OUT_DIR = Path(".")

# -- palette (same validated palette as build_2v3_plots.py) ----------------
SURFACE = "#fcfcfb"
INK_PRIMARY = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRIDLINE = "#e1e0d9"
BASELINE = "#c3c2b7"
BLUE = "#2a78d6"
ORANGE = "#eb6834"
SEQ_LIGHT = "#cde2fb"
SEQ_DARK = "#0d366b"


def _lerp_hex(c1: str, c2: str, t: float) -> str:
    t = max(0.0, min(1.0, t))
    r1, g1, b1 = int(c1[1:3], 16), int(c1[3:5], 16), int(c1[5:7], 16)
    r2, g2, b2 = int(c2[1:3], 16), int(c2[3:5], 16), int(c2[5:7], 16)
    r = round(r1 + (r2 - r1) * t)
    g = round(g1 + (g2 - g1) * t)
    b = round(b1 + (b2 - b1) * t)
    return f"#{r:02x}{g:02x}{b:02x}"


def _pct(made, att):
    made, att = float(made), float(att)
    if att <= 0:
        return None
    return round(made / att * 100, 1)


# -- headshot fetch (shared cache across both plots' populations) ----------

def _fetch_photo_data_uris(player_ids: set[int], cache_dir: Path) -> dict[int, str | None]:
    """Fetches + circular-crops a small headshot for each id, returns a
    dict of player_id -> base64 PNG data URI, or None if no usable real
    photo exists (fetch failed, or it's the generic silhouette
    placeholder -- see player_headshots.py's 2026-09-08 validation)."""
    from player_headshots import fetch_headshot, looks_like_placeholder, circular_thumbnail

    out: dict[int, str | None] = {}
    ids = sorted(player_ids)
    log.info("Fetching headshots for %d unique players (cached under %s)...", len(ids), cache_dir)
    for i, pid in enumerate(ids, 1):
        path = fetch_headshot(pid, cache_dir=cache_dir)
        if path is not None and looks_like_placeholder(path):
            path = None  # generic silhouette -- treat as "no real photo"
        if path is None:
            out[pid] = None
        else:
            thumb = circular_thumbnail(path, size_px=64)
            if thumb is None:
                out[pid] = None
            else:
                buf = BytesIO()
                thumb.save(buf, format="PNG")
                out[pid] = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")
        if i % 25 == 0 or i == len(ids):
            n_real = sum(1 for v in out.values() if v is not None)
            log.info("  %d/%d fetched (%d real photos so far)", i, len(ids), n_real)
    return out


# -- population builders (mirrors build_2v3_plots.py's sampling exactly) ---

def _current_era_population(df: pd.DataFrame, season: str, min_fga: int, seed: int) -> pd.DataFrame:
    pool = df[(df["SEASON"] == season) & (df["FGA"] >= min_fga)].copy()
    if pool.empty:
        raise ValueError(f"No {season} players with FGA >= {min_fga} -- check season_totals_all.csv")

    n_random = min(90, len(pool))
    rng = np.random.default_rng(seed)
    random_ids = set(pool.sample(n=n_random, random_state=rng)["PLAYER_ID"])
    top10_ids = set(pool.sort_values("PTS", ascending=False).head(10)["PLAYER_ID"])

    keep_ids = random_ids | top10_ids
    out = pool[pool["PLAYER_ID"].isin(keep_ids)].copy()
    out["GROUP"] = out["PLAYER_ID"].apply(lambda pid: "top10" if pid in top10_ids else "random")
    out["LABELED"] = out["GROUP"] == "top10"
    return out


def _historic_population(df: pd.DataFrame, start_season: str) -> pd.DataFrame:
    pool = df[df["SEASON"] >= start_season].copy()
    top_100 = pool.sort_values("PTS", ascending=False).head(100).copy()
    top_100["SEASON_YEAR"] = top_100["SEASON"].str[:4].astype(int)

    top_100["LABELED"] = False
    top_100["LABEL_TEXT"] = ""
    leader_idx = top_100.sort_values("PTS", ascending=False).index[0]
    recent_idx = top_100.sort_values("SEASON_YEAR", ascending=False).index[0]
    top_100.loc[leader_idx, "LABELED"] = True
    top_100.loc[leader_idx, "LABEL_TEXT"] = (
        f"{str(top_100.loc[leader_idx, 'PLAYER_NAME']).split(' ')[-1]} "
        f"{top_100.loc[leader_idx, 'SEASON']} ({int(top_100.loc[leader_idx, 'PTS'])} pts)"
    )
    top_100.loc[recent_idx, "LABELED"] = True
    top_100.loc[recent_idx, "LABEL_TEXT"] = (
        f"{str(top_100.loc[recent_idx, 'PLAYER_NAME']).split(' ')[-1]} {top_100.loc[recent_idx, 'SEASON']}"
    )
    return top_100


# -- record building for the JS renderer ------------------------------------

def _build_records_current(pool: pd.DataFrame, photos: dict) -> tuple[list[dict], float, float]:
    records = []
    for _, row in pool.iterrows():
        pid = int(row["PLAYER_ID"])
        ring = ORANGE if row["GROUP"] == "top10" else BLUE
        records.append({
            "id": pid,
            "name": str(row["PLAYER_NAME"]),
            "season": str(row["SEASON"]),
            "pts": int(row["PTS"]),
            "ev2": round(float(row["EV100_FROM_2"]), 2),
            "ev3": round(float(row["EV100_FROM_3"]), 2),
            "fgPct": _pct(row["FGM"], row["FGA"]),
            "threePct": _pct(row["FG3M"], row["FG3A"]),
            "group": row["GROUP"],
            "ring": ring,
            "labeled": bool(row["LABELED"]),
            "labelText": str(row["PLAYER_NAME"]).split(" ")[-1] if row["LABELED"] else "",
            "photo": photos.get(pid),
        })
    lo = min(pool["EV100_FROM_2"].min(), pool["EV100_FROM_3"].min()) - 2
    hi = max(pool["EV100_FROM_2"].max(), pool["EV100_FROM_3"].max()) + 2
    return records, float(lo), float(hi)


def _build_records_historic(pool: pd.DataFrame, photos: dict) -> tuple[list[dict], float, float, int, int]:
    yr_lo, yr_hi = int(pool["SEASON_YEAR"].min()), int(pool["SEASON_YEAR"].max())
    records = []
    for _, row in pool.iterrows():
        pid = int(row["PLAYER_ID"])
        t = (row["SEASON_YEAR"] - yr_lo) / (yr_hi - yr_lo) if yr_hi > yr_lo else 0.0
        ring = _lerp_hex(SEQ_LIGHT, SEQ_DARK, t)
        records.append({
            "id": pid,
            "name": str(row["PLAYER_NAME"]),
            "season": str(row["SEASON"]),
            "pts": int(row["PTS"]),
            "ev2": round(float(row["EV100_FROM_2"]), 2),
            "ev3": round(float(row["EV100_FROM_3"]), 2),
            "fgPct": _pct(row["FGM"], row["FGA"]),
            "threePct": _pct(row["FG3M"], row["FG3A"]),
            "seasonYear": int(row["SEASON_YEAR"]),
            "ring": ring,
            "labeled": bool(row["LABELED"]),
            "labelText": str(row["LABEL_TEXT"]),
            "photo": photos.get(pid),
        })
    lo = min(pool["EV100_FROM_2"].min(), pool["EV100_FROM_3"].min()) - 2
    hi = max(pool["EV100_FROM_2"].max(), pool["EV100_FROM_3"].max()) + 2
    return records, float(lo), float(hi), yr_lo, yr_hi


# -- HTML rendering -----------------------------------------------------

_PAGE_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>
  :root {{
    --surface: {SURFACE}; --ink-primary: {INK_PRIMARY}; --ink-secondary: {INK_SECONDARY};
    --ink-muted: {INK_MUTED}; --gridline: {GRIDLINE}; --baseline: {BASELINE};
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; background: var(--surface); color: var(--ink-primary);
    font-family: -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    padding: 28px 32px 48px;
  }}
  h1 {{ font-size: 20px; margin: 0 0 2px; }}
  .subtitle {{ color: var(--ink-secondary); font-size: 13px; margin: 0 0 18px; }}
  .chart-wrap {{ position: relative; max-width: 980px; }}
  svg {{ width: 100%; height: auto; display: block; }}
  .axis-label {{ fill: var(--ink-secondary); font-size: 13px; }}
  .tick-label {{ fill: var(--ink-muted); font-size: 11px; }}
  .gridline {{ stroke: var(--gridline); stroke-width: 1; }}
  .diag {{ stroke: var(--baseline); stroke-width: 1.5; stroke-dasharray: 6 5; fill: none; }}
  .diag-label {{ fill: var(--ink-muted); font-size: 11.5px; }}
  .marker-ring {{ fill: none; stroke-width: 2.4; transition: r 120ms ease; }}
  .marker-dot {{ transition: r 120ms ease; }}
  .marker-label {{ fill: var(--ink-secondary); font-size: 11px; pointer-events: none; }}
  .legend text, .colorbar-label {{ fill: var(--ink-secondary); font-size: 12px; }}
  #tooltip {{
    position: absolute; pointer-events: none; background: var(--ink-primary); color: var(--surface);
    border-radius: 8px; padding: 8px 11px; font-size: 12.5px; line-height: 1.5;
    box-shadow: 0 4px 16px rgba(0,0,0,.18); opacity: 0; transform: translate(-50%, -110%);
    transition: opacity 100ms ease; white-space: nowrap; z-index: 10;
  }}
  #tooltip.visible {{ opacity: 1; }}
  #tooltip .t-name {{ font-weight: 700; font-size: 13.5px; }}
  #tooltip .t-season {{ color: #c9c8c2; }}
  #tooltip .t-row {{ display: flex; gap: 14px; margin-top: 3px; }}
  #tooltip .t-val {{ font-weight: 700; }}
  details.table-toggle {{ max-width: 980px; margin-top: 22px; }}
  summary {{
    cursor: pointer; color: var(--ink-secondary); font-size: 13px; padding: 6px 0;
    user-select: none;
  }}
  table {{ border-collapse: collapse; width: 100%; font-size: 12.5px; margin-top: 8px; }}
  th, td {{ text-align: right; padding: 5px 10px; border-bottom: 1px solid var(--gridline); font-variant-numeric: tabular-nums; }}
  th:first-child, td:first-child {{ text-align: left; }}
  th {{ color: var(--ink-muted); font-weight: 600; font-size: 11px; text-transform: uppercase; letter-spacing: .02em; }}
  td {{ color: var(--ink-primary); }}
</style>
</head>
<body>
  <h1>{title}</h1>
  <p class="subtitle">{subtitle} — hover any player for season, expected points, and shooting splits.</p>
  <div class="chart-wrap">
    <svg id="chart" viewBox="0 0 {vb_w} {vb_h}"></svg>
    <div id="tooltip"></div>
  </div>
  <details class="table-toggle">
    <summary>View full data table ({n_points} players)</summary>
    <table id="data-table">
      <thead><tr><th>Player</th><th>Season</th><th>PTS</th><th>EV(2)</th><th>EV(3)</th><th>FG%</th><th>3P%</th></tr></thead>
      <tbody></tbody>
    </table>
  </details>

<script>
const CONFIG = {config_json};
const DATA = {data_json};
{render_script}
</script>
</body>
</html>
"""

_RENDER_SCRIPT = r"""
(function () {
  const svg = document.getElementById("chart");
  const tooltip = document.getElementById("tooltip");
  const NS = "http://www.w3.org/2000/svg";

  const margin = { left: 68, right: CONFIG.colorbar ? 108 : 40, top: 26, bottom: 56 };
  const plotW = CONFIG.vbW - margin.left - margin.right;
  const plotH = CONFIG.vbH - margin.top - margin.bottom;
  const lo = CONFIG.lo, hi = CONFIG.hi;

  function sx(v) { return margin.left + ((v - lo) / (hi - lo)) * plotW; }
  function sy(v) { return margin.top + plotH - ((v - lo) / (hi - lo)) * plotH; }

  function el(tag, attrs, parent) {
    const e = document.createElementNS(NS, tag);
    for (const k in attrs) e.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(e);
    return e;
  }

  // -- gridlines + ticks --------------------------------------------------
  const step = CONFIG.tickStep;
  const tickStart = Math.ceil(lo / step) * step;
  for (let v = tickStart; v <= hi; v += step) {
    el("line", { class: "gridline", x1: sx(v), x2: sx(v), y1: margin.top, y2: margin.top + plotH }, svg);
    el("line", { class: "gridline", x1: margin.left, x2: margin.left + plotW, y1: sy(v), y2: sy(v) }, svg);
    const tx = el("text", { class: "tick-label", x: sx(v), y: margin.top + plotH + 18, "text-anchor": "middle" }, svg);
    tx.textContent = v;
    const ty = el("text", { class: "tick-label", x: margin.left - 10, y: sy(v) + 4, "text-anchor": "end" }, svg);
    ty.textContent = v;
  }

  // -- axis labels ----------------------------------------------------
  const xl = el("text", { class: "axis-label", x: margin.left + plotW / 2, y: CONFIG.vbH - 12, "text-anchor": "middle" }, svg);
  xl.textContent = "Expected points per 100 possessions, from 2s";
  const yl = el("text", {
    class: "axis-label", x: 18, y: margin.top + plotH / 2, "text-anchor": "middle",
    transform: `rotate(-90 18 ${margin.top + plotH / 2})`,
  }, svg);
  yl.textContent = "Expected points per 100 possessions, from 3s";

  // -- iso-efficiency diagonal ------------------------------------------
  el("line", { class: "diag", x1: sx(lo), y1: sy(lo), x2: sx(hi), y2: sy(hi) }, svg);
  const labelPos = lo + 0.5 * (hi - lo);
  const dl = el("text", {
    class: "diag-label", x: sx(labelPos), y: sy(labelPos) - 8, "text-anchor": "middle",
  }, svg);
  dl.textContent = "EV(3) = EV(2)";

  // -- markers ------------------------------------------------------------
  const defs = el("defs", {}, svg);
  svg.insertBefore(defs, svg.firstChild);

  const markerLayer = el("g", {}, svg);
  const pointPx = [];
  DATA.forEach((d, i) => {
    const cx = sx(d.ev2), cy = sy(d.ev3);
    pointPx.push([cx, cy]);
    el("g", { id: "m-" + i, "data-i": i }, markerLayer);
  });

  markerLayer.querySelectorAll("g").forEach((g, i) => {
    const d = DATA[i];
    const cx = pointPx[i][0], cy = pointPx[i][1];
    if (d.photo) {
      const r = CONFIG.photoR;
      const clipId = "clip-" + i;
      const clip = el("clipPath", { id: clipId }, defs);
      el("circle", { cx, cy, r: r - 1.2 }, clip);
      el("image", {
        href: d.photo, x: cx - r, y: cy - r, width: r * 2, height: r * 2,
        "clip-path": `url(#${clipId})`, preserveAspectRatio: "xMidYMid slice",
      }, g);
      el("circle", { class: "marker-ring", cx, cy, r, stroke: d.ring }, g);
    } else {
      el("circle", { class: "marker-dot", cx, cy, r: CONFIG.dotR, fill: d.ring, opacity: 0.85 }, g);
    }
    if (d.labeled) {
      const r = d.photo ? CONFIG.photoR : CONFIG.dotR;
      const t = el("text", { class: "marker-label", x: cx + r + 5, y: cy + 4 }, svg);
      t.textContent = d.labelText;
    }
  });

  // -- legend / colorbar ---------------------------------------------------
  if (CONFIG.legend) {
    const lg = el("g", { class: "legend" }, svg);
    CONFIG.legend.forEach((item, i) => {
      const ly = margin.top + 14 + i * 20;
      el("circle", { cx: margin.left + 10, cy: ly, r: 6, fill: "none", stroke: item.color, "stroke-width": 2.4 }, lg);
      const t = el("text", { x: margin.left + 24, y: ly + 4 }, lg);
      t.textContent = item.label;
    });
  }
  if (CONFIG.colorbar) {
    const cbX = margin.left + plotW + 26, cbY = margin.top, cbW = 14, cbH = plotH;
    const gradId = "cb-grad";
    const grad = el("linearGradient", { id: gradId, x1: "0", y1: "1", x2: "0", y2: "0" }, defs);
    el("stop", { offset: "0%", "stop-color": CONFIG.colorbar.lowColor }, grad);
    el("stop", { offset: "100%", "stop-color": CONFIG.colorbar.highColor }, grad);
    el("rect", { x: cbX, y: cbY, width: cbW, height: cbH, fill: `url(#${gradId})` }, svg);
    const lo_t = el("text", { class: "colorbar-label", x: cbX + cbW + 6, y: cbY + cbH - 2 }, svg);
    lo_t.textContent = CONFIG.colorbar.lowLabel;
    const hi_t = el("text", { class: "colorbar-label", x: cbX + cbW + 6, y: cbY + 10 }, svg);
    hi_t.textContent = CONFIG.colorbar.highLabel;
    const mid_t = el("text", { class: "colorbar-label", x: cbX + cbW + 6, y: cbY + cbH / 2 + 4 }, svg);
    mid_t.textContent = "Season";
  }

  // -- hover: nearest point in pixel space --------------------------------
  let hovered = -1;
  function clearHover() {
    if (hovered >= 0) {
      const prev = document.getElementById("m-" + hovered);
      if (prev) prev.querySelectorAll(".marker-ring, .marker-dot").forEach((n) => {
        n.setAttribute("r", n.classList.contains("marker-ring") ? CONFIG.photoR : CONFIG.dotR);
      });
    }
    hovered = -1;
    tooltip.classList.remove("visible");
  }

  svg.addEventListener("pointermove", (evt) => {
    const pt = svg.createSVGPoint();
    pt.x = evt.clientX; pt.y = evt.clientY;
    const loc = pt.matrixTransform(svg.getScreenCTM().inverse());
    let best = -1, bestDist = Infinity;
    for (let i = 0; i < pointPx.length; i++) {
      const dx = pointPx[i][0] - loc.x, dy = pointPx[i][1] - loc.y;
      const dist = dx * dx + dy * dy;
      if (dist < bestDist) { bestDist = dist; best = i; }
    }
    const threshold = CONFIG.hoverThreshold;
    if (best === -1 || bestDist > threshold * threshold) {
      clearHover();
      return;
    }
    if (best !== hovered) {
      clearHover();
      hovered = best;
      const g = document.getElementById("m-" + best);
      g.querySelectorAll(".marker-ring").forEach((n) => n.setAttribute("r", CONFIG.photoR * 1.3));
      g.querySelectorAll(".marker-dot").forEach((n) => n.setAttribute("r", CONFIG.dotR * 1.4));
    }
    const d = DATA[best];
    tooltip.innerHTML = "";
    const name = document.createElement("div"); name.className = "t-name"; name.textContent = d.name;
    const season = document.createElement("div"); season.className = "t-season"; season.textContent = d.season + " — " + d.pts + " pts";
    tooltip.appendChild(name); tooltip.appendChild(season);
    const row1 = document.createElement("div"); row1.className = "t-row";
    row1.appendChild(Object.assign(document.createElement("span"), { textContent: "EV(2) " }));
    row1.lastChild.appendChild(Object.assign(document.createElement("span"), { className: "t-val", textContent: d.ev2 }));
    row1.appendChild(Object.assign(document.createElement("span"), { textContent: "EV(3) " }));
    row1.lastChild.appendChild(Object.assign(document.createElement("span"), { className: "t-val", textContent: d.ev3 }));
    tooltip.appendChild(row1);
    if (d.fgPct !== null || d.threePct !== null) {
      const row2 = document.createElement("div"); row2.className = "t-row";
      if (d.fgPct !== null) {
        row2.appendChild(Object.assign(document.createElement("span"), { textContent: "FG% " }));
        row2.lastChild.appendChild(Object.assign(document.createElement("span"), { className: "t-val", textContent: d.fgPct }));
      }
      if (d.threePct !== null) {
        row2.appendChild(Object.assign(document.createElement("span"), { textContent: "3P% " }));
        row2.lastChild.appendChild(Object.assign(document.createElement("span"), { className: "t-val", textContent: d.threePct }));
      }
      tooltip.appendChild(row2);
    }
    const wrapRect = svg.getBoundingClientRect();
    const scaleX = wrapRect.width / CONFIG.vbW;
    const px = pointPx[best][0] * scaleX;
    const py = pointPx[best][1] * (wrapRect.height / CONFIG.vbH);
    tooltip.style.left = px + "px";
    tooltip.style.top = py + "px";
    tooltip.classList.add("visible");

    // Nudge back on-screen if the (nowrap) tooltip would spill past the
    // container's edge -- common for the highest/lowest scorers, who tend
    // to sit at the extremes of the chart where this matters most.
    const wrapBox = svg.parentElement.getBoundingClientRect();
    const tipBox = tooltip.getBoundingClientRect();
    let dx = 0, dy = 0;
    if (tipBox.left < wrapBox.left) dx = wrapBox.left - tipBox.left;
    if (tipBox.right > wrapBox.right) dx = wrapBox.right - tipBox.right;
    if (tipBox.top < wrapBox.top) dy = wrapBox.top - tipBox.top;
    if (dx !== 0) tooltip.style.left = (px + dx) + "px";
    if (dy !== 0) tooltip.style.top = (py + dy) + "px";
  });
  svg.addEventListener("pointerleave", clearHover);

  // -- data table (non-gating fallback for every value) --------------------
  const tbody = document.querySelector("#data-table tbody");
  const sorted = [...DATA].sort((a, b) => b.pts - a.pts);
  sorted.forEach((d) => {
    const tr = document.createElement("tr");
    const cells = [d.name, d.season, d.pts, d.ev2, d.ev3, d.fgPct ?? "—", d.threePct ?? "—"];
    cells.forEach((c) => {
      const td = document.createElement("td");
      td.textContent = c;
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });
})();
"""


def _safe_json(obj) -> str:
    return json.dumps(obj).replace("</", "<\\/")


def _render_page(title: str, subtitle: str, records: list[dict], lo: float, hi: float,
                  legend: list[dict] | None, colorbar: dict | None) -> str:
    vb_w, vb_h = 900, 700
    span = hi - lo
    tick_step = 5 if span > 20 else 2

    config = {
        "vbW": vb_w, "vbH": vb_h, "lo": lo, "hi": hi, "tickStep": tick_step,
        "photoR": 13, "dotR": 6, "hoverThreshold": 26,
        "legend": legend, "colorbar": colorbar,
    }
    html = _PAGE_TEMPLATE.format(
        title=title, subtitle=subtitle, vb_w=vb_w, vb_h=vb_h, n_points=len(records),
        config_json=_safe_json(config), data_json=_safe_json(records),
        render_script=_RENDER_SCRIPT,
        SURFACE=SURFACE, INK_PRIMARY=INK_PRIMARY, INK_SECONDARY=INK_SECONDARY,
        INK_MUTED=INK_MUTED, GRIDLINE=GRIDLINE, BASELINE=BASELINE,
    )
    return html


def main():
    parser = argparse.ArgumentParser(description="Build interactive HTML versions of the two 'Mega Graph' plots.")
    parser.add_argument("--season", default="2025-26")
    parser.add_argument("--min-fga", type=int, default=200)
    parser.add_argument("--sample-seed", type=int, default=42)
    parser.add_argument("--historic-start", default="1996-97")
    parser.add_argument("--headshots-cache-dir", type=Path, default=Path("data/headshots"))
    args = parser.parse_args()

    if not COMBINED_PATH.exists():
        raise SystemExit(f"{COMBINED_PATH} not found -- run load_kaggle_season_totals.py first.")

    try:
        import player_headshots  # noqa: F401
    except ImportError as e:
        raise SystemExit(f"needs player_headshots.py's dependencies (pip install pillow requests): {e}")

    df = pd.read_csv(COMBINED_PATH)

    current_pool = _current_era_population(df, args.season, args.min_fga, args.sample_seed)
    historic_pool = _historic_population(df, args.historic_start)

    all_ids = set(current_pool["PLAYER_ID"]) | set(historic_pool["PLAYER_ID"])
    photos = _fetch_photo_data_uris(all_ids, args.headshots_cache_dir)
    n_real = sum(1 for v in photos.values() if v is not None)
    log.info("%d/%d unique players got a real photo (rest fall back to a colored dot)", n_real, len(all_ids))

    cur_records, cur_lo, cur_hi = _build_records_current(current_pool, photos)
    cur_html = _render_page(
        title=f"2 vs 3 — {args.season}: {sum(1 for r in cur_records if r['group']=='random')} random players + the 10 highest scorers",
        subtitle=f"{len(cur_records)} players shown",
        records=cur_records, lo=cur_lo, hi=cur_hi,
        legend=[{"label": "Random players (≥%d FGA)" % args.min_fga, "color": BLUE},
                {"label": "10 highest scorers", "color": ORANGE}],
        colorbar=None,
    )
    cur_path = OUT_DIR / f"two_vs_three_{args.season.replace('-', '_')}_interactive.html"
    cur_path.write_text(cur_html, encoding="utf-8")
    print(f"Saved: {cur_path}")

    hist_records, hist_lo, hist_hi, yr_lo, yr_hi = _build_records_historic(historic_pool, photos)
    hist_html = _render_page(
        title=f"2 vs 3 — the 100 highest-scoring player-seasons since {args.historic_start}",
        subtitle=f"{len(hist_records)} player-seasons shown",
        records=hist_records, lo=hist_lo, hi=hist_hi,
        legend=None,
        colorbar={"lowColor": SEQ_LIGHT, "highColor": SEQ_DARK, "lowLabel": str(yr_lo), "highLabel": str(yr_hi)},
    )
    hist_path = OUT_DIR / "two_vs_three_historic_top100_interactive.html"
    hist_path.write_text(hist_html, encoding="utf-8")
    print(f"Saved: {hist_path}")


if __name__ == "__main__":
    main()
