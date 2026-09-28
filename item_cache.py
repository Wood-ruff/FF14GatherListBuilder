import json
import logging
import os
import shutil
import threading
from datetime import datetime, timedelta
from pathlib import Path

CACHE_FILE = Path(__file__).parent / "data" / "cache" / "item_cache.json"
ICONS_DIR = Path(__file__).parent / "data" / "cache" / "icons"
MAX_AGE_DAYS = 60

CACHE_LOCK = threading.Lock()

LOG = logging.getLogger(__name__)


def get_fresh_result(name, kind="item", max_age_hours=None):
    """Return the cached result for a name and kind if it is fresh enough, or None."""
    entry = load_cache().get(cache_key(name, kind))
    return fresh_entry_result(entry, max_age_hours)


def get_fresh_results(names, kind, max_age_hours=None):
    """Return the fresh cached results for many names of one kind in a single read."""
    cache = load_cache()
    results = {}
    for name in names:
        result = fresh_entry_result(cache.get(cache_key(name, kind)), max_age_hours)
        if result is not None:
            results[name] = result
    return results


def fresh_entry_result(entry, max_age_hours):
    """Return one cache entry's result when the entry exists and is fresh."""
    if not entry:
        return None
    if is_expired(entry["fetchdate"], max_age_hours):
        return None
    return entry["result"]


def store_result(name, result, kind="item"):
    """Save one result of the given kind with today's date in the cache file."""
    store_results({name: result}, kind)


def store_results(results, kind):
    """Save many results of one kind with today's date in a single write."""
    with CACHE_LOCK:
        cache = read_cache_file()
        for name, result in results.items():
            cache[cache_key(name, kind)] = {
                "fetchdate": datetime.now().isoformat(),
                "type": kind,
                "result": result,
            }
        save_cache(cache)


def save_cache(cache):
    """Write the full cache contents to a temp file and swap it in atomically."""
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    temp_file = CACHE_FILE.with_suffix(".tmp")
    with open(temp_file, "w", encoding="utf-8") as file:
        json.dump(cache, file, indent=2)
    os.replace(temp_file, CACHE_FILE)


def cache_key(name, kind):
    """Build the cache key for a name and kind."""
    return f"{kind}:{name.lower()}"


def is_expired(fetchdate, max_age_hours=None):
    """Check whether a fetch date is older than the allowed age."""
    if max_age_hours is None:
        max_age_hours = MAX_AGE_DAYS * 24
    oldest_allowed = datetime.now() - timedelta(hours=max_age_hours)
    return datetime.fromisoformat(fetchdate) < oldest_allowed


def has_icon(game_id):
    """Check whether an icon for the game id is cached."""
    return (ICONS_DIR / f"{game_id}.png").exists()


def store_icon(game_id, png_bytes):
    """Save one icon image in the icon cache."""
    ICONS_DIR.mkdir(parents=True, exist_ok=True)
    (ICONS_DIR / f"{game_id}.png").write_bytes(png_bytes)


def clear():
    """Delete the cache file and all cached icons."""
    with CACHE_LOCK:
        if CACHE_FILE.exists():
            CACHE_FILE.unlink()
    if ICONS_DIR.exists():
        shutil.rmtree(ICONS_DIR)


def load_cache():
    """Return the full cache file contents, or an empty dict if it does not exist."""
    with CACHE_LOCK:
        return read_cache_file()


def read_cache_file():
    """Parse the cache file, salvaging what a damaged file still holds."""
    if not CACHE_FILE.exists():
        return {}
    with open(CACHE_FILE, encoding="utf-8") as file:
        text = file.read()
    try:
        return json.loads(text)
    except ValueError:
        return salvage_cache(text)


def salvage_cache(text):
    """Return the first complete json document in the text, or an empty dict."""
    LOG.warning("cache file is damaged, salvaging its readable part")
    try:
        cache, _rest = json.JSONDecoder().raw_decode(text)
    except ValueError:
        return {}
    if not isinstance(cache, dict):
        return {}
    return cache
