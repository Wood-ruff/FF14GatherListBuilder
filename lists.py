import json
import math
import re
from pathlib import Path

import settings
import storage
import xivapi

VALID_LIST_NAME = re.compile(r"^[\w ,'-]{1,50}$", re.UNICODE)
MAX_RECIPE_DEPTH = 10
ALARMS_DIR = Path(__file__).parent / "static" / "alarms"
AUDIO_PATTERNS = ("*.mp3", "*.wav", "*.ogg")


def normalize_spaces(text):
    """Collapse repeated spaces to one and remove leading and trailing spaces."""
    return " ".join(text.split())


def is_valid_list_name(list_name):
    """Check that a list name is safe to use as a file name."""
    return bool(VALID_LIST_NAME.match(list_name))


def get_list_names():
    """Return the names of all saved lists."""
    return storage.get_list_names()


def get_items(list_name):
    """Return the items of the named list."""
    list_name = normalize_spaces(list_name)
    if not is_valid_list_name(list_name):
        return []
    return storage.load_items(list_name)


def add_item(list_name, item_name, amount):
    """Add an amount of an item to the named list, summing up existing entries."""
    list_name = normalize_spaces(list_name)
    item_name = normalize_spaces(item_name)
    if not is_valid_list_name(list_name):
        return
    items = storage.load_items(list_name)
    existing = find_item(items, item_name)
    if existing:
        existing["amount"] += amount
    else:
        items.append(new_item(items, item_name, amount))
    storage.save_items(list_name, items)


def new_item(items, item_name, amount):
    """Build a new list entry, preferring the item name the api returns."""
    game_item = xivapi.fetch_item(item_name)
    game_id = None
    gathering = None
    if game_item:
        item_name = game_item["fields"]["Name"]
        game_id = game_item["row_id"]
        gathering = xivapi.fetch_gathering(game_id)
    return {
        "id": next_item_id(items),
        "name": item_name,
        "amount": amount,
        "game_id": game_id,
        "gathering": gathering,
    }


def add_crafted_item(list_name, item_name, amount):
    """Add all base materials needed to craft an item to the named list."""
    list_name = normalize_spaces(list_name)
    item_name = normalize_spaces(item_name)
    if not is_valid_list_name(list_name):
        return
    add_ingredients_of(list_name, item_name, amount, depth=0)


def add_ingredients_of(list_name, item_name, amount, depth):
    """Resolve recipes recursively, adding items without a recipe to the list."""
    recipe = xivapi.fetch_recipe(item_name)
    if not recipe or depth >= MAX_RECIPE_DEPTH:
        add_item(list_name, item_name, amount)
        return
    crafts = math.ceil(amount / recipe["yields"])
    for ingredient in recipe["ingredients"]:
        add_ingredients_of(list_name, ingredient["name"], ingredient["amount"] * crafts, depth + 1)


def update_item(list_name, item_id, amount):
    """Change the amount of an item in the named list."""
    list_name = normalize_spaces(list_name)
    if not is_valid_list_name(list_name):
        return
    items = storage.load_items(list_name)
    item = find_item_by_id(items, item_id)
    if not item:
        return
    item["amount"] = amount
    storage.save_items(list_name, items)


def remove_item(list_name, item_id):
    """Delete the item with the given id from the named list."""
    list_name = normalize_spaces(list_name)
    if not is_valid_list_name(list_name):
        return
    items = storage.load_items(list_name)
    remaining = [item for item in items if item["id"] != item_id]
    storage.save_items(list_name, remaining)


def find_item_by_id(items, item_id):
    """Return the item with the given id, or None."""
    for item in items:
        if item["id"] == item_id:
            return item
    return None


def next_item_id(items):
    """Return the next free item id within a list."""
    used_ids = [item.get("id", 0) for item in items]
    return max(used_ids, default=0) + 1


def create_list(list_name):
    """Create a new empty list if the name is valid and not taken."""
    list_name = normalize_spaces(list_name)
    if not is_valid_list_name(list_name):
        return
    if list_name not in storage.get_list_names():
        storage.save_items(list_name, [])


def clear_items(list_name):
    """Remove all items from the named list, keeping the list itself."""
    list_name = normalize_spaces(list_name)
    if not is_valid_list_name(list_name):
        return
    storage.save_items(list_name, [])


def remove_list(list_name):
    """Delete a whole list."""
    list_name = normalize_spaces(list_name)
    if not is_valid_list_name(list_name):
        return
    storage.delete_list(list_name)


def clear_caches():
    """Clear all cached api data."""
    xivapi.clear_cache()


def icon_folder():
    """Return the folder where item icons are cached."""
    return xivapi.icon_folder()


def suggest_item_names(text):
    """Return item name suggestions for a partial item name."""
    text = normalize_spaces(text)
    if len(text) < 3:
        return []
    return xivapi.search_item_names(text)


BUILT_IN_ALARMS = ["classic-beep.wav", "chime.wav", "buzzer.wav"]


JOB_GROUPS = {
    "miner": ("Mining", "Quarrying"),
    "botanist": ("Logging", "Harvesting"),
    "fisher": ("Fishing", "Spearfishing"),
}

SORT_KEYS = {
    "name": lambda c: c["name"],
    "level": lambda c: (c["level"], c["stars"], c["name"]),
    "stars": lambda c: (c["stars"], c["level"], c["name"]),
    "job": lambda c: (c["job"] or "~", c["level"], c["name"]),
    "zone": lambda c: (c["zone"] or "~", c["name"]),
    "scrips": lambda c: (c["scrips"]["high"] if c["scrips"] else -1, c["name"]),
}

