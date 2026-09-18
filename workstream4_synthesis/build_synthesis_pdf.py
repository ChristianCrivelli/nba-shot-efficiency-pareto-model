"""
build_synthesis_pdf.py

Renders synthesis_and_strategy.md (workstream 4's write-up) as a
polished, coaching-facing PDF -- the project's stated audience is head
coaches, analytics departments, and player-development teams (see
project_description.md), and a markdown file in a git repo isn't
something any of those people are going to open. This script re-sets the
same content as a proper document: a cover page, the three findings with
their supporting charts embedded inline, the caveats, and the workstream
status table.

Not a markdown-to-PDF converter -- the section text below is transcribed
by hand from synthesis_and_strategy.md so the PDF can be laid out
properly (mixed portrait/landscape pages for the wide zone-heatmap
charts, a real title page, a formatted formula callout). If
synthesis_and_strategy.md changes, this file's SECTION_* content needs
to be updated to match -- it is not read at build time.

Repo layout (as of the 2026-09-17 reorganization): this script lives in
workstream4_synthesis/ alongside synthesis_and_strategy.md. It reads its
three source charts from outputs/ at the repo root (built by
workstream1_zones/build_zone_heatmaps.py and this folder's own
build_breakeven_trend.py) and writes the finished PDF back into this
same workstream4_synthesis/ folder, next to the markdown it's based on.
Paths are resolved relative to the repo root via REPO_ROOT, not the
current working directory.

Usage:
    python build_synthesis_pdf.py
"""

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame, NextPageTemplate, PageBreak,
    Paragraph, Spacer, Image, Table, TableStyle, KeepTogether, HRFlowable,
)
from reportlab.pdfgen import canvas as pdfcanvas

REPO_ROOT = Path(__file__).resolve().parents[1]

OUTPUTS_DIR = REPO_ROOT / "outputs"
OUT_PATH = REPO_ROOT / "workstream4_synthesis" / "synthesis_and_strategy.pdf"

# -- palette: same validated palette as every chart in this project --------
INK_PRIMARY = colors.HexColor("#0b0b0b")
INK_SECONDARY = colors.HexColor("#52514e")
INK_MUTED = colors.HexColor("#898781")
GRIDLINE = colors.HexColor("#e1e0d9")
BASELINE = colors.HexColor("#c3c2b7")
BLUE = colors.HexColor("#2a78d6")
ORANGE = colors.HexColor("#eb6834")
GOLD = colors.HexColor("#c98500")
RED = colors.HexColor("#d03b3b")
PANEL_BG = colors.HexColor("#f5f4f0")

PAGE_W, PAGE_H = LETTER
MARGIN = 0.85 * inch

# ---------------------------------------------------------------------------
# Styles
# ---------------------------------------------------------------------------

def _styles():
    s = {}
    s["CoverTitle"] = ParagraphStyle(
        "CoverTitle", fontName="Helvetica-Bold", fontSize=27, leading=32,
        textColor=INK_PRIMARY, spaceAfter=10,
    )
    s["CoverSubtitle"] = ParagraphStyle(
        "CoverSubtitle", fontName="Helvetica", fontSize=14.5, leading=20,
        textColor=INK_SECONDARY, spaceAfter=4,
    )
    s["CoverMeta"] = ParagraphStyle(
        "CoverMeta", fontName="Helvetica", fontSize=10.5, leading=15,
        textColor=INK_MUTED,
    )
    s["CoverLede"] = ParagraphStyle(
        "CoverLede", fontName="Helvetica", fontSize=11.5, leading=17,
        textColor=INK_SECONDARY, spaceBefore=26,
    )
    s["H1"] = ParagraphStyle(
        "H1", fontName="Helvetica-Bold", fontSize=16.5, leading=20,
        textColor=INK_PRIMARY, spaceBefore=6, spaceAfter=10,
    )
    s["H1Number"] = ParagraphStyle(
        "H1Number", fontName="Helvetica-Bold", fontSize=10, leading=14,
        textColor=ORANGE, spaceBefore=0, spaceAfter=2,
    )
    s["Body"] = ParagraphStyle(
        "Body", fontName="Helvetica", fontSize=10.3, leading=15.4,
        textColor=INK_PRIMARY, spaceAfter=9, alignment=TA_LEFT,
    )
    s["BodyMuted"] = ParagraphStyle(
        "BodyMuted", parent=s["Body"], textColor=INK_SECONDARY, fontSize=9.7,
    )
    s["Bullet"] = ParagraphStyle(
        "Bullet", parent=s["Body"], leftIndent=16, bulletIndent=4, spaceAfter=8,
    )
    s["FormulaBox"] = ParagraphStyle(
        "FormulaBox", fontName="Courier-Bold", fontSize=13, leading=18,
        textColor=INK_PRIMARY, alignment=TA_CENTER,
    )
    s["CaptionLabel"] = ParagraphStyle(
        "CaptionLabel", fontName="Helvetica-Bold", fontSize=9.5, leading=13,
        textColor=INK_SECONDARY, spaceBefore=6, spaceAfter=2,
    )
    s["CaptionBody"] = ParagraphStyle(
        "CaptionBody", fontName="Helvetica", fontSize=9, leading=12.5,
        textColor=INK_MUTED, spaceAfter=10,
    )
    s["TableCell"] = ParagraphStyle(
        "TableCell", fontName="Helvetica", fontSize=9, leading=12.5,
        textColor=INK_PRIMARY,
    )
    s["TableCellBold"] = ParagraphStyle(
        "TableCellBold", parent=s["TableCell"], fontName="Helvetica-Bold",
    )
    return s


