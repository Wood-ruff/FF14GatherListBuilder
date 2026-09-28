import logging
from concurrent.futures import ThreadPoolExecutor

import requests

import item_cache
import settings

SEARCH_URL = "https://v2.xivapi.com/api/search"
SHEET_URL = "https://v2.xivapi.com/api/sheet"
ASSET_URL = "https://v2.xivapi.com/api/asset"

CACHE = {}
ID_CACHE = {}
RECIPES = {}
SUGGESTIONS = {}
GATHERING = {}
AETHERYTES = {}
COLLECTABLES = {}
CRAFTABLES = {}
MATERIAL_SOURCES = {}
CURRENCY_SHOP = {}
VENTURES = []
TOMESTONES = {}
DOWNLOADED_ICONS = set()
API_STATUS = {"last_call_failed": False}

NO_TIME = 65535
CRYSTAL_GAME_IDS = range(2, 20)
NO_NODE = {"timed": False, "times": [], "zone": None, "aetheryte": None, "job_ids": [], "x": None, "y": None}

LOG = logging.getLogger(__name__)


def last_call_failed():
    """Tell whether the most recent api call failed to reach xivapi."""
    return API_STATUS["last_call_failed"]


def fetches_running():
    """Tell whether any big data lookup is currently running."""
    return item_cache.fetches_running()


def clear_cache():
    """Forget all cached items and recipes, in memory and on disk."""
    CACHE.clear()
    ID_CACHE.clear()
    RECIPES.clear()
    SUGGESTIONS.clear()
    GATHERING.clear()
    AETHERYTES.clear()
    COLLECTABLES.clear()
    CRAFTABLES.clear()
    MATERIAL_SOURCES.clear()
    CURRENCY_SHOP.clear()
    VENTURES.clear()
    TOMESTONES.clear()
    DOWNLOADED_ICONS.clear()
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
    with item_cache.fetch_lock(f"item:{key}"):
        if key in CACHE:
            if CACHE[key]:
                ensure_icon(CACHE[key])
            return CACHE[key]
        item = item_cache.get_fresh_result(item_name, "item")
        if not item:
            item = find_exact_match(item_name)
            if item:
                item_cache.store_result(item_name, item, "item")
        if item:
            ensure_icon(item)
        if item or not last_call_failed():
            CACHE[key] = item
        return item


def ensure_icon(item):
    """Download the item's icon once; the page only ever reads the cached file."""
    icon = item["fields"].get("Icon")
    if not icon:
        return
    with item_cache.fetch_lock(f"icon:{item['row_id']}"):
        if item_cache.has_icon(item["row_id"]):
            return
        png = fetch_asset(icon["path"])
        if png:
            item_cache.store_icon(item["row_id"], png)


def icon_folder():
    """Return the folder where item icons are cached."""
    return item_cache.ICONS_DIR


NO_RECIPE = {"no_recipe": True}


RECIPE_BATCH_SIZE = 40
RECIPE_BATCH_FIELDS = (
    "ItemResult@as(raw),CraftType.Name,AmountResult,Ingredient[].Name,AmountIngredient"
)


def warm_recipes(ingredients):
    """Batch cache missing recipes for id to name pairs and return every pair seen."""
    with item_cache.fetch_lock("recipe_warmup"):
        seen = {}
        pending = dict(ingredients)
        for _depth in range(10):
            pending = {game_id: name for game_id, name in pending.items()
                       if game_id not in seen}
            if not pending:
                break
            seen.update(pending)
            missing = {game_id: name for game_id, name in pending.items()
                       if not recipe_cached(name)}
            if missing:
                grouped = item_cache.counted_fetch(lambda: batch_lookup_recipes(sorted(missing)))
                if grouped is None:
                    return seen
                store_recipe_batch(missing, grouped)
            pending = next_ingredients(pending)
        return seen


def next_ingredients(pairs):
    """Collect the ingredient pairs of the cached recipes behind the given items."""
    next_level = {}
    for name in pairs.values():
        recipe = fetch_recipe(name)
        if recipe:
            for ingredient in recipe["ingredients"]:
                next_level[ingredient["game_id"]] = ingredient["name"]
    return next_level


def recipe_cached(item_name):
    """Tell whether the item's recipe or no recipe marker is already known."""
    if item_name.lower() in RECIPES:
        return True
    return cached_recipe(item_name) is not None


def batch_lookup_recipes(game_ids):
    """Fetch the recipes of many result items with chunked search queries."""
    grouped = {}
    for chunk in chunked(game_ids, RECIPE_BATCH_SIZE):
        query = " ".join(f"ItemResult={game_id}" for game_id in chunk)
        rows = search_sheet_rows("Recipe", query, RECIPE_BATCH_FIELDS)
        if rows is None:
            return None
        for row in rows:
            grouped.setdefault(row["fields"]["ItemResult@as(raw)"], []).append(row["fields"])
    return grouped


def store_recipe_batch(missing, grouped):
    """Cache one level of batched recipes and their no recipe markers."""
    stored = {}
    for game_id, name in missing.items():
        rows = grouped.get(game_id)
        recipe = build_batched_recipe(rows) if rows else None
        stored[name] = recipe if recipe else NO_RECIPE
        RECIPES[name.lower()] = recipe
    item_cache.store_results(stored, "recipe")


def build_batched_recipe(rows):
    """Build one cached recipe from its batched search rows."""
    first = rows[0]
    return {
        "yields": first["AmountResult"],
        "ingredients": recipe_ingredients(first),
        "craft_types": distinct_craft_types([{"fields": fields} for fields in rows]),
    }


def fetch_recipe(item_name):
    """Return the recipe for a craftable item from memory, the cache file, or the api."""
    key = item_name.lower()
    with item_cache.fetch_lock(f"recipe:{key}"):
        if key in RECIPES:
            return RECIPES[key]
        recipe = cached_recipe(item_name)
        if recipe is None:
            recipe = lookup_and_store_recipe(item_name)
        if recipe == NO_RECIPE:
            RECIPES[key] = None
            return None
        if recipe is not None:
            RECIPES[key] = recipe
        return recipe


def cached_recipe(item_name):
    """Return the file cached recipe, the no recipe marker, or None when unknown."""
    cached = item_cache.get_fresh_result(item_name, "recipe")
    if cached == NO_RECIPE:
        return cached
    if cached and "craft_types" not in cached:
        return None
    return cached


def lookup_and_store_recipe(item_name):
    """Look the recipe up at the api and cache the result, even a missing one."""
    recipe = lookup_recipe(item_name)
    if recipe:
        item_cache.store_result(item_name, recipe, "recipe")
    elif not last_call_failed():
        item_cache.store_result(item_name, NO_RECIPE, "recipe")
        return NO_RECIPE
    return recipe


def lookup_recipe(item_name):
    """Find the recipes producing the item and return the first one's ingredients, or None."""
    item = fetch_item(item_name)
    if not item:
        return None
    rows = search_rows("Recipe", f"ItemResult={item['row_id']}", "CraftType.Name", limit=10)
    if not rows:
        return None
    recipe = fetch_recipe_row(rows[0]["row_id"])
    if recipe is None:
        return None
    recipe["craft_types"] = distinct_craft_types(rows)
    return recipe


def distinct_craft_types(recipe_rows):
    """Return the distinct crafting class names of the given recipe rows."""
    names = []
    for row in recipe_rows:
        name = row["fields"].get("CraftType", {}).get("fields", {}).get("Name")
        if name and name not in names:
            names.append(name)
    return names


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
    return {"yields": fields["AmountResult"], "ingredients": recipe_ingredients(fields)}


def recipe_ingredients(fields):
    """Return the usable ingredients of one recipe row's fields."""
    ingredients = []
    for ingredient, amount in zip(fields["Ingredient"], fields["AmountIngredient"]):
        if amount > 0 and ingredient["row_id"] > 0:
            ingredients.append({
                "name": ingredient["fields"]["Name"],
                "game_id": ingredient["row_id"],
                "amount": amount,
            })
    return ingredients


