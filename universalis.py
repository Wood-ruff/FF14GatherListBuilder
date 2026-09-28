import logging
from concurrent.futures import ThreadPoolExecutor

import requests

import item_cache

WORLDS_URL = "https://universalis.app/api/v2/worlds"
MARKETABLE_URL = "https://universalis.app/api/v2/marketable"
MARKET_URL = "https://universalis.app/api/v2"

CHUNK_SIZE = 25
OVERVIEW_CHUNK_SIZE = 100
LISTINGS_CHUNK_SIZE = 100
CHUNK_WORKERS = 3
MARKET_TTL_HOURS = 3
LISTING_LIMIT = 50
HISTORY_WINDOW_SECONDS = 7 * 24 * 3600
MAX_HISTORY_ENTRIES = 100
STAT_KEYS = ("price", "avg_price", "min_sale", "max_sale", "week_volume")

LOG = logging.getLogger(__name__)


def fetch_worlds():
    """Return all game worlds as id and name pairs, cached."""
    with item_cache.fetch_lock("universalis_worlds"):
        cached = item_cache.get_fresh_result("all", "universalis_worlds")
        if cached is not None:
            return cached
        worlds = item_cache.counted_fetch(lambda: get_json(WORLDS_URL, None))
        if worlds is None:
            return None
        item_cache.store_result("all", worlds, "universalis_worlds")
        return worlds


def fetch_marketable_ids():
    """Return the ids of all items tradable on the market board, cached."""
    with item_cache.fetch_lock("universalis_marketable"):
        cached = item_cache.get_fresh_result("all", "universalis_marketable")
        if cached is None:
            cached = item_cache.counted_fetch(lambda: get_json(MARKETABLE_URL, None))
            if cached is None:
                return None
            item_cache.store_result("all", cached, "universalis_marketable")
        return set(cached)


def fetch_market_stats(world_id, item_ids):
    """Return market prices and week volume per item id, cached for a few hours."""
    with item_cache.fetch_lock(f"market_stats:{world_id}"):
        cached = item_cache.get_fresh_results(
            [stats_key(world_id, item_id) for item_id in item_ids], "market_stats", MARKET_TTL_HOURS
        )
        stats = {}
        missing = []
        for item_id in item_ids:
            known = cached.get(stats_key(world_id, item_id))
            if known is None or any(key not in known for key in STAT_KEYS):
                missing.append(item_id)
            else:
                stats[item_id] = known
        fetched = fetch_chunks(missing, CHUNK_SIZE,
                               lambda chunk: lookup_market_stats_with_retry(world_id, chunk))
        if fetched is None:
            return None
        stats.update(fetched)
        return stats


def fetch_market_overview(world_id, item_ids):
    """Return the lowest price and daily sale speed per item id, cached for a few hours."""
    with item_cache.fetch_lock(f"market_overview:{world_id}"):
        cached = item_cache.get_fresh_results(
            [stats_key(world_id, item_id) for item_id in item_ids], "market_overview", MARKET_TTL_HOURS
        )
        overview = {}
        missing = []
        for item_id in item_ids:
            known = cached.get(stats_key(world_id, item_id))
            if known is None or "price" not in known or "velocity" not in known:
                missing.append(item_id)
            else:
                overview[item_id] = known
        fetched = fetch_chunks(missing, OVERVIEW_CHUNK_SIZE,
                               lambda chunk: lookup_market_overview_with_retry(world_id, chunk))
        if fetched is None:
            return None
        overview.update(fetched)
        return overview


def fetch_market_listings(world_id, item_ids):
    """Return the cheapest current listings per item id, cached for a few hours."""
    with item_cache.fetch_lock(f"market_listings:{world_id}"):
        cached = item_cache.get_fresh_results(
            [stats_key(world_id, item_id) for item_id in item_ids], "market_listings", MARKET_TTL_HOURS
        )
        listings = {}
        missing = []
        for item_id in item_ids:
            known = cached.get(stats_key(world_id, item_id))
            if known is None:
                missing.append(item_id)
            else:
                listings[item_id] = known
        fetched = fetch_chunks(missing, LISTINGS_CHUNK_SIZE,
                               lambda chunk: lookup_market_listings_with_retry(world_id, chunk))
        if fetched is None:
            return None
        listings.update(fetched)
        return listings


def lookup_market_listings_with_retry(world_id, item_ids):
    """Fetch one chunk of market listings, trying a second time when the api hiccups."""
    fetched = lookup_market_listings(world_id, item_ids)
    if fetched is None:
        fetched = lookup_market_listings(world_id, item_ids)
    return fetched


def lookup_market_listings(world_id, item_ids):
    """Fetch the cheapest listings of up to one chunk of items in one call."""
    joined = ",".join(str(item_id) for item_id in item_ids)
    data = get_json(f"{MARKET_URL}/{world_id}/{joined}", {
        "listings": LISTING_LIMIT,
        "entries": 0,
    })
    if data is None:
        return None
    rows = data.get("items")
    if rows is None:
        rows = {str(data.get("itemID")): data}
    listings = {}
    for item_id in item_ids:
        listings[item_id] = build_listings(rows.get(str(item_id)))
    item_cache.store_results(
        {stats_key(world_id, item_id): entry for item_id, entry in listings.items()}, "market_listings"
    )
    return listings


def build_listings(fields):
    """Reduce one market data row to its price and quantity pairs, cheapest first."""
    if fields is None:
        return []
    pairs = [[listing["pricePerUnit"], listing["quantity"]]
             for listing in fields.get("listings", [])]
    pairs.sort()
    return pairs


