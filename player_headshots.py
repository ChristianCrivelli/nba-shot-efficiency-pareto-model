"""
player_headshots.py

Fetches and caches NBA player headshots from the NBA's own CDN, and
crops them into circular thumbnails for use as scatter-plot markers
(see GitHub issue "Add player headshots to 2v3 scatter plots").

The CDN URL is keyed by PLAYER_ID (which season_totals.py already pulls
into every season's CSV) and needs no authentication:

    https://cdn.nba.com/headshots/nba/latest/1040x760/{PLAYER_ID}.png

Validated against real player IDs 2026-09-08 (test_headshots_smoke.py,
run locally -- the sandbox that wrote this module can't reach
cdn.nba.com). Two real findings from that run, both fixed here:

1. The CDN does NOT 404 for an invalid/nonexistent player ID -- it
   returns HTTP 200 with a generic gray silhouette placeholder instead
   (confirmed with a deliberately bogus ID). So "downloaded successfully"
   is not the same as "has a real photo" -- `looks_like_placeholder()`
   is load-bearing, not just a nice-to-have, especially for historic
   players who may predate digital headshot photography.
2. These PNGs are palette-mode images with a real alpha channel (~60%
   of the image is transparent background, confirmed by inspecting the
   raw pixel data), and a naive `.convert("RGB")` silently drops that
   transparency and paints it black instead of leaving it see-through.
   That corrupted both `circular_thumbnail()` (would have stamped plot
   markers with black halos/corners instead of blending cleanly) and an
   earlier version of `looks_like_placeholder()`'s color analysis (which
   is why its first heuristic -- raw single-channel variance -- failed to
   catch the placeholder: with the background misread as black instead of
   white, "black silhouette on black background" reads as low-variance
   AND "black background behind a real photo" reads as high-variance for
   the wrong reason). Both functions below now explicitly composite onto
   white before analyzing/cropping, and `circular_thumbnail()` preserves
   the source alpha (combined with the circular mask) instead of
   discarding it.

`looks_like_placeholder()`'s current heuristic (max saturation + unique
color count after compositing onto white) was empirically validated
against exactly one confirmed placeholder and two confirmed real photos
(LeBron James, Kareem Abdul-Jabbar) -- a real margin, not a coin flip, but
still eyeball a sample of the historic-plot output before trusting it
wholesale, especially for players from well before modern digital
photography.

Usage:
    from player_headshots import get_player_thumbnail, add_headshot_marker

    thumb = get_player_thumbnail(player_id=2544, cache_dir="data/headshots")
    if thumb is not None:
        add_headshot_marker(ax, x, y, thumb, zoom=0.5)
    else:
        ax.scatter([x], [y], ...)  # fall back to a plain marker
"""

import colorsys
import logging
from io import BytesIO
from pathlib import Path
from typing import Optional

import requests
from PIL import Image, ImageChops, ImageDraw

log = logging.getLogger(__name__)

HEADSHOT_URL_TEMPLATE = "https://cdn.nba.com/headshots/nba/latest/1040x760/{player_id}.png"
DEFAULT_CACHE_DIR = Path("data/headshots")
REQUEST_TIMEOUT = 10
MISSING_SENTINEL_SUFFIX = ".missing"  # remembers a 404 so we don't re-request it every run


def _cache_paths(player_id: int, cache_dir: Path) -> tuple[Path, Path]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    image_path = cache_dir / f"{player_id}.png"
    missing_path = cache_dir / f"{player_id}{MISSING_SENTINEL_SUFFIX}"
    return image_path, missing_path


def fetch_headshot(player_id: int, cache_dir: Path = DEFAULT_CACHE_DIR,
                    force: bool = False) -> Optional[Path]:
    """Downloads (or loads from cache) a player's raw headshot PNG.

    Returns the local file path, or None if no headshot is available
    (e.g. a 404 for a pre-photography-era player). Failed lookups are
    remembered with a sentinel file so re-running doesn't re-request the
    same missing player every time -- pass force=True to retry anyway.
    """
    cache_dir = Path(cache_dir)
    image_path, missing_path = _cache_paths(player_id, cache_dir)

    if not force:
        if image_path.exists():
            return image_path
        if missing_path.exists():
            return None

    url = HEADSHOT_URL_TEMPLATE.format(player_id=player_id)
    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT)
        if resp.status_code == 404 or not resp.content:
            missing_path.write_text("404")
            return None
        resp.raise_for_status()
        image_path.write_bytes(resp.content)
        missing_path.unlink(missing_ok=True)
        return image_path
    except Exception as e:  # noqa: BLE001 -- network flakiness shouldn't kill a plot run
        log.warning("Headshot fetch failed for player %s: %s", player_id, e)
        return None