STYLES = _styles()


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def h1(number, title):
    return [
        Paragraph(number, STYLES["H1Number"]),
        Paragraph(title, STYLES["H1"]),
    ]


def para(text):
    return Paragraph(text, STYLES["Body"])


def bullet(text):
    return Paragraph(f'<bullet>&bull;</bullet>{text}', STYLES["Bullet"])


def rule(color=GRIDLINE, thickness=0.75, space_before=4, space_after=14):
    return HRFlowable(width="100%", thickness=thickness, color=color,
                       spaceBefore=space_before, spaceAfter=space_after)


def chart_image(path, max_width, max_height=None):
    from PIL import Image as PILImage
    with PILImage.open(path) as im:
        w_px, h_px = im.size
    aspect = h_px / w_px
    w = max_width
    h = w * aspect
    if max_height is not None and h > max_height:
        h = max_height
        w = h / aspect
    return Image(str(path), width=w, height=h)


def caption(label, body):
    return [
        Paragraph(label, STYLES["CaptionLabel"]),
        Paragraph(body, STYLES["CaptionBody"]),
    ]


# ---------------------------------------------------------------------------
# Page templates (portrait body pages + landscape chart pages)
# ---------------------------------------------------------------------------

def _portrait_decorations(c: pdfcanvas.Canvas, doc):
    c.saveState()
    c.setStrokeColor(GRIDLINE)
    c.setLineWidth(0.5)
    c.line(MARGIN, PAGE_H - 0.55 * inch, PAGE_W - MARGIN, PAGE_H - 0.55 * inch)
    c.setFont("Helvetica", 8)
    c.setFillColor(INK_MUTED)
    c.drawString(MARGIN, PAGE_H - 0.48 * inch, "The 2-vs-3 Break-Even Frontier")
    c.drawRightString(PAGE_W - MARGIN, PAGE_H - 0.48 * inch, "Synthesis & Strategy")
    c.setFont("Helvetica", 8)
    c.drawCentredString(PAGE_W / 2, 0.5 * inch, f"{doc.page}")
    c.restoreState()


def _landscape_decorations(c: pdfcanvas.Canvas, doc):
    w, h = landscape(LETTER)
    c.saveState()
    c.setFont("Helvetica", 8)
    c.setFillColor(INK_MUTED)
    c.drawCentredString(w / 2, 0.45 * inch, f"{doc.page}")
    c.restoreState()


