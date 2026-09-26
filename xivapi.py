import requests

import item_cache

SEARCH_URL = "https://v2.xivapi.com/api/search"

CACHE = {}


def fetch_item_id(item_name):
    """Return the game item id for an exact item name, ignoring case, or None."""
    item = fetch_item(item_name)
    if item:
        return item["row_id"]
    return None


def fetch_item(item_name):
    """Return full item data from memory, the cache file, or the api."""
    key = item_name.lower()
    if key in CACHE:
        return CACHE[key]
    item = item_cache.get_fresh_result(item_name)
    if not item:
        item = find_exact_match(item_name)
        if item:
            item_cache.store_result(item_name, item)
    CACHE[key] = item
    return item


def find_exact_match(item_name):
    """Find the exact item name in the search results and return it, or None."""
    for result in search_items(item_name):
        if result["fields"]["Name"].lower() == item_name.lower():
            return result
    return None


def search_items(item_name):
    """Query xivapi for items matching the name, returning an empty list on errors."""
    query = f'Name~"{item_name}"'
    params = {"sheets": "Item", "query": query, "limit": 10}
    try:
        response = requests.get(SEARCH_URL, params=params, timeout=10)
        response.raise_for_status()
    except requests.RequestException:
        return []
    return response.json()["results"]
