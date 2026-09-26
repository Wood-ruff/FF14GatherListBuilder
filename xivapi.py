import logging

import requests

import item_cache
import settings

SEARCH_URL = "https://v2.xivapi.com/api/search"
SHEET_URL = "https://v2.xivapi.com/api/sheet"
ASSET_URL = "https://v2.xivapi.com/api/asset"

CACHE = {}
RECIPES = {}
SUGGESTIONS = {}
GATHERING = {}
API_STATUS = {"last_call_failed": False}

NO_TIME = 65535
NO_NODE = {"timed": False, "times": [], "zone": None, "aetheryte": None}

LOG = logging.getLogger(__name__)


def last_call_failed():
    """Tell whether the most recent api call failed to reach xivapi."""
    return API_STATUS["last_call_failed"]


def clear_cache():
    """Forget all cached items and recipes, in memory and on disk."""
    CACHE.clear()
    RECIPES.clear()
    SUGGESTIONS.clear()
    GATHERING.clear()
    item_cache.clear()


SUGGESTION_LIMIT = 50


def search_item_names(text):
    """Return item names matching a partial search, remembered per query and language."""
    key = f"{settings.get_language()}:{text.lower()}"
    if key not in SUGGESTIONS:
        results = search_items(text, SUGGESTION_LIMIT)
        SUGGESTIONS[key] = [result["fields"]["Name"] for result in results]
    return SUGGESTIONS[key]


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


def fetch_gathering(game_id):
    """Return gathering node info for an item from memory, the cache file, or the api."""
    if game_id in GATHERING:
        return GATHERING[game_id]
    info = item_cache.get_fresh_result(str(game_id), "gathering")
    if info is None:
        info = find_in_cached_nodes(game_id)
    if info is None:
        info = lookup_gathering(game_id)
        if info is not None:
            item_cache.store_result(str(game_id), info, "gathering")
    GATHERING[game_id] = info
    return info


def find_in_cached_nodes(game_id):
    """Look for the item in already cached nodes and reuse their data."""
    for entry in item_cache.load_cache().values():
        if entry.get("type") != "node" or item_cache.is_expired(entry["fetchdate"]):
            continue
        node = entry["result"]
        if game_id in node["items"]:
            return item_info_from_node(node)
    return None


def item_info_from_node(node):
    """Build the per-item gathering info from a cached node."""
    return {
        "timed": len(node["times"]) > 0,
        "times": node["times"],
        "zone": node["zone"],
        "aetheryte": node["aetheryte"],
    }


def lookup_gathering(game_id):
    """Fetch the gathering node of an item, caching the whole node with all its items."""
    found = search_rows("GatheringItem", f"Item={game_id}")
    if found is None:
        return None
    if not found:
        return dict(NO_NODE)
    node = lookup_node(found[0]["row_id"])
    if node is None:
        return None
    if not node:
        return dict(NO_NODE)
    item_cache.store_result(str(node["base_id"]), node, "node")
    return item_info_from_node(node)


def lookup_node(gathering_item_id):
    """Fetch one gathering node with its member items, zone, aetheryte and times."""
    bases = search_rows("GatheringPointBase", f"+Item[]={gathering_item_id}", "Item[].Item.Name")
    if bases is None:
        return None
    if not bases:
        return {}
    base = bases[0]
    points = search_rows(
        "GatheringPoint",
        f"GatheringPointBase={base['row_id']}",
        "TerritoryType.PlaceName.Name,TerritoryType.Aetheryte.PlaceName.Name",
    )
    if points is None:
        return None
    if not points:
        return {}
    times = fetch_node_times(points[0]["row_id"])
    if times is None:
        return None
    territory = points[0]["fields"]["TerritoryType"]["fields"]
    return {
        "base_id": base["row_id"],
        "items": node_member_ids(base),
        "zone": territory["PlaceName"]["fields"]["Name"],
        "aetheryte": territory_aetheryte_name(territory),
        "times": times,
    }


def node_member_ids(base):
    """Return the game item ids of all items inside a gathering node."""
    members = []
    for ref in base["fields"]["Item"]:
        if ref["row_id"] > 0:
            members.append(ref["fields"]["Item"]["row_id"])
    return members


def territory_aetheryte_name(territory):
    """Return the zone's aetheryte name, or None if the data has none."""
    aetheryte = territory["Aetheryte"]
    if aetheryte["row_id"] > 0:
        return aetheryte["fields"]["PlaceName"]["fields"]["Name"]
    return None


def fetch_node_times(point_id):
    """Fetch the spawn windows of a gathering point as eorzea minute pairs."""
    url = f"{SHEET_URL}/GatheringPointTransient/{point_id}"
    fields = (
        "EphemeralStartTime,EphemeralEndTime,"
        "GatheringRarePopTimeTable.StartTime,GatheringRarePopTimeTable.Duration"
    )
    data = get_json(url, {"fields": fields})
    if data is None:
        return None
    return rare_pop_times(data["fields"]) + ephemeral_times(data["fields"])


def rare_pop_times(fields):
    """Convert the rare pop time table into start and duration minute pairs."""
    table = fields["GatheringRarePopTimeTable"].get("fields", {})
    times = []
    for start, duration in zip(table.get("StartTime", []), table.get("Duration", [])):
        if start != NO_TIME and duration > 0:
            times.append({
                "start": game_time_to_minutes(start),
                "duration": game_time_to_minutes(duration),
            })
    return times


def ephemeral_times(fields):
    """Convert ephemeral start and end times into one window, if the node has them."""
    start = fields["EphemeralStartTime"]
    end = fields["EphemeralEndTime"]
    if start == NO_TIME or end == NO_TIME:
        return []
    start_minutes = game_time_to_minutes(start)
    duration = (game_time_to_minutes(end) - start_minutes) % 1440
    return [{"start": start_minutes, "duration": duration}]


def game_time_to_minutes(value):
    """Convert the games HHMM numbers into plain minutes."""
    return (value // 100) * 60 + value % 100


def search_rows(sheet, query, fields=None):
    """Search one sheet and return the result rows, or None on network errors."""
    params = {"sheets": sheet, "query": query, "limit": 1, "language": settings.get_language()}
    if fields:
        params["fields"] = fields
    data = get_json(SEARCH_URL, params)
    if data is None:
        return None
    return data["results"]


def find_exact_match(item_name):
    """Find the exact item name in the search results and return it, or None."""
    for result in search_items(item_name):
        if result["fields"]["Name"].lower() == item_name.lower():
            return result
    return None


def search_items(item_name, limit=10):
    """Query xivapi for items matching the name, returning an empty list on errors."""
    query = f'Name~"{item_name}"'
    params = {
        "sheets": "Item",
        "query": query,
        "limit": limit,
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