def build_doc(out_path: Path):
    doc = BaseDocTemplate(
        str(out_path), pagesize=LETTER,
        leftMargin=MARGIN, rightMargin=MARGIN, topMargin=0.95 * inch, bottomMargin=0.8 * inch,
        title="The 2-vs-3 Break-Even Frontier — Synthesis & Strategy",
        author="Pareto 2v3 shot-selection model",
    )
    lw, lh = landscape(LETTER)
    l_margin = 0.6 * inch

    portrait_frame = Frame(MARGIN, doc.bottomMargin, PAGE_W - 2 * MARGIN,
                            PAGE_H - doc.topMargin - doc.bottomMargin, id="portrait")
    cover_frame = Frame(MARGIN, doc.bottomMargin, PAGE_W - 2 * MARGIN,
                         PAGE_H - doc.bottomMargin - 1.6 * inch, id="cover")
    landscape_frame = Frame(l_margin, 0.7 * inch, lw - 2 * l_margin, lh - 1.3 * inch, id="landscape")

    doc.addPageTemplates([
        PageTemplate(id="Cover", frames=[cover_frame], pagesize=LETTER),
        PageTemplate(id="Portrait", frames=[portrait_frame], pagesize=LETTER,
                     onPage=_portrait_decorations),
        PageTemplate(id="Landscape", frames=[landscape_frame], pagesize=landscape(LETTER),
                     onPage=_landscape_decorations),
    ])
    return doc


# ---------------------------------------------------------------------------
# Content
# ---------------------------------------------------------------------------