def fetch_chunks(item_ids, size, lookup_chunk):
    """Fetch the ids in parallel chunks and merge the results, None when one fails."""
    if not item_ids:
        return {}
    results = {}
    with ThreadPoolExecutor(max_workers=CHUNK_WORKERS) as pool:
        for fetched in pool.map(lookup_chunk, chunked(item_ids, size)):
            if fetched is None:
                return None
            results.update(fetched)
    return results


def lookup_market_stats_with_retry(world_id, item_ids):
    """Fetch one chunk of market stats, trying a second time when the api hiccups."""
    fetched = lookup_market_stats(world_id, item_ids)
    if fetched is None:
        fetched = lookup_market_stats(world_id, item_ids)
    return fetched


def lookup_market_overview_with_retry(world_id, item_ids):
    """Fetch one chunk of market overviews, trying a second time when the api hiccups."""
    fetched = lookup_market_overview(world_id, item_ids)
    if fetched is None:
        fetched = lookup_market_overview(world_id, item_ids)
    return fetched


def lookup_market_overview(world_id, item_ids):
    """Fetch price and sale speed of up to one chunk of items in one aggregated call."""
    joined = ",".join(str(item_id) for item_id in item_ids)
    data = get_json(f"{MARKET_URL}/aggregated/{world_id}/{joined}", None)
    if data is None:
        return None
    rows = {row["itemId"]: row for row in data.get("results", [])}
    overview = {}
    for item_id in item_ids:
        overview[item_id] = build_overview(rows.get(item_id))
    item_cache.store_results(
        {stats_key(world_id, item_id): entry for item_id, entry in overview.items()}, "market_overview"
    )
    return overview


def build_overview(row):
    """Reduce one aggregated market row to its world price and daily sale speed."""
    if row is None:
        return {"price": 0, "velocity": 0.0}
    fields = row.get("nq", {})
    price = fields.get("minListing", {}).get("world", {}).get("price", 0)
    velocity = fields.get("dailySaleVelocity", {}).get("world", {}).get("quantity", 0)
    return {"price": int(price), "velocity": round(float(velocity), 1)}


def stats_key(world_id, item_id):
    """Build the cache key of one item's market stats on one world."""
    return f"{world_id}:{item_id}"


def lookup_market_stats(world_id, item_ids):
    """Fetch price and sale speed for up to one chunk of items in one call."""
    joined = ",".join(str(item_id) for item_id in item_ids)
    data = get_json(f"{MARKET_URL}/{world_id}/{joined}", {
        "listings": 0,
        "entries": MAX_HISTORY_ENTRIES,
        "entriesWithin": HISTORY_WINDOW_SECONDS,
    })
    if data is None:
        return None
    rows = data.get("items")
    if rows is None:
        rows = {str(data.get("itemID")): data}
    stats = {}
    for item_id in item_ids:
        stats[item_id] = build_stats(rows.get(str(item_id)))
    item_cache.store_results(
        {stats_key(world_id, item_id): entry for item_id, entry in stats.items()}, "market_stats"
    )
    return stats


def build_stats(fields):
    """Reduce one market data row to its prices and weekly sales volume."""
    if fields is None:
        return {"price": 0, "avg_price": 0, "min_sale": 0, "max_sale": 0, "week_volume": 0}
    sale_prices = [sale["pricePerUnit"] for sale in fields.get("recentHistory", [])]
    return {
        "price": int(fields.get("minPrice", 0)),
        "avg_price": round(fields.get("averagePrice", 0)),
        "min_sale": min(sale_prices, default=0),
        "max_sale": max(sale_prices, default=0),
        "week_volume": int(fields.get("unitsSold", 0)),
    }


PRICE_KIND_LOOKUPS = (
    ("market_overview", OVERVIEW_CHUNK_SIZE, lookup_market_overview_with_retry),
    ("market_stats", CHUNK_SIZE, lookup_market_stats_with_retry),
    ("market_listings", LISTINGS_CHUNK_SIZE, lookup_market_listings_with_retry),
)


def refresh_cached_prices():
    """Refetch every cached market price, counted as one background fetch."""
    return item_cache.counted_fetch(refresh_all_price_kinds)


def refresh_all_price_kinds():
    """Run one bulk refetch pipeline per price kind and world, telling if all succeeded."""
    complete = True
    for kind, size, lookup in PRICE_KIND_LOOKUPS:
        for world_id, item_ids in cached_price_worlds(kind).items():
            if not refresh_price_kind(kind, world_id, item_ids, size, lookup):
                complete = False
    return complete


def refresh_price_kind(kind, world_id, item_ids, size, lookup):
    """Refetch the cached item ids of one price kind on one world in full chunks."""
    with item_cache.fetch_lock(f"{kind}:{world_id}"):
        fetched = fetch_chunks(item_ids, size, lambda chunk: lookup(world_id, chunk))
    return fetched is not None


def cached_price_worlds(kind):
    """Group the cached item ids of one price kind by their world."""
    worlds = {}
    for name in item_cache.names_of_kind(kind):
        world_part, _, item_part = name.partition(":")
        if world_part.isdigit() and item_part.isdigit():
            worlds.setdefault(int(world_part), []).append(int(item_part))
    return worlds


def chunked(values, size):
    """Split the values into lists of at most the given size."""
    return [values[start:start + size] for start in range(0, len(values), size)]


def get_json(url, params):
    """Send one api request and return the parsed json, or None on errors."""
    LOG.info("calling universalis: %s %s", url, params)
    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
    except requests.RequestException as error:
        LOG.warning("universalis request to %s failed: %s", url, error)
        return None
    return response.json()
