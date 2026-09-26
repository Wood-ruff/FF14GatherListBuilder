import json
from datetime import date, timedelta
from pathlib import Path

CACHE_FILE = Path(__file__).parent / "data" / "item_cache.json"
MAX_AGE_DAYS = 60


def get_fresh_result(item_name):
    """Return the cached result for an item if it is fresh enough, or None."""
    entry = load_cache().get(item_name.lower())
    if not entry:
        return None
    if is_expired(entry["fetchdate"]):
        return None
    return entry["result"]


def store_result(item_name, result):
    """Save one item result with today's date in the cache file."""
    cache = load_cache()
    cache[item_name.lower()] = {
        "fetchdate": date.today().isoformat(),
        "result": result,
    }
    CACHE_FILE.parent.mkdir(exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as file:
        json.dump(cache, file, indent=2)


def is_expired(fetchdate):
    """Check whether a fetch date is older than the maximum cache age."""
    oldest_allowed = date.today() - timedelta(days=MAX_AGE_DAYS)
    return date.fromisoformat(fetchdate) < oldest_allowed


def load_cache():
    """Return the full cache file contents, or an empty dict if it does not exist."""
    if not CACHE_FILE.exists():
        return {}
    with open(CACHE_FILE, encoding="utf-8") as file:
        return json.load(file)