def fetch_item_by_id(game_id):
    """Return item data for a game id in the current language, independent of names."""
    key = f"{settings.get_language()}:{game_id}"
    with item_cache.fetch_lock(f"item_id:{key}"):
        if key in ID_CACHE:
            if ID_CACHE[key]:
                ensure_icon(ID_CACHE[key])
            return ID_CACHE[key]
        item = item_cache.get_fresh_result(key, "item_id")
        if item is None:
            item = lookup_item_by_id(game_id)
            if item is not None:
                item_cache.store_result(key, item, "item_id")
        if item:
            ensure_icon(item)
        if item or not last_call_failed():
            ID_CACHE[key] = item
        return item


def lookup_item_by_id(game_id):
    """Fetch one item row from the api by its id."""
    url = f"{SHEET_URL}/Item/{game_id}"
    data = get_json(url, {"fields": "Name,Icon", "language": settings.get_language()})
    if data is None or not data["fields"].get("Name"):
        return None
    return {"row_id": data["row_id"], "fields": data["fields"]}


def fetch_gathering(game_id):
    """Return gathering node info for an item from memory, the cache file, or the api."""
    with item_cache.fetch_lock(f"gathering:{game_id}"):
        if game_id in GATHERING:
            return GATHERING[game_id]
        info = item_cache.get_fresh_result(str(game_id), "gathering")
        if info is not None and (not isinstance(info.get("job_ids"), list) or "x" not in info):
            info = None
        if info is not None and game_id in CRYSTAL_GAME_IDS and len(info["job_ids"]) < 2:
            info = None
        if info is None and game_id not in CRYSTAL_GAME_IDS:
            info = find_in_cached_nodes(game_id)
        if info is None:
            info = lookup_gathering(game_id)
            if info is not None:
                item_cache.store_result(str(game_id), info, "gathering")
        if info is not None:
            GATHERING[game_id] = info
        return info


def find_in_cached_nodes(game_id):
    """Look for the item in already cached nodes and reuse their data."""
    for entry in item_cache.load_cache().values():
        if entry.get("type") != "node" or item_cache.is_expired(entry["fetchdate"]):
            continue
        node = entry["result"]
        if "job_id" in node and "x" in node and game_id in node["items"]:
            return item_info_from_node(node)
    return None


def item_info_from_node(node):
    """Build the per-item gathering info from a cached node."""
    return {
        "timed": len(node["times"]) > 0,
        "times": node["times"],
        "zone": node["zone"],
        "aetheryte": node["aetheryte"],
        "job_ids": [node["job_id"]],
        "x": node.get("x"),
        "y": node.get("y"),
    }


def lookup_gathering(game_id):
    """Fetch the gathering data of an item, caching its first node with all its items."""
    found = search_rows("GatheringItem", f"Item={game_id}")
    if found is None:
        return None
    if not found:
        return dict(NO_NODE)
    return lookup_gathering_node(found[0]["row_id"])


def lookup_gathering_node(gathering_item_id):
    """Fetch the node data behind one gathering item row."""
    bases = search_rows(
        "GatheringPointBase", f"+Item[]={gathering_item_id}",
        "Item[].Item.Name,GatheringType.Name", limit=100,
    )
    if bases is None:
        return None
    if not bases:
        return dict(NO_NODE)
    node = lookup_node(bases[0])
    if node is None:
        return None
    if not node:
        return dict(NO_NODE)
    item_cache.store_result(str(node["base_id"]), node, "node")
    info = item_info_from_node(node)
    info["job_ids"] = distinct_gathering_jobs(bases)
    return info


def warm_gathering(game_ids):
    """Batch resolve which items come from nodes and cache all their gathering data."""
    with item_cache.fetch_lock("gathering_warmup"):
        missing = [game_id for game_id in dict.fromkeys(game_ids)
                   if game_id not in GATHERING and game_id not in CRYSTAL_GAME_IDS
                   and item_cache.get_fresh_result(str(game_id), "gathering") is None]
        if not missing:
            return
        membership = item_cache.counted_fetch(lambda: batch_gathering_rows(missing))
        if membership is None:
            return
        item_cache.counted_fetch(lambda: store_gathering_batch(missing, membership))


def batch_gathering_rows(game_ids):
    """Map item ids to their gathering item row ids with chunked search queries."""
    mapping = {}
    for chunk in chunked(game_ids, RECIPE_BATCH_SIZE):
        query = " ".join(f"Item={game_id}" for game_id in chunk)
        rows = search_sheet_rows("GatheringItem", query, RAW_ITEM_FIELD)
        if rows is None:
            return None
        for row in rows:
            mapping.setdefault(row["fields"][RAW_ITEM_FIELD], row["row_id"])
    return mapping


def store_gathering_batch(game_ids, membership):
    """Cache the gathering info of node items and no node markers for the rest."""
    infos = {str(game_id): dict(NO_NODE) for game_id in game_ids if game_id not in membership}
    members = {game_id: membership[game_id] for game_id in game_ids if game_id in membership}
    if members:
        infos.update(batch_lookup_nodes(members))
    for key, info in infos.items():
        GATHERING[int(key)] = info
    item_cache.store_results(infos, "gathering")


def batch_lookup_nodes(members):
    """Resolve many items' nodes with batched base, point and time lookups."""
    grouped = batch_gathering_bases(sorted(set(members.values())))
    if grouped is None:
        return {}
    picks = {game_id: pick_node_base(grouped.get(gi_id)) for game_id, gi_id in members.items()}
    base_ids = sorted({base["row_id"] for base in picks.values() if base})
    points = batch_gathering_points(base_ids)
    if points is None:
        return {}
    times = batch_node_times(sorted({point["row_id"] for point in points.values()}))
    return assemble_member_nodes(members, grouped, picks, points, times)


def pick_node_base(rows):
    """Return the base with the lowest row id, or None without any base."""
    if not rows:
        return None
    return min(rows, key=lambda row: row["row_id"])


NODE_BASE_FIELDS = "Item@as(raw),Item[].Item.Name,GatheringType.Name"


def batch_gathering_bases(gathering_item_ids):
    """Group all node bases by the gathering item ids they contain."""
    wanted = set(gathering_item_ids)
    grouped = {}
    seen = set()
    for chunk in chunked(gathering_item_ids, RECIPE_BATCH_SIZE):
        query = " ".join(f"Item[]={gi_id}" for gi_id in chunk)
        rows = search_sheet_rows("GatheringPointBase", query, NODE_BASE_FIELDS)
        if rows is None:
            return None
        for row in rows:
            for gi_id in row["fields"]["Item@as(raw)"]:
                if gi_id in wanted and (gi_id, row["row_id"]) not in seen:
                    seen.add((gi_id, row["row_id"]))
                    grouped.setdefault(gi_id, []).append(row)
    return grouped


def batch_gathering_points(base_ids):
    """Map base ids to their first gathering point with zone data."""
    points = {}
    for chunk in chunked(base_ids, RECIPE_BATCH_SIZE):
        query = " ".join(f"GatheringPointBase={base_id}" for base_id in chunk)
        rows = search_sheet_rows(
            "GatheringPoint", query, f"GatheringPointBase@as(raw),{POINT_FIELDS}"
        )
        if rows is None:
            return None
        for row in rows:
            base_id = row["fields"]["GatheringPointBase@as(raw)"]
            known = points.get(base_id)
            if known is None or row["row_id"] < known["row_id"]:
                points[base_id] = row
    return points


def batch_node_times(point_ids):
    """Map point ids to their spawn windows, fetched in bulk sheet calls."""
    times = {}
    for chunk in chunked(point_ids, 100):
        data = get_json(f"{SHEET_URL}/GatheringPointTransient", {
            "rows": ",".join(str(point_id) for point_id in chunk),
            "fields": NODE_TIME_FIELDS,
            "limit": len(chunk),
        })
        if data is None:
            return times
        for row in data["rows"]:
            times[row["row_id"]] = rare_pop_times(row["fields"]) + ephemeral_times(row["fields"])
    return times


