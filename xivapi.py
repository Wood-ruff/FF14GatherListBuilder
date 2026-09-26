import logging

import requests

import item_cache
import settings

SEARCH_URL = "https://v2.xivapi.com/api/search"
SHEET_URL = "https://v2.xivapi.com/api/sheet"
ASSET_URL = "https://v2.xivapi.com/api/asset"

CACHE = {}
RECIPES = {}
API_STATUS = {"last_call_failed": False}

LOG = logging.getLogger(__name__)


def last_call_failed():
    """Tell whether the most recent api call failed to reach xivapi."""
    return API_STATUS["last_call_failed"]


def clear_cache():
    """Forget all cached items and recipes, in memory and on disk."""
    CACHE.clear()
    RECIPES.clear()
    item_cache.clear()


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
    item = item_cache.get_fresh_result(item_name, "item")
    if not item:
        item = find_exact_match(item_name)
        if item:
            item_cache.store_result(item_name, item, "item")
    if item:
        ensure_icon(item)
    CACHE[key] = item
    return item


def ensure_icon(item):
    """Download the item's icon once; the page only ever reads the cached file."""
    icon = item["fields"].get("Icon")
    if not icon or item_cache.has_icon(item["row_id"]):
        return
    png = fetch_asset(icon["path"])
    if png:
        item_cache.store_icon(item["row_id"], png)


def icon_folder():
    """Return the folder where item icons are cached."""
    return item_cache.ICONS_DIR


def fetch_recipe(item_name):
    """Return the recipe for a craftable item from memory, the cache file, or the api."""
    key = item_name.lower()
    if key in RECIPES:
        return RECIPES[key]
    recipe = item_cache.get_fresh_result(item_name, "recipe")
    if not recipe:
        recipe = lookup_recipe(item_name)
        if recipe:
            item_cache.store_result(item_name, recipe, "recipe")
    RECIPES[key] = recipe
    return recipe


def lookup_recipe(item_name):
    """Find the first recipe producing the item and return its ingredients, or None."""
    item = fetch_item(item_name)
    if not item:
        return None
    recipe_id = search_first_recipe_id(item["row_id"])
    if not recipe_id:
        return None
    return fetch_recipe_row(recipe_id)


def search_first_recipe_id(item_id):
    """Return the row id of the first recipe producing the item, or None."""
    params = {"sheets": "Recipe", "query": f"ItemResult={item_id}", "limit": 1}
    data = get_json(SEARCH_URL, params)
    if not data or not data["results"]:
        return None
    return data["results"][0]["row_id"]


def fetch_recipe_row(recipe_id):
    """Fetch one recipe row and return its yield and ingredient list, or None."""
    url = f"{SHEET_URL}/Recipe/{recipe_id}"
    params = {
        "fields": "AmountResult,Ingredient[].Name,AmountIngredient",
        "language": settings.get_language(),
    }
    data = get_json(url, params)
    if not data:
        return None
    fields = data["fields"]
    ingredients = []
    for ingredient, amount in zip(fields["Ingredient"], fields["AmountIngredient"]):
        if amount > 0 and ingredient["row_id"] > 0:
            ingredients.append({
                "name": ingredient["fields"]["Name"],
                "game_id": ingredient["row_id"],
                "amount": amount,
            })
    return {"yields": fields["AmountResult"], "ingredients": ingredients}


def find_exact_match(item_name):
    """Find the exact item name in the search results and return it, or None."""
    for result in search_items(item_name):
        if result["fields"]["Name"].lower() == item_name.lower():
            return result
    return None


def search_items(item_name):
    """Query xivapi for items matching the name, returning an empty list on errors."""
    query = f'Name~"{item_name}"'
    params = {
        "sheets": "Item",
        "query": query,
        "limit": 10,
        "language": settings.get_language(),
    }
    data = get_json(SEARCH_URL, params)
    if not data:
        return []
    return data["results"]


def get_json(url, params):
    """Send one api request and return the parsed json, or None on errors."""
    LOG.info("calling xivapi: %s %s", url, params)
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
    except requests.RequestException as error:
        LOG.warning("xivapi request to %s failed: %s", url, error)
        API_STATUS["last_call_failed"] = True
        return None
    API_STATUS["last_call_failed"] = False
    return response.json()


def fetch_asset(path):
    """Download one game asset as png bytes, or None on errors."""
    LOG.info("calling xivapi asset: %s", path)
    params = {"path": path, "format": "png"}
    try:
        response = requests.get(ASSET_URL, params=params, timeout=10)
        response.raise_for_status()
    except requests.RequestException as error:
        LOG.warning("xivapi asset download of %s failed: %s", path, error)
        API_STATUS["last_call_failed"] = True
        return None
    API_STATUS["last_call_failed"] = False
    return response.content