def build_story(content_width):
    story = []

    # -- Cover page ----------------------------------------------------
    story.append(Spacer(1, 1.7 * inch))
    story.append(Paragraph("The 2-vs-3<br/>Break-Even Frontier", STYLES["CoverTitle"]))
    story.append(HRFlowable(width=1.4 * inch, thickness=2.2, color=ORANGE,
                             spaceBefore=6, spaceAfter=16, hAlign="LEFT"))
    story.append(Paragraph("Synthesis &amp; Strategy — Workstream 4", STYLES["CoverSubtitle"]))
    story.append(Paragraph("A coaching briefing from the Pareto 2v3 shot-selection model",
                            STYLES["CoverSubtitle"]))
    story.append(Spacer(1, 0.5 * inch))
    story.append(Paragraph(
        "This is the project's final write-up, pulling together the break-even math "
        "from workstream 3, the population-level “Mega Graph” from workstream 2, and "
        "the zone-level frontiers from workstream 1 into one conclusion. It states the "
        "findings, not how they were built — working notes and methodology detail for "
        "all four workstreams live in the project's <font face=\"Courier\">report.md</font> "
        "and its decisions log.",
        STYLES["CoverLede"]))
    story.append(Spacer(1, 0.35 * inch))
    story.append(Paragraph(
        "Prepared for head coaches, analytics departments, and player-development teams.",
        STYLES["CoverMeta"]))
    story.append(NextPageTemplate("Portrait"))
    story.append(PageBreak())

    # -- The core relationship ------------------------------------------
    story += h1("", "The core relationship")
    story.append(para(
        "A 2-point shot made at rate p2 and a 3-point shot made at rate p3 produce the "
        "same expected points when 2×p2 = 3×p3 — so the break-even 2-point percentage, "
        "for any given 3-point percentage, is:"
    ))
    formula_table = Table(
        [[Paragraph("FG2%<sub>break-even</sub> = 1.5 × FG3%", STYLES["FormulaBox"])]],
        colWidths=[content_width],
    )
    formula_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), PANEL_BG),
        ("BOX", (0, 0), (-1, -1), 0.75, GRIDLINE),
        ("TOPPADDING", (0, 0), (-1, -1), 14),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
    ]))
    story.append(Spacer(1, 4))
    story.append(formula_table)
    story.append(Spacer(1, 10))
    story.append(para(
        "Below that line, the average 2 is a worse bet than the average 3, points per "
        "shot. Above it, the reverse. This single relationship is the thread running "
        "through all three findings below."
    ))
    story.append(rule())

    # -- Finding 1 --------------------------------------------------------
    story += h1("FINDING 1", "The league didn't clear its own break-even line until 2021-22")
    story.append(para(
        "Applying the formula above to actual league-wide shooting each season turns up "
        "a specific, countable answer to “how the frontier has moved outward across "
        "eras” — and it's not the answer the modern “Moreyball” narrative would suggest."
    ))
    story.append(para(
        "League-wide 3-point percentage has been remarkably flat for three decades: "
        "34–37% every single season from 1996-97 through 2025-26, no real trend up or "
        "down. What moved was the volume (3-point attempts rose from 21% of all field "
        "goal attempts in 1996-97 to 41–42% in the most recent two seasons — teams "
        "shooting roughly twice as many 3s per shot attempt as they did at the start of "
        "this dataset) and, more consequentially for this specific question, league-wide "
        "2-point percentage: it climbed steadily, from 46–48% in the late 1990s to "
        "54–55% in 2022–2026, as the long, contested mid-range jumper — the shot the "
        "“Moreyball” case was actually built against — was phased out of the league's "
        "shot diet in favor of shots at the rim."
    ))
    story.append(para(
        "The two lines (actual 2PT%, and 1.5× that season's 3PT%) don't cross until "
        "<b>2021-22</b>. For every season from 1996-97 through 2020-21, the league's actual "
        "2-point percentage sat <i>below</i> its own break-even line — meaning that, in "
        "aggregate, the league would have scored more efficiently by taking more 3s and "
        "fewer 2s for essentially this entire span, even as teams were visibly moving in "
        "that direction the whole time. Only in the last handful of seasons has 2-point "
        "shooting improved enough, in aggregate, to actually justify the volume of 2s "
        "still being taken — and even then narrowly and not every season (2023-24 dipped "
        "back 0.2 points below the line)."
    ))
    fig1 = [chart_image(OUTPUTS_DIR / "breakeven_trend.png", content_width)]
    fig1 += caption(
        "Figure 1. League-wide FG2% vs. that season's break-even line (top), and 3-point "
        "attempt rate (bottom), 1996-97 through 2025-26.",
        "Source: data/breakeven_trend.csv, built by "
        "workstream4_synthesis/build_breakeven_trend.py from the same season totals "
        "workstream 2's Mega Graph uses.",
    )
    story.append(KeepTogether(fig1))
    story.append(para(
        "The practical read: the league-wide shift toward 3-point volume over the last "
        "15 years wasn't chasing a moving break-even target — the target barely moved, "
        "because 3-point percentage itself barely moved. It was teams improving the "
        "<i>quality</i> of the 2s they still took (fewer long twos, more rim shots) that "
        "eventually caught the break-even line up to where 3-point volume already was."
    ))
    story.append(PageBreak())

    # -- Finding 2 --------------------------------------------------------
    story += h1("FINDING 2", "“Pareto-efficient” is not the same as “a good shot”")
    story.append(para(
        "Workstream 1's zone-level frontiers are the natural zone-level counterpart to "
        "Finding 1, and they surface a distinction worth stating plainly before drawing "
        "any coaching conclusion from them: a zone is “Pareto-efficient” here because "
        "<i>no other zone beats it on both expected points and risk at once</i> — not "
        "because it's a high-value shot in absolute terms. A low-risk, low-return zone "
        "can sit on the frontier perfectly legitimately, as the anchor at the safe end, "
        "without being a shot anyone should actually want more of."
    ))
    story.append(para(
        "That distinction matters because it's exactly what shows up in the non-RA "
        "(“jump shots only”) cut: <b>mid-range zones are Pareto-efficient 20 of 30 "
        "times</b> across the league average and the 5 named players — a surprisingly "
        "high rate, given the mid-range shot's reputation as the analytics era's "
        "designated inefficient shot. They're on the frontier because they're often the "
        "<i>lowest-risk</i> jump shot available, not because they're a good bet — every "
        "mid-range zone in this dataset has a lower expected value than the best "
        "available 3-point zone for that same player. The frontier includes them at the "
        "low-risk end the same way it includes Restricted Area at the low-risk end of "
        "the full frontier."
    ))
    story.append(para("Two findings that <i>do</i> translate directly into “take more / fewer of these”:"))
    story.append(bullet(
        "<b>“Above the Break 3” is never independently efficient once Restricted Area "
        "is in play</b> (0 of 18 full-frontier cells, across every entity) — it's always "
        "dominated by the rim. That's expected and not actionable on its own; it's the "
        "“duh, layups are good” restatement of the whole exercise."
    ))
    story.append(bullet(
        "<b>Corner-3 is the strongest non-rim option, but only for shooters who can "
        "actually hit it.</b> League-wide, both corners sit on the non-RA frontier with "
        "the highest expected value of any jump-shot zone. Per player, though, this "
        "splits hard: Stephen Curry's corner-3 numbers (1.57–1.67 points/shot) are elite "
        "and clearly worth hunting; Giannis Antetokounmpo has essentially no corner-3 "
        "shot at all — 3 attempts (all missed) from the left corner and none from the "
        "right in this dataset — not “inefficient” so much as “not part of his shot "
        "profile,” which is itself the finding for a player like him (see Finding 3)."
    ))
    landscape_w, landscape_h = landscape(LETTER)
    l_margin = 0.6 * inch
    landscape_frame_w = landscape_w - 2 * l_margin
    landscape_frame_h = landscape_h - 1.3 * inch - 1.1 * inch  # leave room for the caption below

    story.append(NextPageTemplate("Landscape"))
    story.append(PageBreak())
    fig2 = [chart_image(OUTPUTS_DIR / "zone_efficiency_full.png", landscape_frame_w, landscape_frame_h)]
    fig2 += caption(
        "Figure 2. Zone-level Pareto frontier, full court — League Average and the 5 "
        "named players. Gold = efficient, red = dominated, gray = excluded (heaves).",
        "Source: data/zone_efficiency.csv, 2023-24 shot-location data. Restricted Area "
        "included — the rim predictably dominates almost everything else.",
    )
    story.append(KeepTogether(fig2))
    story.append(PageBreak())
    fig3 = [chart_image(OUTPUTS_DIR / "zone_efficiency_nonra.png", landscape_frame_w, landscape_frame_h)]
    fig3 += caption(
        "Figure 3. Zone-level Pareto frontier, non-RA cut — Restricted Area excluded to "
        "isolate the real jump-shot tradeoff among mid-range, corner-3, and "
        "above-the-break-3 zones.",
        "Source: data/zone_efficiency.csv, 2023-24 shot-location data.",
    )
    story.append(KeepTogether(fig3))
    story.append(NextPageTemplate("Portrait"))
    story.append(PageBreak())

    # -- Finding 3 --------------------------------------------------------
    story += h1("FINDING 3", "The 5 players split into distinct shapes, not one archetype")
    story.append(bullet(
        "<b>Stephen Curry</b> is the one player in this group whose non-rim shot "
        "selection actually matches the league-wide “shoot more 3s” prescription at the "
        "individual level: his right-corner 3 (1.67 EV) is his single most valuable "
        "efficient zone, clearing even his own Restricted Area number (1.28) — a rarity "
        "in this dataset, where the rim usually tops every player's frontier outright. "
        "His mid-range zones (0.59–0.68) sit well below both. For him, the break-even "
        "math and his actual shot profile are already aligned."
    ))
    story.append(bullet(
        "<b>LeBron James and Luka Doncic</b> both still get real value at the rim (1.47 "
        "and 1.52 EV) but differ from there. LeBron's right-corner 3 (1.70 EV, 23 "
        "attempts) actually <i>out-values</i> his own rim number and is Pareto-efficient "
        "on the full frontier right alongside it — a genuine “shoot more of this "
        "specific shot” finding. Luka's frontier is different: Restricted Area is his "
        "<i>only</i> full-frontier zone (every one of his 3-point zones is dominated once "
        "the rim is in the comparison), and only once Restricted Area is set aside does "
        "a best non-rim option emerge — right-side above-the-break 3 (1.24 EV). Two "
        "players who both finish well at the rim, but only one of them has a 3-point "
        "zone that stands on its own merits rather than just being “the best of what's "
        "left.”"
    ))
    story.append(bullet(
        "<b>Nikola Jokic</b> is the outlier finding of the whole workstream: his "
        "non-restricted-area paint shots (73% FG, 1.47 EV) <i>beat</i> his own Restricted "
        "Area number (70%, 1.40 EV) in this dataset — on only 15 attempts, flagged "
        "accordingly, but a real enough gap to be worth a team's own larger-sample "
        "follow-up rather than dismissing outright."
    ))
    story.append(bullet(
        "<b>Giannis Antetokounmpo</b> is the clearest “one shot, everything else is a "
        "discount” profile of the five: Restricted Area (1.55 EV) towers over every "
        "zone he takes, and none of them are close — not because he barely shoots 3s "
        "(his above-the-break attempts, 120 combined across three sub-zones, are real "
        "volume) but because none of them work: 0.74–0.95 EV, all dominated. His corners "
        "are where “near-empty” actually applies — 3 attempts (all missed) from the "
        "left, none at all from the right in this dataset. There's no zone-efficiency "
        "argument for him to shoot more 3s from this data — the argument, if there is "
        "one, is about generating more shots at the rim in the first place, which is "
        "outside what a shot-selection frontier can speak to."
    ))
    story.append(rule())

    # -- Caveats -----------------------------------------------------------
    story += h1("", "Caveats — read before acting on any of the above")
    story.append(bullet(
        "<b>League averages mask individual variance.</b> Finding 1 is a league-wide "
        "aggregate; it says nothing about whether <i>your</i> team's or <i>your</i> "
        "player's 2-point shooting has cleared its own break-even line. The same math "
        "applies at any level — team, player, even single game — but the numbers above "
        "are the league only."
    ))
    story.append(bullet(
        "<b>Season mismatch between workstreams.</b> Finding 1 uses 1996-97 through "
        "2025-26 season totals. Finding 2 and Finding 3 use 2023-24 shot-location data "
        "only — the one season with real zone-level data in this project. They're not "
        "describing the same year, and shouldn't be read as a single unified season "
        "snapshot."
    ))
    story.append(bullet(
        "<b>No defense, shot clock, or shot-creation difficulty in this model.</b> A "
        "“Pareto-efficient” zone is efficient conditional on a shot from there actually "
        "being available on a given possession — it says nothing about how hard that "
        "shot is to generate, who's guarding it, or what happens to these numbers under "
        "playoff-level defensive attention."
    ))
    story.append(bullet(
        "<b>Small samples are flagged, not fixed.</b> Several of the per-player zone "
        "numbers above (Jokic's paint-left, LeBron's several under-20-attempt zones, "
        "both of Giannis's corner-3 splits) rest on fewer than 20 shots for that "
        "player-zone combination in a single season. They're real numbers from real "
        "data, not typos or bugs, but they carry real sampling uncertainty that a full "
        "season-over-season average would substantially narrow."
    ))
    story.append(bullet(
        "<b>The portfolio framing is a simplification.</b> Treating each shot as an "
        "independent, one-shot risk/return draw is the framing the whole project is "
        "built on, and it's a reasonable one for this kind of analysis — but it doesn't "
        "capture second-order effects like offensive rebounding rates by shot type, "
        "free-throw generation, or how a team's shot profile affects its opponent's "
        "transition opportunities."
    ))
    story.append(rule())

    # -- Status table --------------------------------------------------
    story += h1("", "Where this leaves the four workstreams")
    rows = [
        [Paragraph("#", STYLES["TableCellBold"]), Paragraph("Workstream", STYLES["TableCellBold"]),
         Paragraph("Status", STYLES["TableCellBold"])],
        ["1", Paragraph("Efficient Zones + Players", STYLES["TableCell"]),
         Paragraph("Done — zone-level Pareto heatmaps", STYLES["TableCell"])],
        ["2", Paragraph("Mega Graph + Efficiency Gap", STYLES["TableCell"]),
         Paragraph("Done — static + interactive scatter plots", STYLES["TableCell"])],
        ["3", Paragraph("2 vs 3 (core scatter + break-even relation)", STYLES["TableCell"]),
         Paragraph("Done — folded into workstreams 1, 2, and 4", STYLES["TableCell"])],
        ["4", Paragraph("Synthesis &amp; Strategy", STYLES["TableCell"]),
         Paragraph("Done — this document", STYLES["TableCell"])],
    ]
    tbl = Table(rows, colWidths=[0.35 * inch, 2.6 * inch, content_width - 2.95 * inch])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), INK_PRIMARY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PANEL_BG]),
        ("GRID", (0, 0), (-1, -1), 0.5, GRIDLINE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 12))
    story.append(Paragraph(
        "All four are now built. <font face=\"Courier\">report.md</font> remains the "
        "working methodology notes; the project decisions log has the full "
        "session-by-session history of what was tried, what changed, and why.",
        STYLES["BodyMuted"]))

    return story


def main():
    for f in ["breakeven_trend.png", "zone_efficiency_full.png", "zone_efficiency_nonra.png"]:
        p = OUTPUTS_DIR / f
        if not p.exists():
            raise SystemExit(f"missing {p} -- run the workstream 1/4 build scripts first.")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    content_width = PAGE_W - 2 * MARGIN
    doc = build_doc(OUT_PATH)
    story = build_story(content_width)
    doc.build(story)
    print(f"Saved: {OUT_PATH} ({OUT_PATH.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