def assemble_member_nodes(members, grouped, picks, points, times):
    """Build and cache every member's node info from the batched pieces."""
    infos = {}
    pending = []
    for game_id, gi_id in members.items():
        base = picks[game_id]
        point = points.get(base["row_id"]) if base else None
        if point is None:
            infos[str(game_id)] = dict(NO_NODE)
        else:
            pending.append((game_id, gi_id, base, point))
    with ThreadPoolExecutor(max_workers=ICON_WORKERS) as pool:
        finished = list(pool.map(lambda entry: finish_member_node(entry, times), pending))
    nodes = {}
    for game_id, gi_id, node in finished:
        if node is None:
            continue
        nodes[str(node["base_id"])] = node
        info = item_info_from_node(node)
        info["job_ids"] = distinct_gathering_jobs(grouped[gi_id])
        infos[str(game_id)] = info
    item_cache.store_results(nodes, "node")
    return infos


def finish_member_node(entry, times):
    """Complete one member's node from the batched parts, filling missing times."""
    game_id, gi_id, base, point = entry
    node_times = times.get(point["row_id"])
    if node_times is None:
        node_times = fetch_node_times(point["row_id"])
    if node_times is None:
        return game_id, gi_id, None
    return game_id, gi_id, node_from_parts(base, point, node_times)


def warm_items(game_ids):
    """Batch fetch and cache missing item rows for the given game ids."""
    language = settings.get_language()
    with item_cache.fetch_lock("item_warmup"):
        missing = [game_id for game_id in dict.fromkeys(game_ids)
                   if f"{language}:{game_id}" not in ID_CACHE
                   and item_cache.get_fresh_result(f"{language}:{game_id}", "item_id") is None]
        if not missing:
            return
        rows = item_cache.counted_fetch(lambda: batch_item_rows(missing, "Name,Icon", language))
        if rows is None:
            return
        stored = {}
        named = {}
        for row in rows:
            item = {"row_id": row["row_id"], "fields": row["fields"]}
            stored[f"{language}:{row['row_id']}"] = item
            ID_CACHE[f"{language}:{row['row_id']}"] = item
            name = row["fields"].get("Name")
            if name:
                named[name] = item
                CACHE[name.lower()] = item
        item_cache.store_results(stored, "item_id")
        item_cache.store_results(named, "item")


ICON_WORKERS = 4


def warm_icons(game_ids):
    """Download the missing icons of the given items with a few parallel workers."""
    language = settings.get_language()
    items = []
    for game_id in dict.fromkeys(game_ids):
        item = ID_CACHE.get(f"{language}:{game_id}") or item_cache.get_fresh_result(
            f"{language}:{game_id}", "item_id"
        )
        if item and item["fields"].get("Icon") and not item_cache.has_icon(item["row_id"]):
            items.append(item)
    if not items:
        return
    with ThreadPoolExecutor(max_workers=ICON_WORKERS) as pool:
        list(pool.map(ensure_icon, items))


def warm_item_details(game_ids):
    """Batch fetch and cache missing price and market details for the game ids."""
    with item_cache.fetch_lock("item_details_warmup"):
        missing = [game_id for game_id in dict.fromkeys(game_ids)
                   if item_cache.get_fresh_result(str(game_id), "item_details") is None]
        if not missing:
            return
        fields = "PriceMid,ItemSearchCategory@as(raw)"
        rows = item_cache.counted_fetch(
            lambda: batch_item_rows(missing, fields, settings.get_language())
        )
        if rows is None:
            return
        stored = {}
        for row in rows:
            stored[str(row["row_id"])] = {
                "price": row["fields"]["PriceMid"],
                "marketable": row["fields"]["ItemSearchCategory@as(raw)"] > 0,
            }
        item_cache.store_results(stored, "item_details")


def batch_item_rows(game_ids, fields, language):
    """Fetch many item sheet rows in chunked calls and return them all."""
    rows = []
    for chunk in chunked(game_ids, 100):
        data = get_json(f"{SHEET_URL}/Item", {
            "rows": ",".join(str(game_id) for game_id in chunk),
            "fields": fields,
            "language": language,
            "limit": len(chunk),
        })
        if data is None:
            return None
        rows.extend(data["rows"])
    return rows


def distinct_gathering_jobs(bases):
    """Return the distinct gathering type ids of the given node bases."""
    job_ids = []
    for base in bases:
        job_id = base["fields"]["GatheringType"]["row_id"]
        if job_id not in job_ids:
            job_ids.append(job_id)
    return job_ids


POINT_FIELDS = (
    "TerritoryType.PlaceName.Name,TerritoryType.Aetheryte.PlaceName.Name,"
    "TerritoryType.Map.SizeFactor,TerritoryType.Map.OffsetX,TerritoryType.Map.OffsetY"
)


def lookup_node(base):
    """Fetch one gathering node with its items, zone, aetheryte, position and times."""
    points = search_rows("GatheringPoint", f"GatheringPointBase={base['row_id']}", POINT_FIELDS)
    if points is None:
        return None
    if not points:
        return {}
    times = fetch_node_times(points[0]["row_id"])
    if times is None:
        return None
    return node_from_parts(base, points[0], times)


def node_from_parts(base, point, times):
    """Build one node from its base and point rows, resolving position and aetheryte."""
    territory = point["fields"]["TerritoryType"]["fields"]
    territory_id = point["fields"]["TerritoryType"]["row_id"]
    map_fields = territory.get("Map", {}).get("fields", {})
    x, y = node_map_position(base["row_id"], map_fields)
    aetheryte = closest_aetheryte(territory_id, map_fields.get("SizeFactor", 100), x, y)
    return {
        "base_id": base["row_id"],
        "items": node_member_ids(base),
        "zone": territory["PlaceName"]["fields"]["Name"],
        "aetheryte": aetheryte or territory_aetheryte_name(territory),
        "times": times,
        "job_id": base["fields"]["GatheringType"]["row_id"],
        "x": x,
        "y": y,
    }


def node_map_position(base_id, map_fields):
    """Return the node's in game map coordinates, or None pair without position data."""
    url = f"{SHEET_URL}/ExportedGatheringPoint/{base_id}"
    LOG.info("calling xivapi: %s", url)
    data = fetch_optional_json(url, {"fields": "X,Y"})
    if data is None:
        return None, None
    size_factor = map_fields.get("SizeFactor", 100)
    x = to_map_coord(data["fields"]["X"], map_fields.get("OffsetX", 0), size_factor)
    y = to_map_coord(data["fields"]["Y"], map_fields.get("OffsetY", 0), size_factor)
    return x, y


def closest_aetheryte(territory_id, size_factor, x, y):
    """Return the name of the aetheryte nearest to the map position, or None."""
    if x is None:
        return None
    aetherytes = fetch_zone_aetherytes(territory_id, size_factor)
    if not aetherytes:
        return None
    nearest = min(aetherytes, key=lambda a: (a["x"] - x) ** 2 + (a["y"] - y) ** 2)
    return nearest["name"]


def fetch_zone_aetherytes(territory_id, size_factor):
    """Return the zone's aetherytes with map coordinates, cached per territory."""
    key = f"{settings.get_language()}:{territory_id}"
    if key in AETHERYTES:
        return AETHERYTES[key]
    data = item_cache.get_fresh_result(key, "aetherytes")
    if data is None:
        data = lookup_zone_aetherytes(territory_id, size_factor)
        if data is not None:
            item_cache.store_result(key, data, "aetherytes")
    AETHERYTES[key] = data
    return data


def lookup_zone_aetherytes(territory_id, size_factor):
    """Fetch the zone's aetheryte map markers from the api."""
    rows = search_rows(
        "MapMarker", f"+DataType=3 +DataKey.Territory={territory_id}",
        "X,Y,DataKey.PlaceName.Name", limit=20,
    )
    if rows is None:
        return None
    scale = 41 / (size_factor / 100)
    aetherytes = []
    for row in rows:
        name = row["fields"]["DataKey"].get("fields", {}).get("PlaceName", {}).get("fields", {}).get("Name")
        if name:
            aetherytes.append({
                "name": name,
                "x": round(row["fields"]["X"] / 2048 * scale + 1, 1),
                "y": round(row["fields"]["Y"] / 2048 * scale + 1, 1),
            })
    return aetherytes


def node_member_ids(base):
    """Return the game item ids of all items inside a gathering node."""
    members = []
    for ref in base["fields"]["Item"]:
        if ref["row_id"] > 0:
            members.append(ref["fields"]["Item"]["row_id"])
    return members


