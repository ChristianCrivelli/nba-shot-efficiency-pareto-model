"""
test_headshots_smoke.py

Run this locally (needs real internet access -- won't work in the
sandbox that wrote this repo's scripts) to sanity-check
player_headshots.py against a handful of real NBA player IDs before
trusting it inside build_2v3_plots.py.

Checks:
  - a recent/current player (should hit and look like a real photo)
  - an older, retired-a-while player (borderline case for CDN coverage)
  - a deliberately bogus ID (should fail gracefully -> None, not a crash)

Usage:
    pip install requests pillow
    python test_headshots_smoke.py
"""

from pathlib import Path

from player_headshots import get_player_thumbnail, looks_like_placeholder, fetch_headshot

# A small, mixed sample: recent star, a player from further back, and a
# deliberately invalid ID. Swap in players relevant to your actual 5
# favorites / historic top-100 once this passes.
TEST_PLAYER_IDS = {
    "LeBron James (current era)": 2544,
    "Kareem Abdul-Jabbar (pre-CDN era, retired 1989)": 76003,
    "Deliberately bogus ID": 999999999,
}

CACHE_DIR = Path("data/headshots_smoke_test")


def main():
    print(f"Testing against cache dir: {CACHE_DIR}\n")
    for label, player_id in TEST_PLAYER_IDS.items():
        print(f"-- {label} (PLAYER_ID={player_id}) --")
        path = fetch_headshot(player_id, cache_dir=CACHE_DIR)
        if path is None:
            print("  No headshot available (404 or fetch error) -- fallback path works as expected.\n")
            continue
        print(f"  Downloaded/cached: {path}")
        if looks_like_placeholder(path):
            print("  WARNING: looks like it might be a generic silhouette placeholder, not a real photo.")
        thumb = get_player_thumbnail(player_id, cache_dir=CACHE_DIR)
        print(f"  Circular thumbnail built: {thumb is not None}\n")

    print("If the current-era player got a real photo and the bogus ID failed gracefully,")
    print("the fetch/cache/crop pipeline works. Check the pre-CDN-era player's result manually")
    print(f"(open {CACHE_DIR}/<player_id>.png) to see whether historic coverage is usable.")


if __name__ == "__main__":
    main()
