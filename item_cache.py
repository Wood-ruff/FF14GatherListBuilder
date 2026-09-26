import json
import shutil
from datetime import date, timedelta
from pathlib import Path

CACHE_FILE = Path(__file__).parent / "data" / "cache" / "item_cache.json"
ICONS_DIR = Path(__file__).parent / "data" / "cache" / "icons"
MAX_AGE_DAYS = 60


def get_fresh_result(name, kind="item"):
    """Return the cached result for a name and kind if it is fresh enough, or None."""
    entry = load_cache().get(cache_key(name, kind))
    if not entry:
        return None
    if is_expired(entry["fetchdate"]):
        return None
    return entry["result"]


def store_result(name, result, kind="item"):
    """Save one result of the given kind with today's date in the cache file."""
    store_results({name: result}, kind)


def store_results(results, kind):
    """Save many results of one kind with today's date in a single write."""
    cache = load_cache()
    for name, result in results.items():
        cache[cache_key(name, kind)] = {
            "fetchdate": date.today().isoformat(),
            "type": kind,
            "result": result,
        }
    save_cache(cache)


def save_cache(cache):
    """Write the full cache contents to the cache file."""
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as file:
        json.dump(cache, file, indent=2)


def cache_key(name, kind):
    """Build the cache key for a name and kind."""
    return f"{kind}:{name.lower()}"


def is_expired(fetchdate):
    """Check whether a fetch date is older than the maximum cache age."""
    oldest_allowed = date.today() - timedelta(days=MAX_AGE_DAYS)
    return date.fromisoformat(fetchdate) < oldest_allowed


def has_icon(game_id):
    """Check whether an icon for the game id is cached."""
    return (ICONS_DIR / f"{game_id}.png").exists()


def store_icon(game_id, png_bytes):
    """Save one icon image in the icon cache."""
    ICONS_DIR.mkdir(parents=True, exist_ok=True)
    (ICONS_DIR / f"{game_id}.png").write_bytes(png_bytes)


def clear():
    """Delete the cache file and all cached icons."""
    if CACHE_FILE.exists():
        CACHE_FILE.unlink()
    if ICONS_DIR.exists():
        shutil.rmtree(ICONS_DIR)


def load_cache():
    """Return the full cache file contents, or an empty dict if it does not exist."""
    if not CACHE_FILE.exists():
        return {}
    with open(CACHE_FILE, encoding="utf-8") as file:
        return json.load(file)