def territory_aetheryte_name(territory):
    """Return the zone's aetheryte name, or None if the data has none."""
    aetheryte = territory.get("Aetheryte", {})
    if aetheryte.get("row_id", 0) > 0:
        return aetheryte["fields"]["PlaceName"]["fields"]["Name"]
    return None


NODE_TIME_FIELDS = (
    "EphemeralStartTime,EphemeralEndTime,"
    "GatheringRarePopTimeTable.StartTime,GatheringRarePopTimeTable.Duration"
)


def fetch_node_times(point_id):
    """Fetch the spawn windows of a gathering point as eorzea minute pairs."""
    url = f"{SHEET_URL}/GatheringPointTransient/{point_id}"
    data = get_json(url, {"fields": NODE_TIME_FIELDS})
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


def fetch_collectables():
    """Return all gathering collectables from memory, the cache file, or the api."""
    language = settings.get_language()
    with item_cache.fetch_lock(f"collectables:{language}"):
        if language in COLLECTABLES:
            return COLLECTABLES[language]
        data = item_cache.get_fresh_result(language, "collectables")
        if data is None:
            data = item_cache.counted_fetch(lookup_collectables)
            if data is not None:
                item_cache.store_result(language, data, "collectables")
        if data is not None:
            COLLECTABLES[language] = data
        return data


def lookup_collectables():
    """Fetch all gathering collectables with jobs, scrips and node positions."""
    items = collectable_items()
    if items is None:
        return None
    scrips = collectable_scrips()
    if scrips is None:
        return None
    nodes = collectable_nodes([item["gi_id"] for item in items])
    if nodes is None:
        return None
    download_job_icons({node["job_id"] for node in nodes.values()})
    entries = [build_collectable(item, scrips, nodes) for item in items]
    store_gathering_markers(entries)
    return entries


def store_gathering_markers(entries):
    """Cache each collectable's node info so adding it to a list needs no lookups."""
    markers = {}
    for entry in entries:
        markers[str(entry["game_id"])] = {
            "timed": entry["timed"],
            "times": entry["times"],
            "zone": entry["zone"],
            "aetheryte": entry["aetheryte"],
            "job_ids": [entry["job_id"]] if entry["job_id"] is not None else [],
            "x": entry["x"],
            "y": entry["y"],
        }
    item_cache.store_results(markers, "gathering")


def collectable_items():
    """Fetch all collectable gathering items in one request."""
    params = {
        "sheets": "GatheringItem",
        "query": "Item.IsCollectable=true",
        "limit": 500,
        "fields": "Item.Name,GatheringItemLevel.GatheringItemLevel,GatheringItemLevel.Stars",
        "language": settings.get_language(),
    }
    data = get_json(SEARCH_URL, params)
    if data is None:
        return None
    items = []
    for row in data["results"]:
        item = row["fields"]["Item"]
        if item["row_id"] > 0 and item["fields"]["Name"]:
            level = row["fields"]["GatheringItemLevel"]["fields"]
            items.append({
                "gi_id": row["row_id"],
                "game_id": item["row_id"],
                "name": item["fields"]["Name"],
                "level": level["GatheringItemLevel"],
                "stars": level["Stars"],
            })
    return items


SCRIP_FIELDS = (
    "Item,CollectablesShopRewardScrip.LowReward,"
    "CollectablesShopRewardScrip.MidReward,CollectablesShopRewardScrip.HighReward"
)


def collectable_scrips():
    """Map item ids to scrip rewards per tier, paging through the shop sheet."""
    params = {"sheets": "CollectablesShopItem", "query": "Item>0", "limit": 500, "fields": SCRIP_FIELDS}
    rewards = {}
    for _page in range(10):
        data = get_json(SEARCH_URL, params)
        if data is None:
            return None
        for row in data["results"]:
            add_scrip_reward(rewards, row)
        if "next" not in data:
            break
        params = {"cursor": data["next"], "limit": 500, "fields": SCRIP_FIELDS}
    return rewards


def add_scrip_reward(rewards, row):
    """Store one shop row's scrip amounts under its item id."""
    item_id = row["fields"]["Item"]["row_id"]
    scrip = row["fields"]["CollectablesShopRewardScrip"].get("fields", {})
    if item_id > 0 and scrip:
        rewards[item_id] = {
            "low": scrip["LowReward"],
            "mid": scrip["MidReward"],
            "high": scrip["HighReward"],
        }


def collectable_nodes(gi_ids):
    """Map gathering item ids to their node's job, zone, position and spawn times."""
    bases = gathering_bases(gi_ids)
    if bases is None:
        return None
    positions = node_positions(list(bases))
    zones = node_zones(list(bases))
    if positions is None or zones is None:
        return None
    times = node_times([zone["point_id"] for zone in zones.values()])
    if times is None:
        return None
    nodes = {}
    for base_id, base in bases.items():
        zone = zones.get(base_id)
        node_time = times.get(zone["point_id"], []) if zone else []
        node = build_node(base, positions.get(base_id), zone, node_time)
        for gi_id in base["members"]:
            nodes.setdefault(gi_id, node)
    return nodes


TRANSIENT_FIELDS = (
    "EphemeralStartTime,EphemeralEndTime,"
    "GatheringRarePopTimeTable.StartTime,GatheringRarePopTimeTable.Duration"
)


def node_times(point_ids):
    """Fetch spawn windows for the given gathering points in batches."""
    times = {}
    for chunk in chunked(sorted(set(point_ids)), 100):
        rows = ",".join(str(point_id) for point_id in chunk)
        data = get_json(f"{SHEET_URL}/GatheringPointTransient", {"rows": rows, "fields": TRANSIENT_FIELDS})
        if data is None:
            return None
        for row in data["rows"]:
            times[row["row_id"]] = rare_pop_times(row["fields"]) + ephemeral_times(row["fields"])
    return times


def gathering_bases(gi_ids):
    """Fetch the gathering point bases containing the given gathering items."""
    bases = {}
    for chunk in chunked(gi_ids, 40):
        query = " ".join(f"Item[]={gi_id}" for gi_id in chunk)
        results = search_rows("GatheringPointBase", query, "Item[].IsHidden,GatheringType.Name", limit=100)
        if results is None:
            return None
        for base in results:
            bases[base["row_id"]] = {
                "job": base["fields"]["GatheringType"]["fields"]["Name"],
                "job_id": base["fields"]["GatheringType"]["row_id"],
                "members": [ref["row_id"] for ref in base["fields"]["Item"] if ref["row_id"] > 0],
            }
    return bases


def node_positions(base_ids):
    """Fetch raw world coordinates for the node bases by paging the whole sheet."""
    wanted = set(base_ids)
    positions = {}
    params = {"limit": 500, "fields": "X,Y"}
    for _page in range(10):
        data = get_json(f"{SHEET_URL}/ExportedGatheringPoint", params)
        if data is None:
            return None
        for row in data["rows"]:
            if row["row_id"] in wanted:
                positions[row["row_id"]] = (row["fields"]["X"], row["fields"]["Y"])
        if len(data["rows"]) < params["limit"]:
            break
        params = dict(params, after=data["rows"][-1]["row_id"])
    return positions


ZONE_FIELDS = (
    "GatheringPointBase.GatheringLevel,TerritoryType.PlaceName.Name,"
    "TerritoryType.Aetheryte.PlaceName.Name,"
    "TerritoryType.Map.SizeFactor,TerritoryType.Map.OffsetX,TerritoryType.Map.OffsetY"
)


def node_zones(base_ids):
    """Fetch zone names and map scale data for the given node bases."""
    zones = {}
    for chunk in chunked(base_ids, 25):
        query = " ".join(f"GatheringPointBase={base_id}" for base_id in chunk)
        results = search_rows("GatheringPoint", query, ZONE_FIELDS, limit=100)
        if results is None:
            return None
        for point in results:
            add_zone(zones, point)
    return zones


def add_zone(zones, point):
    """Store one gathering point's zone and map data under its base id."""
    base_id = point["fields"]["GatheringPointBase"]["row_id"]
    territory = point["fields"]["TerritoryType"]["fields"]
    name = territory["PlaceName"].get("fields", {}).get("Name")
    if not name:
        return
    map_fields = territory["Map"].get("fields", {})
    zones.setdefault(base_id, {
        "name": name,
        "point_id": point["row_id"],
        "aetheryte": territory_aetheryte_name(territory),
        "size_factor": map_fields.get("SizeFactor", 100),
        "offset_x": map_fields.get("OffsetX", 0),
        "offset_y": map_fields.get("OffsetY", 0),
    })


