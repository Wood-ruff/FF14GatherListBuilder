import json
import logging
import shutil
import threading
from datetime import datetime, timedelta
from pathlib import Path

import jsonfile

CACHE_FILE = Path(__file__).parent / "data" / "cache" / "item_cache.json"
ICONS_DIR = Path(__file__).parent / "data" / "cache" / "icons"
MAX_AGE_DAYS = 60

CACHE_LOCK = threading.Lock()
MEMORY = {"path": None, "stamp": None, "cache": None}

FETCH_LOCKS = {}
FETCH_LOCKS_GUARD = threading.Lock()
FETCHES = {"count": 0}


def fetch_lock(name):
    """Return the lock that lets only one fetch of the named data run at a time."""
    with FETCH_LOCKS_GUARD:
        return FETCH_LOCKS.setdefault(name, threading.Lock())


def counted_fetch(lookup):
    """Run one lookup while counting it as a running background fetch."""
    with FETCH_LOCKS_GUARD:
        FETCHES["count"] += 1
    try:
        return lookup()
    finally:
        with FETCH_LOCKS_GUARD:
            FETCHES["count"] -= 1


def fetches_running():
    """Tell whether any counted lookup is currently fetching data."""
    return FETCHES["count"] > 0

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
    """Write the full cache contents to disk and keep the memory copy current."""
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    written = jsonfile.write_json_file(CACHE_FILE, cache)
    MEMORY["cache"] = cache
    MEMORY["path"] = CACHE_FILE
    if written:
        MEMORY["stamp"] = file_stamp()


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
    """Return the cache contents, parsing the file only when it changed on disk."""
    if not CACHE_FILE.exists():
        MEMORY["cache"] = {}
        MEMORY["path"] = CACHE_FILE
        MEMORY["stamp"] = None
        return MEMORY["cache"]
    stamp = file_stamp()
    if MEMORY["cache"] is None or MEMORY["path"] != CACHE_FILE or MEMORY["stamp"] != stamp:
        MEMORY["cache"] = parse_cache_file()
        MEMORY["path"] = CACHE_FILE
        MEMORY["stamp"] = stamp
    return MEMORY["cache"]


def file_stamp():
    """Return the cache file's change marker of modification time and size."""
    stat = CACHE_FILE.stat()
    return (stat.st_mtime_ns, stat.st_size)


def parse_cache_file():
    """Parse the cache file, salvaging what a damaged file still holds."""
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