NATURAL_DIRECTIONS = {
    "name": "asc",
    "level": "desc",
    "stars": "desc",
    "job": "asc",
    "zone": "asc",
    "scrips": "desc",
}


def get_collectables(sort_by="level", direction=None, job="all", min_level=None, max_level=None):
    """Return gathering collectables filtered and sorted for display."""
    collectables = xivapi.fetch_collectables() or []
    kept = filter_collectables(collectables, job, min_level, max_level)
    return sort_collectables(kept, sort_by, direction)


def filter_collectables(collectables, job, min_level, max_level):
    """Keep only collectables matching the job and level filters."""
    kept = []
    for collectable in collectables:
        if job in JOB_GROUPS and collectable["job"] not in JOB_GROUPS[job]:
            continue
        if min_level is not None and collectable["level"] < min_level:
            continue
        if max_level is not None and collectable["level"] > max_level:
            continue
        kept.append(collectable)
    return kept


def sort_collectables(collectables, sort_by, direction):
    """Sort collectables by one column in the given or its natural direction."""
    if sort_by not in SORT_KEYS:
        sort_by = "level"
    direction = normalize_direction(sort_by, direction)
    return sorted(collectables, key=SORT_KEYS[sort_by], reverse=direction == "desc")


def normalize_direction(sort_by, direction):
    """Return asc or desc, falling back to the column's natural direction."""
    if direction in ("asc", "desc"):
        return direction
    return NATURAL_DIRECTIONS.get(sort_by, "desc")


CRAFT_SORT_KEYS = {
    "name": lambda c: c["name"],
    "level": lambda c: (c["level"], c["stars"], c["name"]),
    "stars": lambda c: (c["stars"], c["level"], c["name"]),
    "job": lambda c: (c["jobs"][0]["name"] if c["jobs"] else "~", c["level"], c["name"]),
    "scrips": lambda c: (c["scrips"]["high"] if c["scrips"] else -1, c["name"]),
}

JOB_NAMES_FILE = Path(__file__).parent / "job_names.json"
JOB_NAME_CACHE = {}


def load_job_names():
    """Return the craft type to job name mapping from the overwrite file."""
    if not JOB_NAME_CACHE and JOB_NAMES_FILE.exists():
        with open(JOB_NAMES_FILE, encoding="utf-8") as file:
            JOB_NAME_CACHE.update(json.load(file))
    return JOB_NAME_CACHE


def get_craftables(sort_by="level", direction=None, job="all", min_level=None, max_level=None, scrip_only=True):
    """Return craftable collectables filtered and sorted for display."""
    craftables = [with_job_names(c) for c in xivapi.fetch_craftables() or []]
    kept = filter_craftables(craftables, job, min_level, max_level, scrip_only)
    return sort_craftables(kept, sort_by, direction)


def with_job_names(craftable):
    """Replace raw craft type names with real job names and their icons."""
    mapping = load_job_names()
    jobs = []
    for craft_type in craftable["jobs"]:
        override = mapping.get(craft_type)
        if override:
            xivapi.download_craft_icon(override["icon_id"])
            jobs.append({"name": override["name"], "icon_id": override["icon_id"]})
        else:
            jobs.append({"name": craft_type, "icon_id": None})
    return dict(craftable, jobs=jobs)


def filter_craftables(craftables, job, min_level, max_level, scrip_only):
    """Keep only craftables matching the job, level and scrip filters."""
    kept = []
    for craftable in craftables:
        jobs = [entry["name"].lower() for entry in craftable["jobs"]]
        if job != "all" and job not in jobs:
            continue
        if min_level is not None and craftable["level"] < min_level:
            continue
        if max_level is not None and craftable["level"] > max_level:
            continue
        if scrip_only and not craftable["scrips"]:
            continue
        kept.append(craftable)
    return kept


def sort_craftables(craftables, sort_by, direction):
    """Sort craftables by one column in the given or its natural direction."""
    if sort_by not in CRAFT_SORT_KEYS:
        sort_by = "level"
    direction = normalize_direction(sort_by, direction)
    return sorted(craftables, key=CRAFT_SORT_KEYS[sort_by], reverse=direction == "desc")


def add_craft_with_materials(list_name, item_name, amount):
    """Add a craftable item itself and all its base materials to the named list."""
    add_item(list_name, item_name, amount)
    recipe = xivapi.fetch_recipe(normalize_spaces(item_name))
    if recipe:
        add_crafted_item(list_name, item_name, amount)


def alarm_sounds():
    """Return all alarm sound file names, built-in sounds first, custom ones after."""
    found = []
    for pattern in AUDIO_PATTERNS:
        found.extend(path.name for path in ALARMS_DIR.glob(pattern))
    built_in = [name for name in BUILT_IN_ALARMS if name in found]
    custom = sorted(name for name in found if name not in BUILT_IN_ALARMS)
    return built_in + custom


def last_lookup_failed():
    """Tell whether the most recent api lookup failed to reach xivapi."""
    return xivapi.last_call_failed()


def get_language():
    """Return the configured game data language."""
    return settings.get_language()


def set_language(language):
    """Change the game data language."""
    settings.set_language(language)


def supported_languages():
    """Return all supported game data languages."""
    return settings.LANGUAGES


def find_item(items, item_name):
    """Return the item with the given name, ignoring case, or None."""
    for item in items:
        if item["name"].lower() == item_name.lower():
            return item
    return None