def build_node(base, position, zone, times):
    """Combine base, position, zone and time data into one node description."""
    node = {
        "job": base["job"],
        "job_id": base["job_id"],
        "zone": None,
        "aetheryte": None,
        "x": None,
        "y": None,
        "times": times,
        "timed": len(times) > 0,
    }
    if zone:
        node["zone"] = zone["name"]
        node["aetheryte"] = zone["aetheryte"]
        if position:
            node["x"] = to_map_coord(position[0], zone["offset_x"], zone["size_factor"])
            node["y"] = to_map_coord(position[1], zone["offset_y"], zone["size_factor"])
    return node


def build_collectable(item, scrips, nodes):
    """Combine item, scrip and node data into one collectable entry."""
    node = nodes.get(item["gi_id"]) or build_node({"job": None, "job_id": None}, None, None, [])
    return {
        "game_id": item["game_id"],
        "name": item["name"],
        "level": item["level"],
        "stars": item["stars"],
        "scrips": scrips.get(item["game_id"]),
        "job": node["job"],
        "job_id": node["job_id"],
        "zone": node["zone"],
        "aetheryte": node["aetheryte"],
        "x": node["x"],
        "y": node["y"],
        "times": node["times"],
        "timed": node["timed"],
    }


def download_craft_icon(icon_id):
    """Download one crafting job icon once; later reads come from the cache."""
    key = f"crafticon_{icon_id}"
    with item_cache.fetch_lock(f"icon:{key}"):
        if key in DOWNLOADED_ICONS or item_cache.has_icon(key):
            DOWNLOADED_ICONS.add(key)
            return
        png = fetch_asset(f"ui/icon/062000/{icon_id:06d}.tex")
        if png:
            item_cache.store_icon(key, png)
            DOWNLOADED_ICONS.add(key)


def ensure_job_type_icon(type_id):
    """Download one gathering job icon if it is not cached yet."""
    with item_cache.fetch_lock(f"icon:jobtype_{type_id}"):
        if not item_cache.has_icon(f"jobtype_{type_id}"):
            download_job_icons({type_id})


def download_job_icons(job_ids):
    """Download the gathering job icons once."""
    data = get_json(f"{SHEET_URL}/GatheringType", {"fields": "IconMain"})
    if data is None:
        return
    for row in data["rows"]:
        key = f"jobtype_{row['row_id']}"
        if row["row_id"] in job_ids and not item_cache.has_icon(key):
            png = fetch_asset(row["fields"]["IconMain"]["path"])
            if png:
                item_cache.store_icon(key, png)


def to_map_coord(world, offset, size_factor):
    """Convert a raw world coordinate into the in game map coordinate."""
    scale = size_factor / 100
    return round(((world + offset) * scale + 1024) / 2048 * 41 / scale + 1, 1)


def chunked(values, size):
    """Split values into lists of at most the given size."""
    values = list(values)
    return [values[i:i + size] for i in range(0, len(values), size)]


def fetch_craftables():
    """Return all craftable collectables from memory, the cache file, or the api."""
    language = settings.get_language()
    with item_cache.fetch_lock(f"craftables:{language}"):
        if language in CRAFTABLES:
            return CRAFTABLES[language]
        data = item_cache.get_fresh_result(language, "craftables")
        if data and "ingredients" not in data[0]:
            data = None
        if data is None:
            data = item_cache.counted_fetch(lookup_craftables)
            if data is not None:
                item_cache.store_result(language, data, "craftables")
        if data is not None:
            CRAFTABLES[language] = data
        return data


def lookup_craftables():
    """Fetch all craftable collectables with their jobs and scrip rewards."""
    recipes = collectable_recipes()
    if recipes is None:
        return None
    scrips = collectable_scrips()
    if scrips is None:
        return None
    return build_craftables(recipes, scrips)


RECIPE_LIST_FIELDS = (
    "ItemResult.Name,CraftType.Name,"
    "RecipeLevelTable.ClassJobLevel,RecipeLevelTable.Stars,"
    "AmountResult,Ingredient[].Name,AmountIngredient"
)


def collectable_recipes():
    """Fetch all recipes producing collectables, paging through the recipe sheet."""
    params = {
        "sheets": "Recipe",
        "query": "ItemResult.IsCollectable=true",
        "limit": 500,
        "fields": RECIPE_LIST_FIELDS,
        "language": settings.get_language(),
    }
    recipes = []
    for _page in range(10):
        data = get_json(SEARCH_URL, params)
        if data is None:
            return None
        recipes.extend(data["results"])
        if "next" not in data:
            break
        params = {"cursor": data["next"], "limit": 500, "fields": RECIPE_LIST_FIELDS}
    return recipes


def build_craftables(recipes, scrips):
    """Group recipes by their result item into craftable collectable entries."""
    entries = {}
    for recipe in recipes:
        item = recipe["fields"]["ItemResult"]
        if item["row_id"] <= 0 or not item["fields"]["Name"]:
            continue
        level = recipe["fields"]["RecipeLevelTable"]["fields"]
        entry = entries.setdefault(item["row_id"], {
            "game_id": item["row_id"],
            "name": item["fields"]["Name"],
            "level": level["ClassJobLevel"],
            "stars": level["Stars"],
            "jobs": [],
            "scrips": scrips.get(item["row_id"]),
            "yields": recipe["fields"]["AmountResult"],
            "ingredients": recipe_ingredients(recipe["fields"]),
        })
        job = recipe["fields"]["CraftType"]["fields"]["Name"]
        if job not in entry["jobs"]:
            entry["jobs"].append(job)
    return list(entries.values())


RAW_ITEM_FIELD = "Item@as(raw)"
SPECIAL_SHOP_FIELDS = (
    "Item[].Item@as(raw),Item[].ItemCost@as(raw),Item[].CurrencyCost,Item[].CostType,"
    "Item[].ReceiveCount,Item[].Quest@as(raw),Item[].AchievementUnlock@as(raw)"
)
TRANSIENT_RAW_FIELDS = "EphemeralStartTime,GatheringRarePopTimeTable@as(raw)"
BICOLOR_GEMSTONE_ID = 26807
GIL_ITEM_ID = 1
COST_TYPE_TOMESTONE = 2
COST_TYPE_SCRIP = 3
SCRIP_COST_INDEXES = {2: 33913, 4: 33914, 6: 41784, 7: 41785}
SCRIP_ITEM_IDS = set(SCRIP_COST_INDEXES.values())
REQUIRED_SOURCE_KEYS = ("timed", "gemstone", "scrip", "currency", "prices", "reducible", "reduction")


def fetch_material_sources():
    """Return item ids by acquisition source from memory, the cache file, or the api."""
    with item_cache.fetch_lock("material_sources"):
        if MATERIAL_SOURCES:
            return dict(MATERIAL_SOURCES)
        data = item_cache.get_fresh_result("all", "material_sources")
        if data and any(key not in data for key in REQUIRED_SOURCE_KEYS):
            data = None
        if data is None:
            data = item_cache.counted_fetch(lookup_material_sources)
            if data is not None:
                item_cache.store_result("all", data, "material_sources")
        if data is not None:
            MATERIAL_SOURCES.update(data)
        return data


def lookup_material_sources():
    """Fetch which items are gatherable, bought, unlock gated or on timed nodes only."""
    nodes = node_item_sources()
    if nodes is None:
        return None
    gatherable, timed = nodes
    for sheet in ("FishParameter", "SpearfishingItem"):
        ids = sheet_item_ids(sheet)
        if ids is None:
            return None
        gatherable.update(ids)
    gil = sheet_item_ids("GilShopItem")
    if gil is None:
        return None
    seals = sheet_item_ids("GCScripShopItem")
    if seals is None:
        return None
    trades = special_shop_items()
    if trades is None:
        return None
    reducible = search_item_ids("AetherialReduce>=1")
    if reducible is None:
        return None
    aethersands = search_item_ids('Name~"aethersand"')
    if aethersands is None:
        return None
    return {
        "gatherable": sorted(gatherable),
        "timed": sorted(timed),
        "reducible": reducible,
        "reduction": aethersands,
        "gil": sorted(gil),
        "special": sorted(trades["open"] | trades["locked"] | set(seals)),
        "locked": sorted(trades["locked"] - trades["open"] - set(seals)),
        "gemstone": sorted(trades["gemstone"] - trades["nongemstone"]),
        "scrip": scrip_only_prices(trades),
        "currency": trades["currency"],
        "prices": trades["prices"],
    }