def _composite_on_white(img: Image.Image) -> Image.Image:
    """These CDN PNGs carry real transparency (~60% of the image, per a
    2026-09-08 pixel-level check) -- flattening with .convert("RGB")
    directly paints that transparent region black. Compositing onto an
    opaque white background first gives an accurate picture of what a
    viewer actually sees."""
    rgba = img.convert("RGBA")
    white_bg = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
    return Image.alpha_composite(white_bg, rgba).convert("RGB")


def looks_like_placeholder(image_path: Path) -> bool:
    """Detects the NBA CDN's generic silhouette placeholder (confirmed
    2026-09-08: the CDN returns this with an HTTP 200, not a 404, for a
    nonexistent player ID -- so a successful download alone doesn't mean
    a real photo). Two signals, both required:

    - max_saturation: the placeholder is a flat two-tone (white bg + one
      solid gray fill) vector graphic with essentially zero color, vs.
      0.82+ for a real photo (skin tones, jersey/team colors).
    - n_unique: the placeholder quantizes to ~120 distinct colors in a
      48x48 downsample (mostly anti-aliased edge blends); real photos ran
      600+. Requiring this ALONGSIDE low saturation (not saturation
      alone) means a genuinely black-and-white archival photo -- which
      would have low saturation too -- won't get misflagged: real
      photographic detail still produces hundreds of distinct gray
      shades, unlike this flat graphic.

    Empirically validated against exactly one confirmed placeholder (a
    deliberately bogus player ID) and two confirmed real photos (LeBron
    James, Kareem Abdul-Jabbar) -- a real margin (placeholder: sat=0.06,
    120 colors; reals: sat>=0.82, 600+ colors), not exhaustive. Eyeball a
    sample of real output before trusting this wholesale.
    """
    try:
        flat = _composite_on_white(Image.open(image_path))
        pixels = list(flat.resize((48, 48)).getdata())
        n_unique = len(set(pixels))
        max_saturation = max(colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)[1] for r, g, b in pixels)
        return n_unique < 300 and max_saturation < 0.15
    except Exception:  # noqa: BLE001
        return False


def circular_thumbnail(image_path: Path, size_px: int = 120) -> Optional[Image.Image]:
    """Loads an image and returns a circular-cropped, alpha-masked RGBA
    thumbnail suitable for use as a matplotlib OffsetImage marker.

    Loads as RGBA (not RGB) and keeps the source's own alpha channel --
    these CDN images carry real transparency around the subject (~60% of
    the image, confirmed 2026-09-08), and a naive .convert("RGB") would
    have painted that transparent region solid black, giving every
    headshot marker an ugly black halo/corners on the plot instead of
    blending into the figure background. The final alpha is the circular
    mask AND the source's own alpha combined, so a pixel only shows if
    it's both inside the circle and was actually opaque in the photo."""
    try:
        img = Image.open(image_path).convert("RGBA")
    except Exception as e:  # noqa: BLE001
        log.warning("Could not open headshot %s: %s", image_path, e)
        return None

    # Crop to a centered square first (headshots are usually portrait-ish).
    w, h = img.size
    side = min(w, h)
    left = (w - side) // 2
    top = max(0, (h - side) // 2 - int(side * 0.05))  # bias slightly up to favor the face
    img = img.crop((left, top, left + side, min(h, top + side)))
    img = img.resize((size_px, size_px), Image.LANCZOS)

    circle_mask = Image.new("L", (size_px, size_px), 0)
    ImageDraw.Draw(circle_mask).ellipse((0, 0, size_px, size_px), fill=255)

    r, g, b, src_alpha = img.split()
    final_alpha = ImageChops.multiply(circle_mask, src_alpha)  # 0 outside the circle either way
    return Image.merge("RGBA", (r, g, b, final_alpha))


def get_player_thumbnail(player_id: int, cache_dir: Path = DEFAULT_CACHE_DIR,
                          size_px: int = 120) -> Optional[Image.Image]:
    """One-call convenience: fetch (with cache) + circular-crop. Returns
    None if no usable headshot exists for this player -- callers should
    fall back to a plain marker in that case."""
    path = fetch_headshot(player_id, cache_dir=cache_dir)
    if path is None:
        return None
    return circular_thumbnail(path, size_px=size_px)


def add_headshot_marker(ax, x: float, y: float, thumbnail: Image.Image, zoom: float = 0.5):
    """Places a circular headshot thumbnail at (x, y) on a matplotlib Axes."""
    from matplotlib.offsetbox import AnnotationBbox, OffsetImage

    imagebox = OffsetImage(thumbnail, zoom=zoom)
    imagebox.image.axes = ax
    ab = AnnotationBbox(imagebox, (x, y), frameon=False, pad=0, zorder=4)
    ax.add_artist(ab)
    return ab
