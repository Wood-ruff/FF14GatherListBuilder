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


def get_items(list_name, timed_first=False):
    """Return the items of the named list, craftable items first, timed first on demand."""
    list_name = normalize_spaces(list_name)
    if not is_valid_list_name(list_name):
        return []
    items = sorted(storage.load_items(list_name), key=item_sort_group)
    if timed_first:
        items = sorted(items, key=lambda item: not is_timed(item))
    for item in items:
        item["group"] = (0 if is_timed(item) else 1) if timed_first else item_sort_group(item)
        item["crystal"] = is_crystal(item)
    return items


def is_timed(item):
    """Check whether an item has a timed gathering node."""
    gathering = item.get("gathering")
    return bool(gathering and gathering.get("timed")) and not is_crystal(item)


CRYSTAL_GAME_IDS = xivapi.CRYSTAL_GAME_IDS


def is_crystal(item):
    """Check whether an item is an elemental shard, crystal or cluster."""
    return item.get("game_id") in CRYSTAL_GAME_IDS


def item_sort_group(item):
    """Group items for display: craftables first, then normal items, crystals last."""
    if is_crystal(item):
        return 2
    if item.get("craftable", False):
        return 0
    return 1


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
    craftable = False
    job_icons = []
    if game_item:
        item_name = game_item["fields"]["Name"]
        game_id = game_item["row_id"]
        gathering = xivapi.fetch_gathering(game_id)
        recipe = xivapi.fetch_recipe(item_name)
        craftable = recipe is not None
        job_icons = job_symbols(recipe, gathering)
    return {
        "id": next_item_id(items),
        "name": item_name,
        "amount": amount,
        "game_id": game_id,
        "gathering": gathering,
        "craftable": craftable,
        "job_icons": job_icons,
        "done": False,
        "muted": False,
        "materials_added": False,
        "sticky": False,
        "note": "",
        "language": settings.get_language(),
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


def add_materials_for(list_name, item_id):
    """Add the base materials for one list item, scaled by its current amount."""
    list_name = normalize_spaces(list_name)
    if not is_valid_list_name(list_name):
        return
    items = storage.load_items(list_name)
    item = find_item_by_id(items, item_id)
    if not item:
        return
    if xivapi.fetch_recipe(item["name"]):
        add_crafted_item(list_name, item["name"], item["amount"])
        set_item_flag(list_name, item_id, "materials_added", True)


def set_done(list_name, item_id, done):
    """Mark one item in the named list as done or not done."""
    set_item_flag(list_name, item_id, "done", done)


def set_muted(list_name, item_id, muted):
    """Suppress or restore the alarm of one item in the named list."""
    set_item_flag(list_name, item_id, "muted", muted)


def set_materials_added(list_name, item_id, added):
    """Mark whether the materials of one item were added to the list."""
    set_item_flag(list_name, item_id, "materials_added", added)


def set_sticky(list_name, item_id, sticky):
    """Pin or unpin one item of the named list."""
    set_item_flag(list_name, item_id, "sticky", sticky)


def set_note(list_name, item_id, note):
    """Save a short note on one item of the named list."""
    set_item_flag(list_name, item_id, "note", note[:200])


def set_item_flag(list_name, item_id, flag, value):
    """Set one boolean flag on one item in the named list."""
    list_name = normalize_spaces(list_name)
    if not is_valid_list_name(list_name):
        return
    items = storage.load_items(list_name)
    item = find_item_by_id(items, item_id)
    if not item:
        return
    item[flag] = value
    storage.save_items(list_name, items)


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


ITEM_MODEL_FILE = Path(__file__).parent / "models" / "item.json"


def load_item_model():
    """Return the item data model with its default values."""
    with open(ITEM_MODEL_FILE, encoding="utf-8") as file:
        return json.load(file)


def migrate_lists():
    """Add missing model fields to all stored lists and name the lists needing fresh data."""
    model = load_item_model()
    outdated = []
    for list_name in storage.get_list_names():
        changed = migrate_list(list_name, model)
        if changed or list_needs_data(list_name):
            outdated.append(list_name)
    return outdated


def list_needs_data(list_name):
    """Check whether any item of a list is missing derived game data."""
    return any(item_needs_data(item) for item in storage.load_items(list_name))


def item_needs_data(item):
    """Check whether an item has a game id but incomplete game data."""
    if item.get("game_id") is None:
        return False
    if not item.get("job_icons"):
        return True
    gathering = item.get("gathering")
    if gathering is not None and "x" not in gathering:
        return True
    return is_crystal(item) and len(item["job_icons"]) < 2


def migrate_list(list_name, model):
    """Fill missing model fields of one list with defaults, telling whether it changed."""
    items = storage.load_items(list_name)
    changed = False
    for item in items:
        for field, default in model.items():
            if field not in item:
                item[field] = default
                changed = True
    if changed:
        storage.save_items(list_name, items)
    return changed


def create_list(list_name):
    """Create a new empty list if the name is valid and not taken."""
    list_name = normalize_spaces(list_name)
    if not is_valid_list_name(list_name):
        return
    if list_name not in storage.get_list_names():
        storage.save_items(list_name, [])


def filter_items(items, name_filter):
    """Keep only items whose name contains the search term."""
    return [item for item in items if matches_name(item, name_filter)]


def add_all_materials(list_name):
    """Add the base materials of every craftable item that does not have them yet."""
    list_name = normalize_spaces(list_name)
    if not is_valid_list_name(list_name):
        return
    items = storage.load_items(list_name)
    for item in items:
        if item.get("craftable", False) and not item.get("materials_added", False):
            add_materials_for(list_name, item["id"])


def remove_materials(list_name):
    """Remove all materials and crystals from the named list, keeping craftable items."""
    list_name = normalize_spaces(list_name)
    if not is_valid_list_name(list_name):
        return
    items = storage.load_items(list_name)
    craftables = [item for item in items if item.get("craftable", False)]
    for item in craftables:
        item["materials_added"] = False
    storage.save_items(list_name, craftables)


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


MAX_IMPORT_ITEMS = 500
MAX_IMPORT_AMOUNT = 999999


def lists_folder():
    """Return the folder where the list files live."""
    return storage.DATA_DIR


def import_list(list_name, items):
    """Create an imported list under a free name and return that name, or None."""
    list_name = normalize_spaces(list_name)
    if not is_valid_list_name(list_name) or not isinstance(items, list):
        return None
    cleaned = []
    for item in items[:MAX_IMPORT_ITEMS]:
        if valid_import_item(item):
            cleaned.append(imported_item(len(cleaned) + 1, item))
    name = free_list_name(list_name)
    storage.save_items(name, cleaned)
    return name


def free_list_name(list_name):
    """Return the list name itself or a numbered variant if it is taken."""
    names = storage.get_list_names()
    if list_name not in names:
        return list_name
    counter = 2
    while f"{list_name} {counter}" in names:
        counter += 1
    return f"{list_name} {counter}"


def valid_import_item(item):
    """Check whether an imported entry has a usable name and amount."""
    if not isinstance(item, dict):
        return False
    name = item.get("name")
    amount = item.get("amount")
    return isinstance(name, str) and bool(name.strip()) and isinstance(amount, int) and amount > 0


def imported_item(item_id, item):
    """Keep only the known fields of an imported item, with safe defaults."""
    game_id = item.get("game_id")
    return {
        "id": item_id,
        "name": normalize_spaces(item["name"])[:100],
        "amount": min(item["amount"], MAX_IMPORT_AMOUNT),
        "game_id": game_id if isinstance(game_id, int) else None,
        "gathering": None,
        "craftable": bool(item.get("craftable", False)),
        "done": bool(item.get("done", False)),
        "muted": bool(item.get("muted", False)),
        "materials_added": bool(item.get("materials_added", False)),
        "sticky": bool(item.get("sticky", False)),
        "note": imported_note(item),
        "job_icons": [],
        "language": None,
    }


def imported_note(item):
    """Return the imported item's note when it is a plain short text."""
    note = item.get("note")
    if isinstance(note, str):
        return note[:200]
    return ""


def refresh_list_data(list_name):
    """Re-fetch the game data of every item in a list, keeping the user's settings."""
    list_name = normalize_spaces(list_name)
    if not is_valid_list_name(list_name):
        return
    items = storage.load_items(list_name)
    for item in items:
        game_item = None
        if item.get("game_id"):
            game_item = xivapi.fetch_item_by_id(item["game_id"])
        if not game_item:
            game_item = xivapi.fetch_item(item["name"])
        if game_item:
            apply_game_item(item, game_item)
            item["gathering"] = xivapi.fetch_gathering(item["game_id"])
            recipe = xivapi.fetch_recipe(item["name"])
            item["craftable"] = recipe is not None
            item["job_icons"] = job_symbols(recipe, item["gathering"])
    storage.save_items(list_name, items)


def apply_game_item(item, game_item):
    """Write freshly fetched game data onto a list item."""
    item["name"] = game_item["fields"]["Name"]
    item["game_id"] = game_item["row_id"]
    item["language"] = settings.get_language()


def needs_localization(items):
    """Check whether any item was resolved in another language."""
    language = settings.get_language()
    return any(item.get("game_id") and item.get("language") != language for item in items)


def localize_list(list_name):
    """Re-fetch items of a list by id so their names match the current language."""
    list_name = normalize_spaces(list_name)
    if not is_valid_list_name(list_name):
        return
    language = settings.get_language()
    items = storage.load_items(list_name)
    changed = False
    for item in items:
        if item.get("game_id") and item.get("language") != language:
            game_item = xivapi.fetch_item_by_id(item["game_id"])
            if game_item:
                apply_game_item(item, game_item)
                changed = True
    if changed:
        storage.save_items(list_name, items)


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


BACKGROUNDS_DIR = Path(__file__).parent / "static" / "backgrounds"
IMAGE_PATTERNS = ("*.jpg", "*.jpeg", "*.png", "*.webp", "*.gif")


def background_images():
    """Return the file names of all available background images."""
    names = []
    for pattern in IMAGE_PATTERNS:
        names.extend(path.name for path in BACKGROUNDS_DIR.glob(pattern))
    return sorted(names)


BUILT_IN_ALARMS = [
    "classic-beep.wav", "chime.wav", "buzzer.wav",
    "bells.wav", "alert.wav", "sonar.wav", "tick-tock.wav", "fanfare.wav", "shop-bell.wav",
]


PAGE_SIZES = [25, 50, 100, 250]
DEFAULT_PAGE_SIZE = 50


def paginate(entries, page, size):
    """Return one page of entries plus the corrected page number and page count."""
    if size not in PAGE_SIZES:
        size = DEFAULT_PAGE_SIZE
    page_count = max(1, -(-len(entries) // size))
    page = min(max(page, 1), page_count)
    start = (page - 1) * size
    return entries[start:start + size], page, page_count


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


def get_collectables(sort_by="level", direction=None, job="all", min_level=None, max_level=None, min_scrips=None, scrip_mode="all", name_filter=""):
    """Return gathering collectables filtered and sorted for display."""
    collectables = xivapi.fetch_collectables() or []
    kept = filter_collectables(collectables, job, min_level, max_level, min_scrips, scrip_mode, name_filter)
    return sort_collectables(kept, sort_by, direction)


def matches_name(entry, name_filter):
    """Check whether the entry's name contains the search term, ignoring case."""
    return name_filter.lower() in entry["name"].lower()


def filter_collectables(collectables, job, min_level, max_level, min_scrips, scrip_mode, name_filter=""):
    """Keep only collectables matching the name, job, level and scrip filters."""
    kept = []
    for collectable in collectables:
        if not matches_name(collectable, name_filter):
            continue
        if job in JOB_GROUPS and collectable["job"] not in JOB_GROUPS[job]:
            continue
        if min_level is not None and collectable["level"] < min_level:
            continue
        if max_level is not None and collectable["level"] > max_level:
            continue
        if not has_enough_scrips(collectable, min_scrips):
            continue
        if not matches_scrip_mode(collectable, scrip_mode):
            continue
        kept.append(collectable)
    return kept


def matches_scrip_mode(collectable, scrip_mode):
    """Check whether the item fits the scrip display mode."""
    if scrip_mode == "scrip":
        return collectable["scrips"] is not None
    if scrip_mode == "noscrip":
        return collectable["scrips"] is None
    return True


def has_enough_scrips(collectable, min_scrips):
    """Check whether the item's lowest scrip reward reaches the filter value."""
    if min_scrips is None:
        return True
    scrips = collectable["scrips"]
    return scrips is not None and scrips["low"] >= min_scrips


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


def get_craftables(sort_by="level", direction=None, job="all", min_level=None, max_level=None, scrip_mode="scrip", min_scrips=None, name_filter=""):
    """Return craftable collectables filtered and sorted for display."""
    craftables = [with_job_names(c) for c in xivapi.fetch_craftables() or []]
    kept = filter_craftables(craftables, job, min_level, max_level, scrip_mode, min_scrips, name_filter)
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


def filter_craftables(craftables, job, min_level, max_level, scrip_mode, min_scrips, name_filter=""):
    """Keep only craftables matching the name, job, level and scrip filters."""
    kept = []
    for craftable in craftables:
        if not matches_name(craftable, name_filter):
            continue
        jobs = [entry["name"].lower() for entry in craftable["jobs"]]
        if job != "all" and job not in jobs:
            continue
        if min_level is not None and craftable["level"] < min_level:
            continue
        if max_level is not None and craftable["level"] > max_level:
            continue
        if not matches_scrip_mode(craftable, scrip_mode):
            continue
        if not has_enough_scrips(craftable, min_scrips):
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
        mark_materials_added(list_name, item_name)


def mark_materials_added(list_name, item_name):
    """Remember that the materials of one item were added to the list."""
    list_name = normalize_spaces(list_name)
    if not is_valid_list_name(list_name):
        return
    items = storage.load_items(list_name)
    item = find_item(items, normalize_spaces(item_name))
    if item:
        item["materials_added"] = True
        storage.save_items(list_name, items)


def get_rotation(level, jobs, orange_scrips):
    """Return timed scrip collectables gatherable at the level by the chosen professions."""
    rotation = []
    for collectable in xivapi.fetch_collectables() or []:
        if not collectable["timed"] or not collectable["scrips"]:
            continue
        if collectable["level"] > level:
            continue
        if orange_scrips and collectable["level"] != 100:
            continue
        if not orange_scrips and collectable["level"] > 99:
            continue
        if not rotation_job_matches(collectable["job"], jobs):
            continue
        rotation.append(collectable)
    return rotation


def rotation_job_matches(job, jobs):
    """Check whether the gathering method belongs to one of the chosen professions."""
    for chosen in jobs:
        if job in JOB_GROUPS.get(chosen, ()):
            return True
    return False


UNIQUE_MATERIAL_WEIGHT = 10

MATERIAL_COST_WEIGHTS = {
    "crystal": 0.25,
    "gather": 1,
    "gather_timed": 2,
    "gil": 0.5,
    "special": 0.5,
    "special_locked": 6,
    "gemstone": 8,
    "gemstone_unlocked": 0.5,
    "loot": 8,
}


def get_craft_costs(level, job, orange_scrips, gemstones_unlocked=False):
    """Return scrip craftables ranked by material cost per scrip, cheapest first."""
    sources = material_source_sets()
    entries = []
    for craftable in get_craftables(job=job, scrip_mode="scrip"):
        if not craft_level_matches(craftable["level"], level, orange_scrips):
            continue
        entry = craft_cost_entry(craftable, sources, gemstones_unlocked)
        if entry:
            entries.append(entry)
    return sorted(entries, key=lambda entry: entry["score"])


def material_source_sets():
    """Return the acquisition source item id sets, or None while xivapi is unreachable."""
    sources = xivapi.fetch_material_sources()
    if sources is None:
        return None
    return {key: set(ids) for key, ids in sources.items()}


def craft_level_matches(craft_level, level, orange_scrips):
    """Check whether a recipe level fits the level cap and the scrip color."""
    if craft_level > level:
        return False
    if orange_scrips:
        return craft_level == 100
    return craft_level <= 99


def craft_cost_entry(craftable, sources, gemstones_unlocked):
    """Build one cost entry with material counts and score, or None without recipe data."""
    materials = craft_materials(craftable, sources)
    scrips = craftable["scrips"]["high"] * craftable.get("yields", 1)
    if not materials or scrips <= 0:
        return None
    cost = material_cost(materials, gemstones_unlocked)
    return {
        "game_id": craftable["game_id"],
        "name": craftable["name"],
        "jobs": craftable["jobs"],
        "level": craftable["level"],
        "stars": craftable["stars"],
        "scrips": scrips,
        "materials": materials,
        "unique_materials": sum(1 for m in materials if m["source"] != "crystal"),
        "total_materials": sum(m["amount"] for m in materials if m["source"] != "crystal"),
        "has_loot": any(is_looted(m, gemstones_unlocked) for m in materials),
        "has_locked": any(m["locked"] for m in materials),
        "cost": round(cost, 2),
        "score": round(cost / scrips, 3),
    }


def craft_materials(craftable, sources):
    """Resolve the craftable's ingredients to base materials marked with their sources."""
    totals = {}
    for ingredient in craftable.get("ingredients") or []:
        add_base_material(totals, ingredient, ingredient["amount"], sources, depth=0)
    return list(totals.values())


def add_base_material(totals, ingredient, amount, sources, depth):
    """Accumulate one ingredient, expanding crafted intermediates recursively."""
    source = material_source(ingredient["game_id"], sources)
    if source == "loot" and depth < MAX_RECIPE_DEPTH:
        recipe = xivapi.fetch_recipe(ingredient["name"])
        if recipe:
            crafts = math.ceil(amount / recipe["yields"])
            for sub_ingredient in recipe["ingredients"]:
                add_base_material(totals, sub_ingredient, sub_ingredient["amount"] * crafts, sources, depth + 1)
            return
    entry = totals.setdefault(ingredient["game_id"], {
        "name": ingredient["name"],
        "game_id": ingredient["game_id"],
        "amount": 0,
        "source": source,
        "locked": source == "special" and ingredient["game_id"] in sources["locked"],
        "timed": sources is not None and source == "gather" and ingredient["game_id"] in sources["timed"],
    })
    entry["amount"] += amount


def material_source(game_id, sources):
    """Classify how one material is acquired, treating unknown items as loot."""
    if game_id in CRYSTAL_GAME_IDS:
        return "crystal"
    if sources is None or game_id in sources["gatherable"]:
        return "gather"
    if game_id in sources["gil"]:
        return "gil"
    if game_id in sources["gemstone"]:
        return "gemstone"
    if game_id in sources["special"]:
        return "special"
    return "loot"


def material_cost(materials, gemstones_unlocked):
    """Weigh material amounts, unique material types and their sources into one cost."""
    cost = 0
    for material in materials:
        weight_key = material_weight_key(material, gemstones_unlocked)
        cost += material["amount"] * MATERIAL_COST_WEIGHTS[weight_key]
        if material["source"] != "crystal":
            cost += UNIQUE_MATERIAL_WEIGHT
    return cost


def material_weight_key(material, gemstones_unlocked):
    """Pick the cost weight of one material from its source and its restrictions."""
    if material["locked"]:
        return "special_locked"
    if material["timed"]:
        return "gather_timed"
    if material["source"] == "gemstone" and gemstones_unlocked:
        return "gemstone_unlocked"
    return material["source"]


def is_looted(material, gemstones_unlocked):
    """Check whether a material has to be taken from enemies."""
    if material["source"] == "loot":
        return True
    return material["source"] == "gemstone" and not gemstones_unlocked


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


def job_symbols(recipe, gathering):
    """Return the crafting and gathering job icons of an item."""
    symbols = []
    if recipe:
        for craft_type in recipe.get("craft_types", []):
            override = load_job_names().get(craft_type)
            if override:
                xivapi.download_craft_icon(override["icon_id"])
                symbols.append({"type": "craft", "icon": override["icon_id"]})
    if gathering:
        for job_id in gathering.get("job_ids") or []:
            xivapi.ensure_job_type_icon(job_id)
            symbols.append({"type": "gather", "icon": job_id})
    return symbols


def find_item(items, item_name):
    """Return the item with the given name, ignoring case, or None."""
    for item in items:
        if item["name"].lower() == item_name.lower():
            return item
    return None