CURRENCY_CATEGORY_QUERY = "ItemUICategory=100"


def fetch_currency_shop():
    """Return what every currency buys from memory, the cache file, or the api."""
    with item_cache.fetch_lock("currency_shop"):
        if CURRENCY_SHOP:
            return dict(CURRENCY_SHOP)
        data = item_cache.get_fresh_result("all", "currency_shop")
        if data is None:
            data = item_cache.counted_fetch(lookup_currency_shop)
            if data is not None:
                item_cache.store_result("all", data, "currency_shop")
        if data is not None:
            CURRENCY_SHOP.update(data)
        return data


def lookup_currency_shop():
    """Collect the special shop offers that are paid with exactly one real currency."""
    currencies = search_item_ids(CURRENCY_CATEGORY_QUERY)
    if currencies is None:
        return None
    tomestones = tomestone_currency_ids()
    if tomestones is None:
        return None
    currency_ids = set(currencies) | set(tomestones.values())
    shops = sheet_rows("SpecialShop", SPECIAL_SHOP_FIELDS, limit=100)
    if shops is None:
        return None
    offers = {}
    for fields in shops.values():
        for trade in fields["Item"]:
            collect_currency_offer(trade, offers, currency_ids, tomestones)
    return offers


def collect_currency_offer(trade, offers, currency_ids, tomestones):
    """Record one trade under its currency when a single known currency pays it."""
    costs = trade_costs(trade, tomestones)
    if len(costs) != 1 or costs[0][0] not in currency_ids:
        return
    currency, cost = costs[0]
    gated = trade.get("Quest@as(raw)", 0) > 0 or trade.get("AchievementUnlock@as(raw)", 0) > 0
    counts = trade.get("ReceiveCount", [])
    for slot, item_id in enumerate(trade.get(RAW_ITEM_FIELD, [])):
        if item_id <= 0:
            continue
        amount = max(counts[slot] if slot < len(counts) else 1, 1)
        keep_cheapest_offer(offers, currency, item_id, cost, amount, gated)


def keep_cheapest_offer(offers, currency, item_id, cost, amount, gated):
    """Keep the best price per received unit for one currency and item pair."""
    entries = offers.setdefault(str(currency), {})
    known = entries.get(str(item_id))
    if known is None or cost / amount < known["cost"] / known["amount"]:
        entries[str(item_id)] = {"cost": cost, "amount": amount, "locked": gated}


VENTURE_TASK_FIELDS = (
    "RetainerLevel,VentureCost,MaxTimemin,Task@as(raw),ClassJobCategory@as(raw),"
    "RetainerTaskParameter.ItemLevelDoW,RetainerTaskParameter.PerceptionDoL,"
    "RetainerTaskParameter.PerceptionFSH"
)
VENTURE_TASK_QUERY = "+IsRandom=false +Task>0"


def fetch_ventures():
    """Return all normal retainer ventures from memory, the cache file, or the api."""
    with item_cache.fetch_lock("ventures"):
        if VENTURES:
            return list(VENTURES)
        data = item_cache.get_fresh_result("all", "ventures")
        if data and "minutes" not in data[0]:
            data = None
        if data is None:
            data = item_cache.counted_fetch(lookup_ventures)
            if data is not None:
                item_cache.store_result("all", data, "ventures")
        if data is not None:
            VENTURES.extend(data)
        return data


def lookup_ventures():
    """Collect every normal retainer venture with its reward and quantity tiers."""
    tasks = search_sheet_rows("RetainerTask", VENTURE_TASK_QUERY, VENTURE_TASK_FIELDS)
    if tasks is None:
        return None
    rewards = sheet_rows("RetainerTaskNormal", "Item@as(raw),Quantity")
    if rewards is None:
        return None
    jobs = venture_job_keys({row["fields"]["ClassJobCategory@as(raw)"] for row in tasks})
    if jobs is None:
        return None
    ventures = []
    for row in tasks:
        venture = build_venture(row["fields"], rewards, jobs)
        if venture is not None:
            ventures.append(venture)
    return ventures


def build_venture(fields, rewards, jobs):
    """Build one venture entry from its task row and reward row."""
    reward = rewards.get(fields["Task@as(raw)"])
    if reward is None or reward["Item@as(raw)"] <= 0:
        return None
    job = jobs[fields["ClassJobCategory@as(raw)"]]
    return {
        "item": reward["Item@as(raw)"],
        "level": fields["RetainerLevel"],
        "cost": max(fields["VentureCost"], 1),
        "minutes": fields["MaxTimemin"],
        "job": job,
        "quantities": reward["Quantity"],
        "breakpoints": venture_breakpoints(job, fields["RetainerTaskParameter"]["fields"]),
    }


def venture_breakpoints(job, params):
    """Return the stat thresholds of the venture's quantity tiers for one job."""
    if job == "battle":
        return params["ItemLevelDoW"]
    if job == "fisher":
        return params["PerceptionFSH"]
    return params["PerceptionDoL"]


def venture_job_keys(category_ids):
    """Map class job category ids to the retainer job keys they stand for."""
    keys = {}
    for category_id in category_ids:
        data = get_json(f"{SHEET_URL}/ClassJobCategory/{category_id}", {"fields": "MIN,BTN,FSH"})
        if data is None:
            return None
        keys[category_id] = job_key_from_flags(data["fields"])
    return keys


def job_key_from_flags(flags):
    """Turn one class job category's flags into a retainer job key."""
    if flags.get("MIN"):
        return "miner"
    if flags.get("BTN"):
        return "botanist"
    if flags.get("FSH"):
        return "fisher"
    return "battle"


def search_sheet_rows(sheet, query, fields):
    """Search one sheet and return all matching rows, paging the results."""
    params = {"sheets": sheet, "query": query, "limit": 500, "fields": fields,
              "language": settings.get_language()}
    rows = []
    for _page in range(40):
        data = get_json(SEARCH_URL, params)
        if data is None:
            return None
        rows.extend(data["results"])
        if "next" not in data:
            break
        params = {"cursor": data["next"], "limit": 500, "fields": fields}
    return rows


def fetch_item_names(game_ids):
    """Return display names by item id, fetching all missing ones in one call."""
    language = settings.get_language()
    with item_cache.fetch_lock(f"item_names:{language}"):
        names = {}
        missing = []
        for game_id in game_ids:
            cached = item_cache.get_fresh_result(f"{language}:{game_id}", "item_name")
            if cached is None:
                missing.append(game_id)
            else:
                names[game_id] = cached
        if missing:
            names.update(lookup_item_names(missing, language))
        return names


def lookup_item_names(game_ids, language):
    """Fetch the names of the item ids in one sheet call and cache them."""
    data = get_json(f"{SHEET_URL}/Item", {
        "rows": ",".join(str(game_id) for game_id in game_ids),
        "fields": "Name",
        "language": language,
        "limit": len(game_ids),
    })
    if data is None:
        return {}
    names = {row["row_id"]: row["fields"]["Name"] for row in data["rows"]}
    item_cache.store_results(
        {f"{language}:{game_id}": name for game_id, name in names.items()}, "item_name"
    )
    return names


def scrip_only_prices(trades):
    """Keep the scrip prices of the items that are sold for scrips alone."""
    return {
        item_id: info for item_id, info in trades["scrip"].items()
        if int(item_id) not in trades["nonscrip"]
    }


def node_item_sources():
    """Return all node gatherable item ids and the ones found on timed nodes only."""
    gi_map = gathering_item_map()
    if gi_map is None:
        return None
    base_members = sheet_rows("GatheringPointBase", RAW_ITEM_FIELD)
    if base_members is None:
        return None
    point_bases = sheet_rows("GatheringPoint", "GatheringPointBase@as(raw)")
    if point_bases is None:
        return None
    transients = sheet_rows("GatheringPointTransient", TRANSIENT_RAW_FIELDS)
    if transients is None:
        return None
    pointed_bases = {fields["GatheringPointBase@as(raw)"] for fields in point_bases.values()}
    timed_bases = timed_base_ids(point_bases, transients)
    return classify_node_items(gi_map, base_members, pointed_bases, timed_bases)


def classify_node_items(gi_map, base_members, pointed_bases, timed_bases):
    """Split node items into all gatherable ids and the ids on timed nodes only."""
    gatherable = set()
    timed = set()
    untimed = set()
    for base_id, fields in base_members.items():
        for gi_id in fields[RAW_ITEM_FIELD]:
            item_id = gi_map.get(gi_id)
            if item_id is None:
                continue
            gatherable.add(item_id)
            if base_id in timed_bases:
                timed.add(item_id)
            elif base_id in pointed_bases:
                untimed.add(item_id)
    return gatherable, timed - untimed


def timed_base_ids(point_bases, transients):
    """Return the node base ids whose gathering points only spawn in time windows."""
    timed = set()
    for point_id, fields in point_bases.items():
        base_id = fields["GatheringPointBase@as(raw)"]
        if base_id > 0 and transient_is_timed(transients.get(point_id)):
            timed.add(base_id)
    return timed


def transient_is_timed(fields):
    """Check whether a gathering point's spawns are bound to time windows."""
    if fields is None:
        return False
    if fields["GatheringRarePopTimeTable@as(raw)"] > 0:
        return True
    return fields["EphemeralStartTime"] != NO_TIME


def gathering_item_map():
    """Map gathering item row ids to their item ids, paging the GatheringItem sheet."""
    params = {"sheets": "GatheringItem", "query": "Item>0", "limit": 500, "fields": RAW_ITEM_FIELD}
    mapping = {}
    for _page in range(40):
        data = get_json(SEARCH_URL, params)
        if data is None:
            return None
        for row in data["results"]:
            mapping[row["row_id"]] = row["fields"][RAW_ITEM_FIELD]
        if "next" not in data:
            break
        params = {"cursor": data["next"], "limit": 500, "fields": RAW_ITEM_FIELD}
    return mapping


MARKET_ICON_ID = 60570


def ensure_market_icon():
    """Download the market board symbol once and return its icon file name."""
    key = f"symbol_{MARKET_ICON_ID}"
    with item_cache.fetch_lock(f"icon:{key}"):
        if key in DOWNLOADED_ICONS or item_cache.has_icon(key):
            DOWNLOADED_ICONS.add(key)
            return f"{key}.png"
        png = fetch_asset(f"ui/icon/060000/{MARKET_ICON_ID:06d}.tex")
        if png:
            item_cache.store_icon(key, png)
            DOWNLOADED_ICONS.add(key)
        return f"{key}.png"


def fetch_item_details(game_id):
    """Return an item's gil price and market availability, cached."""
    with item_cache.fetch_lock(f"item_details:{game_id}"):
        cached = item_cache.get_fresh_result(str(game_id), "item_details")
        if cached is not None:
            return cached
        data = get_json(f"{SHEET_URL}/Item/{game_id}",
                        {"fields": "PriceMid,ItemSearchCategory@as(raw)"})
        if data is None:
            return None
        details = {
            "price": data["fields"]["PriceMid"],
            "marketable": data["fields"]["ItemSearchCategory@as(raw)"] > 0,
        }
        item_cache.store_result(str(game_id), details, "item_details")
        return details


def fetch_item_offers(game_id):
    """Return the item's shop offers with prices and vendors, cached per language."""
    key = f"{settings.get_language()}:{game_id}"
    with item_cache.fetch_lock(f"offers:{key}"):
        cached = item_cache.get_fresh_result(key, "offers")
        if cached is not None:
            return cached
        offers = lookup_item_offers(game_id)
        if offers is not None:
            item_cache.store_result(key, offers, "offers")
        return offers


MAX_GIL_SHOPS = 3
MAX_SPECIAL_SHOPS = 5


def lookup_item_offers(game_id):
    """Collect the item's gil and special shop offers, each with its vendor."""
    offers = gil_offers(game_id)
    if offers is None:
        return None
    special = special_offers(game_id)
    if special is None:
        return None
    return distinct_offers(offers + special)


def gil_offers(game_id):
    """Build one offer per gil shop selling the item."""
    rows = search_rows("GilShopItem", f"Item={game_id}", limit=20)
    if rows is None:
        return None
    shop_ids = []
    for row in rows:
        if row["row_id"] not in shop_ids:
            shop_ids.append(row["row_id"])
    if not shop_ids:
        return []
    details = fetch_item_details(game_id)
    price = details["price"] if details else None
    offers = []
    for shop_id in shop_ids[:MAX_GIL_SHOPS]:
        offer = build_offer(shop_id, None, GIL_ITEM_ID, price)
        if offer is None:
            return None
        offers.append(offer)
    return offers


SPECIAL_OFFER_FIELDS = f"Name,{SPECIAL_SHOP_FIELDS}"


def special_offers(game_id):
    """Build one offer per special shop selling the item."""
    rows = search_rows("SpecialShop", f"Item[].Item[]={game_id}", SPECIAL_OFFER_FIELDS, limit=MAX_SPECIAL_SHOPS)
    if rows is None:
        return None
    if not rows:
        return []
    tomestones = tomestone_currency_ids()
    if tomestones is None:
        return None
    offers = []
    for row in rows:
        currency, price = shop_item_cost(row["fields"]["Item"], game_id, tomestones)
        offer = build_offer(row["row_id"], row["fields"]["Name"] or None, currency, price)
        if offer is None:
            return None
        offers.append(offer)
    return offers


def shop_item_cost(shop_trades, game_id, tomestones):
    """Return the currency and price of the first trade giving the item."""
    for trade in shop_trades:
        if game_id not in trade.get(RAW_ITEM_FIELD, []):
            continue
        costs = trade_costs(trade, tomestones)
        if costs:
            return costs[0]
    return None, None


def build_offer(shop_id, shop_name, currency, price):
    """Combine one shop's price with its located vendor, or None on api errors."""
    vendor = shop_vendor(shop_id)
    if vendor is None:
        return None
    return {"shop": shop_name, "currency": currency, "price": price, "vendor": vendor or None}


def distinct_offers(offers):
    """Drop duplicated offers, preferring the ones with a located vendor."""
    offers = sorted(offers, key=lambda offer: (offer["vendor"] is None, offer["shop"] is None))
    seen = set()
    kept = []
    for offer in offers:
        vendor = offer["vendor"] or {}
        name = vendor.get("name") or offer["shop"]
        if name is None and any(same_deal(offer, other) for other in kept):
            continue
        key = (name, offer["currency"], offer["price"])
        if key not in seen:
            seen.add(key)
            kept.append(offer)
    return kept


def same_deal(offer, other):
    """Check whether two offers ask the same price in the same currency."""
    return offer["currency"] == other["currency"] and offer["price"] == other["price"]


def shop_vendor(shop_id):
    """Return the located npc offering one shop, {} when unknown, cached per shop."""
    key = f"{settings.get_language()}:{shop_id}"
    cached = item_cache.get_fresh_result(key, "shop_vendor")
    if cached is not None:
        return cached
    vendor = lookup_shop_vendor(shop_id)
    if vendor is not None:
        item_cache.store_result(key, vendor, "shop_vendor")
    return vendor


def lookup_shop_vendor(shop_id):
    """Find and locate one npc that offers the shop, {} when none is known."""
    npcs = search_rows("ENpcBase", f"ENpcData[]={shop_id}", limit=3)
    if npcs is None:
        return None
    for npc in npcs:
        located = npc_location(npc["row_id"])
        if located is None:
            return None
        if located:
            return located
    return {}


def npc_location(npc_id):
    """Return one npc's name, zone, position and closest aetheryte, {} when unplaced."""
    levels = search_rows("Level", f"Object={npc_id}", "X,Z,Territory@as(raw)")
    if levels is None:
        return None
    if not levels:
        return {}
    name = npc_name(npc_id)
    if name is None:
        return None
    fields = levels[0]["fields"]
    territory_id = fields["Territory@as(raw)"]
    place = fetch_territory_info(territory_id)
    if place is None:
        return None
    x = to_map_coord(fields["X"], place["offset_x"], place["size_factor"])
    y = to_map_coord(fields["Z"], place["offset_y"], place["size_factor"])
    aetheryte = closest_aetheryte(territory_id, place["size_factor"], x, y)
    return {
        "name": name,
        "zone": place["zone"],
        "aetheryte": aetheryte or place["aetheryte"],
        "x": x,
        "y": y,
    }


def npc_name(npc_id):
    """Return one npc's display name, or None on api errors."""
    url = f"{SHEET_URL}/ENpcResident/{npc_id}"
    data = get_json(url, {"fields": "Singular", "language": settings.get_language()})
    if data is None:
        return None
    return data["fields"]["Singular"]


TERRITORY_FIELDS = (
    "PlaceName.Name,Aetheryte.PlaceName.Name,"
    "Map.SizeFactor,Map.OffsetX,Map.OffsetY"
)


def fetch_territory_info(territory_id):
    """Return one territory's zone name, fallback aetheryte and map maths, cached."""
    key = f"{settings.get_language()}:{territory_id}"
    cached = item_cache.get_fresh_result(key, "territory")
    if cached is not None:
        return cached
    url = f"{SHEET_URL}/TerritoryType/{territory_id}"
    data = get_json(url, {"fields": TERRITORY_FIELDS, "language": settings.get_language()})
    if data is None:
        return None
    fields = data["fields"]
    map_fields = fields.get("Map", {}).get("fields", {})
    info = {
        "zone": fields["PlaceName"]["fields"]["Name"],
        "aetheryte": territory_aetheryte_name(fields),
        "size_factor": map_fields.get("SizeFactor", 100),
        "offset_x": map_fields.get("OffsetX", 0),
        "offset_y": map_fields.get("OffsetY", 0),
    }
    item_cache.store_result(key, info, "territory")
    return info


def sheet_rows(sheet, fields, limit=500):
    """Return one whole sheet as row id to fields, paging through it."""
    url = f"{SHEET_URL}/{sheet}"
    params = {"limit": limit, "fields": fields}
    rows = {}
    for _page in range(40):
        data = get_json(url, params)
        if data is None:
            return None
        for row in data["rows"]:
            rows[row["row_id"]] = row["fields"]
        if len(data["rows"]) < limit:
            break
        params = dict(params, after=data["rows"][-1]["row_id"])
    return rows


def search_item_ids(query):
    """Collect the item ids matching one english Item sheet search, paging the results."""
    params = {"sheets": "Item", "query": query, "limit": 500, "language": "en", "fields": "Name"}
    ids = set()
    for _page in range(40):
        data = get_json(SEARCH_URL, params)
        if data is None:
            return None
        for row in data["results"]:
            ids.add(row["row_id"])
        if "next" not in data:
            break
        params = {"cursor": data["next"], "limit": 500, "fields": "Name"}
    return sorted(ids)


def sheet_item_ids(sheet):
    """Collect the distinct item ids of one sheet's Item column, paging the sheet."""
    params = {"sheets": sheet, "query": "Item>0", "limit": 500, "fields": RAW_ITEM_FIELD}
    ids = set()
    for _page in range(40):
        data = get_json(SEARCH_URL, params)
        if data is None:
            return None
        for row in data["results"]:
            ids.add(row["fields"][RAW_ITEM_FIELD])
        if "next" not in data:
            break
        params = {"cursor": data["next"], "limit": 500, "fields": RAW_ITEM_FIELD}
    return sorted(ids)


def special_shop_items():
    """Collect special shop items by unlock gating, cost currency and scrip price."""
    tomestones = tomestone_currency_ids()
    if tomestones is None:
        return None
    shops = sheet_rows("SpecialShop", SPECIAL_SHOP_FIELDS, limit=100)
    if shops is None:
        return None
    trades = {
        "open": set(), "locked": set(),
        "gemstone": set(), "nongemstone": set(),
        "scrip": {}, "nonscrip": set(),
        "currency": {}, "prices": {},
    }
    for fields in shops.values():
        for trade in fields["Item"]:
            collect_special_trade(trade, trades, tomestones)
    return trades


def tomestone_currency_ids():
    """Map tomestone cost indexes to their currency item ids, cached."""
    with item_cache.fetch_lock("tomestones"):
        if TOMESTONES:
            return dict(TOMESTONES)
        data = item_cache.get_fresh_result("all", "tomestones")
        if data is None:
            data = lookup_tomestone_ids()
            if data is not None:
                item_cache.store_result("all", data, "tomestones")
        if data is None:
            return None
        mapping = {int(index): item_id for index, item_id in data.items()}
        TOMESTONES.update(mapping)
        return mapping


def lookup_tomestone_ids():
    """Fetch the tomestone index to currency item id mapping."""
    rows = sheet_rows("TomestonesItem", "Item@as(raw),Tomestones@as(raw)")
    if rows is None:
        return None
    mapping = {}
    for fields in rows.values():
        if fields["Tomestones@as(raw)"] > 0 and fields[RAW_ITEM_FIELD] > 0:
            mapping[str(fields["Tomestones@as(raw)"])] = fields[RAW_ITEM_FIELD]
    return mapping


def collect_special_trade(trade, trades, tomestones):
    """Sort one trade's received items by unlock gating and by cost currency."""
    gated = trade.get("Quest@as(raw)", 0) > 0 or trade.get("AchievementUnlock@as(raw)", 0) > 0
    costs = trade_costs(trade, tomestones)
    cost_ids = {cost_id for cost_id, _amount in costs if cost_id}
    for slot, item_id in enumerate(trade.get(RAW_ITEM_FIELD, [])):
        if item_id <= 0:
            continue
        trades["locked" if gated else "open"].add(item_id)
        if cost_ids:
            trades["currency"].setdefault(str(item_id), costs[0][0])
            trades["prices"].setdefault(str(item_id), costs[0][1])
        if cost_ids == {BICOLOR_GEMSTONE_ID}:
            trades["gemstone"].add(item_id)
        else:
            trades["nongemstone"].add(item_id)
        if cost_ids and cost_ids <= SCRIP_ITEM_IDS:
            record_scrip_price(trades["scrip"], item_id, costs, trade, slot)
        else:
            trades["nonscrip"].add(item_id)


def trade_costs(trade, tomestones):
    """Resolve one trade's cost slots into currency item ids and amounts."""
    types = trade.get("CostType", [])
    ids = trade.get("ItemCost@as(raw)", [])
    amounts = trade.get("CurrencyCost", [])
    costs = []
    for slot in range(min(len(ids), len(amounts))):
        if amounts[slot] <= 0 or ids[slot] <= 0:
            continue
        cost_type = types[slot] if slot < len(types) else 0
        costs.append((resolve_cost_item(cost_type, ids[slot], tomestones), amounts[slot]))
    return costs


def resolve_cost_item(cost_type, cost_value, tomestones):
    """Return a cost slot's currency item id, translating indexed currencies."""
    if cost_type == COST_TYPE_SCRIP:
        return SCRIP_COST_INDEXES.get(cost_value)
    if cost_type == COST_TYPE_TOMESTONE:
        return tomestones.get(cost_value)
    return cost_value


def record_scrip_price(prices, item_id, costs, trade, slot):
    """Remember the cheapest scrip price and bundle size of one received item."""
    price = sum(amount for cost_id, amount in costs if cost_id in SCRIP_ITEM_IDS)
    currency = next(cost_id for cost_id, _amount in costs if cost_id in SCRIP_ITEM_IDS)
    counts = trade.get("ReceiveCount", [])
    bundle = max(counts[slot] if slot < len(counts) else 1, 1)
    known = prices.get(str(item_id))
    if known is None or price / bundle < known["price"] / known["bundle"]:
        prices[str(item_id)] = {"price": price, "bundle": bundle, "currency": currency}


def search_rows(sheet, query, fields=None, limit=1):
    """Search one sheet and return the result rows, or None on network errors."""
    params = {"sheets": sheet, "query": query, "limit": limit, "language": settings.get_language()}
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


def fetch_optional_json(url, params):
    """Fetch json where a missing row is expected and does not count as an api failure."""
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
    except requests.RequestException:
        return None
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
