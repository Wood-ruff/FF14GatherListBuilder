import json
import math
import re
from pathlib import Path

import settings
import storage
import universalis
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
    merge_item(items, item_name, amount)
    storage.save_items(list_name, items)


def merge_item(items, item_name, amount):
    """Add an amount of an item to the loaded items, summing up existing entries."""
    existing = find_item(items, item_name)
    if existing:
        existing["amount"] += amount
    else:
        items.append(new_item(items, item_name, amount))


def new_item(items, item_name, amount):
    """Build a new list entry, preferring the item name the api returns."""
    game_item = xivapi.fetch_item(item_name)
    game_id = None
    gathering = None
    craftable = False
    job_icons = []
    marketable = None
    if game_item:
        item_name = game_item["fields"]["Name"]
        game_id = game_item["row_id"]
        gathering = xivapi.fetch_gathering(game_id)
        recipe = xivapi.fetch_recipe(item_name)
        craftable = recipe is not None
        job_icons = job_symbols(recipe, gathering)
        marketable = item_marketable(game_id)
    return {
        "id": next_item_id(items),
        "name": item_name,
        "amount": amount,
        "game_id": game_id,
        "gathering": gathering,
        "craftable": craftable,
        "job_icons": job_icons,
        "marketable": marketable,
        "done": False,
        "muted": False,
        "materials_added": False,
        "sticky": False,
        "note": "",
        "language": settings.get_language(),
    }


def item_marketable(game_id):
    """Tell whether an item can be traded on the market board, or None when unknown."""
    details = xivapi.fetch_item_details(game_id)
    if details is None:
        return None
    return details["marketable"]


def add_crafted_item(list_name, item_name, amount):
    """Add all base materials needed to craft an item to the named list."""
    list_name = normalize_spaces(list_name)
    item_name = normalize_spaces(item_name)
    if not is_valid_list_name(list_name):
        return
    warm_material_data(item_name)
    items = storage.load_items(list_name)
    merge_ingredients_of(items, item_name, amount, depth=0)
    storage.save_items(list_name, items)


def warm_material_data(item_name):
    """Batch fetch everything the item's whole material tree will need."""
    game_id = xivapi.fetch_item_id(item_name)
    if game_id:
        warm_material_trees({game_id: item_name})


def warm_material_trees(pairs):
    """Batch fetch the recipes and item data behind the given craftables."""
    materials = xivapi.warm_recipes(pairs) or {}
    ids = sorted(materials)
    xivapi.warm_items(ids)
    xivapi.warm_icons(ids)
    xivapi.warm_gathering(ids)
    xivapi.warm_item_details(ids)


def merge_ingredients_of(items, item_name, amount, depth):
    """Resolve recipes recursively, merging items without a recipe into the list."""
    recipe = xivapi.fetch_recipe(item_name)
    if not recipe or depth >= MAX_RECIPE_DEPTH:
        merge_item(items, item_name, amount)
        return
    crafts = math.ceil(amount / recipe["yields"])
    for ingredient in recipe["ingredients"]:
        merge_ingredients_of(items, ingredient["name"], ingredient["amount"] * crafts, depth + 1)


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
    if item.get("marketable") is None:
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
    pending = [item for item in items
               if item.get("craftable", False) and not item.get("materials_added", False)]
    warm_material_trees({item["game_id"]: item["name"] for item in pending if item.get("game_id")})
    for item in pending:
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
        "marketable": None,
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
    warm_list_data(items)
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
            item["marketable"] = item_marketable(item["game_id"])
    storage.save_items(list_name, items)


def warm_list_data(items):
    """Batch fetch all game data the list items are about to be refreshed with."""
    known = [item for item in items if item.get("game_id")]
    ids = [item["game_id"] for item in known]
    xivapi.warm_items(ids)
    xivapi.warm_icons(ids)
    xivapi.warm_gathering(ids)
    xivapi.warm_recipes({item["game_id"]: item["name"] for item in known})
    xivapi.warm_item_details(ids)


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
    outdated = [item["game_id"] for item in items
                if item.get("game_id") and item.get("language") != language]
    xivapi.warm_items(outdated)
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


def market_icon_file():
    """Make sure the market board symbol is cached and return its file name."""
    return xivapi.ensure_market_icon()


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
    "scrip": 0.5,
    "special": 0.5,
    "special_locked": 6,
    "gemstone": 8,
    "gemstone_unlocked": 0.5,
    "loot": 8,
}


def get_craft_costs(level, job, orange_scrips, gemstones_unlocked=False, hide_loot=False, hide_locked=False):
    """Return scrip craftables ranked by material cost per scrip, cheapest first."""
    sources = material_source_sets()
    candidates = [craftable for craftable in get_craftables(job=job, scrip_mode="scrip")
                  if craft_level_matches(craftable["level"], level, orange_scrips)]
    xivapi.warm_recipes(craftable_ingredients(candidates))
    entries = []
    for craftable in candidates:
        entry = craft_cost_entry(craftable, sources, gemstones_unlocked)
        if entry and not entry_blocked(entry, gemstones_unlocked, hide_loot, hide_locked):
            entries.append(entry)
    ensure_currency_icons(entries)
    return sorted(entries, key=lambda entry: entry["score"])


def craftable_ingredients(craftables):
    """Collect the distinct ingredient id and name pairs of the craftables."""
    pairs = {}
    for craftable in craftables:
        for ingredient in craftable.get("ingredients", []):
            pairs[ingredient["game_id"]] = ingredient["name"]
    return pairs


def entry_blocked(entry, gemstones_unlocked, hide_loot, hide_locked):
    """Check whether any of the entry's materials is unobtainable under the filters."""
    return any(
        material_blocked(material, gemstones_unlocked, hide_loot, hide_locked)
        for material in entry["materials"]
    )


def material_blocked(material, gemstones_unlocked, hide_loot, hide_locked):
    """Check whether every way to get a material is switched off by the filters."""
    if material["source"] == "loot":
        return hide_loot
    if material["source"] == "gemstone":
        return hide_loot and hide_locked and not gemstones_unlocked
    if material["locked"]:
        return hide_locked
    return False


def ensure_currency_icons(entries):
    """Make sure the icons of all cost currencies are cached."""
    currencies = set()
    for entry in entries:
        for material in entry["materials"]:
            if material["currency"]:
                currencies.add(material["currency"])
    xivapi.warm_items(sorted(currencies))
    for currency_id in currencies:
        xivapi.fetch_item_by_id(currency_id)


def material_source_sets():
    """Return the acquisition source lookups, or None while xivapi is unreachable."""
    sources = xivapi.fetch_material_sources()
    if sources is None:
        return None
    lookups = {}
    for key, values in sources.items():
        if isinstance(values, dict):
            lookups[key] = {int(item_id): value for item_id, value in values.items()}
        else:
            lookups[key] = set(values)
    return lookups


def craft_level_matches(craft_level, level, orange_scrips):
    """Check whether a recipe level fits the level cap and the scrip color."""
    if craft_level > level:
        return False
    if orange_scrips:
        return craft_level == 100
    return craft_level <= 99


def craft_cost_entry(craftable, sources, gemstones_unlocked):
    """Build one cost entry with material counts and score, or None when not worth it."""
    materials = craft_materials(craftable, sources)
    scrips = craftable["scrips"]["high"] * craftable.get("yields", 1)
    if not materials or scrips <= 0:
        return None
    paid = scrips_paid(materials)
    net_scrips = scrips - paid
    if net_scrips <= 0:
        return None
    cost = material_cost(materials, gemstones_unlocked)
    return {
        "game_id": craftable["game_id"],
        "name": craftable["name"],
        "jobs": craftable["jobs"],
        "level": craftable["level"],
        "stars": craftable["stars"],
        "scrips": scrips,
        "scrip_paid": paid,
        "net_scrips": net_scrips,
        "materials": materials,
        "unique_materials": sum(1 for m in materials if m["source"] != "crystal"),
        "total_materials": sum(m["amount"] for m in materials if m["source"] != "crystal"),
        "has_loot": any(is_looted(m, gemstones_unlocked) for m in materials),
        "has_locked": any(m["locked"] for m in materials),
        "cost": round(cost, 2),
        "score": round(cost / net_scrips, 3),
    }


def scrips_paid(materials):
    """Sum the scrips spent on materials that are only sold for scrips."""
    paid = 0
    for material in materials:
        scrip = material["scrip"]
        if scrip:
            paid += math.ceil(material["amount"] / scrip["bundle"]) * scrip["price"]
    return paid


def craft_materials(craftable, sources):
    """Resolve the craftable's ingredients to base materials, crystals sorted last."""
    totals = {}
    for ingredient in craftable.get("ingredients") or []:
        add_base_material(totals, ingredient, ingredient["amount"], sources, depth=0)
    return sorted(totals.values(), key=lambda material: material["source"] == "crystal")


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
    entry = totals.setdefault(ingredient["game_id"], new_material(ingredient, source, sources))
    entry["amount"] += amount


def new_material(ingredient, source, sources):
    """Build one base material entry with its source details."""
    game_id = ingredient["game_id"]
    scrip = sources["scrip"].get(game_id) if source == "scrip" else None
    return {
        "name": ingredient["name"],
        "game_id": game_id,
        "amount": 0,
        "source": source,
        "locked": source == "special" and game_id in sources["locked"],
        "timed": sources is not None and source == "gather" and game_id in sources["timed"],
        "scrip": scrip,
        "currency": material_currency(game_id, source, sources, scrip),
    }


def material_currency(game_id, source, sources, scrip):
    """Return the currency item id a bought material is paid with, or None."""
    if source == "gil":
        return xivapi.GIL_ITEM_ID
    if scrip:
        return scrip["currency"]
    if source in ("gemstone", "special"):
        return sources["currency"].get(game_id)
    return None


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
    if game_id in sources["scrip"]:
        return "scrip"
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


def get_item_sources(list_name, item_id):
    """Collect everything known about how one list item can be acquired."""
    list_name = normalize_spaces(list_name)
    if not is_valid_list_name(list_name):
        return None
    item = find_item_by_id(storage.load_items(list_name), item_id)
    if item is None or not item.get("game_id"):
        return None
    return item_source_info(item)


def item_source_info(item):
    """Build the acquisition overview of one item from the known source data."""
    game_id = item["game_id"]
    sources = material_source_sets() or {}
    scrip = sources.get("scrip", {}).get(game_id)
    info = {
        "name": item["name"],
        "game_id": game_id,
        "crystal": is_crystal(item),
        "craftable": bool(item.get("craftable")),
        "gatherable": game_id in sources.get("gatherable", ()),
        "timed": game_id in sources.get("timed", ()),
        "reduction": game_id in sources.get("reduction", ()),
        "reducible": game_id in sources.get("reducible", ()),
        "gil": game_id in sources.get("gil", ()),
        "scrip": scrip,
        "gemstone": game_id in sources.get("gemstone", ()),
        "special": game_id in sources.get("special", ()),
        "locked": game_id in sources.get("locked", ()),
        "offers": [],
    }
    info["loot"] = not any((
        info["crystal"], info["gatherable"], info["gil"], info["special"], info["craftable"],
        info["reduction"],
    ))
    currency = scrip["currency"] if scrip else sources.get("currency", {}).get(game_id)
    info["currency"] = currency
    info["currency_name"] = currency_display_name(currency)
    info["price"] = sources.get("prices", {}).get(game_id)
    if info["gil"] or info["special"]:
        info["offers"] = named_offers(game_id)
    return info


def named_offers(game_id):
    """Return the item's shop offers with their currency display names."""
    offers = xivapi.fetch_item_offers(game_id) or []
    return [dict(offer, currency_name=currency_display_name(offer["currency"])) for offer in offers]


def currency_display_name(currency_id):
    """Return the display name of a currency item, or None."""
    if not currency_id:
        return None
    currency = xivapi.fetch_item_by_id(currency_id)
    if currency:
        return currency["fields"]["Name"]
    return None


YIELD_RESULT_LIMIT = 20


def get_currency_options():
    """Return the spendable currencies for the yield calculator, sorted by name."""
    shop = xivapi.fetch_currency_shop() or {}
    ids = [int(currency_id) for currency_id in shop]
    names = xivapi.fetch_item_names(ids)
    options = [{"id": currency_id, "name": names[currency_id]}
               for currency_id in ids if names.get(currency_id)]
    return sorted(options, key=lambda option: option["name"])


def get_worlds():
    """Return all game worlds for the server dropdown, sorted by name."""
    worlds = universalis.fetch_worlds() or []
    return sorted(worlds, key=lambda world: world["name"])


def get_currency_yields(currency_id, world_id):
    """Rank what one currency buys by gil yield per unit on one world's market."""
    shop = xivapi.fetch_currency_shop() or {}
    offers = shop.get(str(currency_id), {})
    marketable = universalis.fetch_marketable_ids()
    if marketable is None:
        return None
    sellable = {int(item_id): offer for item_id, offer in offers.items()
                if int(item_id) in marketable}
    stats = universalis.fetch_market_stats(world_id, sorted(sellable))
    if stats is None:
        return None
    entries = build_yield_entries(sellable, stats)
    entries.sort(key=lambda entry: entry["yield"], reverse=True)
    entries = entries[:YIELD_RESULT_LIMIT]
    names = xivapi.fetch_item_names([entry["game_id"] for entry in entries])
    for entry in entries:
        entry["name"] = names.get(entry["game_id"], "")
    return entries


VENTURE_JOBS = ("battle", "miner", "botanist", "fisher")


def get_venture_yields(world_id, job, level, stat):
    """Rank retainer ventures by gil per venture on one world's market."""
    ventures = xivapi.fetch_ventures()
    if ventures is None:
        return None
    marketable = universalis.fetch_marketable_ids()
    if marketable is None:
        return None
    candidates = [venture for venture in ventures
                  if venture["job"] == job and venture["item"] in marketable
                  and (level is None or venture["level"] <= level)]
    stats = universalis.fetch_market_stats(world_id, sorted({v["item"] for v in candidates}))
    if stats is None:
        return None
    entries = build_venture_entries(candidates, stats, stat)
    entries.sort(key=lambda entry: entry["yield"], reverse=True)
    entries = entries[:YIELD_RESULT_LIMIT]
    names = xivapi.fetch_item_names([entry["game_id"] for entry in entries])
    for entry in entries:
        entry["name"] = names.get(entry["game_id"], "")
    return entries


def build_venture_entries(ventures, stats, stat):
    """Build one yield row per venture whose reward currently sells on the market."""
    entries = []
    for venture in ventures:
        market = stats.get(venture["item"])
        if market is None or market["price"] <= 0:
            continue
        quantity = venture_quantity(venture, stat)
        entries.append({
            "game_id": venture["item"],
            "level": venture["level"],
            "quantity": quantity,
            "price": market["price"],
            "avg_price": market["avg_price"],
            "min_sale": market["min_sale"],
            "max_sale": market["max_sale"],
            "yield": round(market["price"] * quantity / venture["cost"], 1),
            "week_volume": market["week_volume"],
        })
    return entries


def venture_quantity(venture, stat):
    """Return the reward amount of one venture at the retainer's stat tier."""
    quantities = venture["quantities"]
    if stat is None:
        return quantities[-1]
    tier = sum(1 for threshold in venture["breakpoints"] if threshold <= stat)
    return quantities[min(tier, len(quantities) - 1)]


GATHERING_JOBS = ("miner", "botanist", "all")

GATHERING_ITEMS_PER_RUN = 21
UNTIMED_RUNS_PER_HOUR = 30
EORZEA_DAY_REAL_MINUTES = 70
GATHERING_RESULT_LIMIT = 50
VOLUME_WARNING_SHARE = 0.7
QUICK_GATHER_MINUTES = 10
HIGH_VOLUME_WEEK_SALES = 2500


def get_gathering_yields(world_id, job, min_level, max_level,
                         hide_slow=False, quick=False, high_volume=False):
    """Rank node items by gil per hour of own gathering on one world's market."""
    gatherables = xivapi.fetch_gatherables()
    if gatherables is None:
        return None
    marketable = universalis.fetch_marketable_ids()
    if marketable is None:
        return None
    candidates = [gatherable for gatherable in gatherables
                  if gatherable["item"] in marketable
                  and gatherable_matches(gatherable, job, min_level, max_level)
                  and hourly_gathering_items(gatherable) > 0]
    overview = universalis.fetch_market_overview(world_id, sorted({g["item"] for g in candidates}))
    if overview is None:
        return None
    if high_volume:
        candidates = [g for g in candidates
                      if overview.get(g["item"], {}).get("velocity", 0) * 7 >= HIGH_VOLUME_WEEK_SALES]
    top = best_rough_yields(candidates, overview)
    stats = universalis.fetch_market_stats(world_id, sorted({g["item"] for g in top}))
    if stats is None:
        return None
    entries = build_gathering_entries(top, stats)
    if high_volume:
        entries = [entry for entry in entries
                   if entry["week_volume"] >= HIGH_VOLUME_WEEK_SALES]
    if hide_slow:
        entries = [entry for entry in entries
                   if entry["hourly_items"] <= realistic_sales(entry["week_volume"])]
    if quick:
        entries = [entry for entry in entries if is_quick_gather(entry)]
        entries.sort(key=lambda entry: entry["price"], reverse=True)
    else:
        entries.sort(key=lambda entry: entry["yield"], reverse=True)
    entries = entries[:GATHERING_RESULT_LIMIT]
    names = xivapi.fetch_item_names([entry["game_id"] for entry in entries])
    for entry in entries:
        entry["name"] = names.get(entry["game_id"], "")
    return entries


def realistic_sales(volume):
    """Sales one seller can realistically capture out of a trade volume; mirrors the JS helper."""
    return max(0.0, VOLUME_WARNING_SHARE * volume - math.sqrt(volume))


def quick_haul_items(entry):
    """Items one quick trip yields: a few runs on open nodes, one visit on a timed one."""
    if entry["timed"]:
        return GATHERING_ITEMS_PER_RUN
    run_minutes = 60 / UNTIMED_RUNS_PER_HOUR
    return GATHERING_ITEMS_PER_RUN * QUICK_GATHER_MINUTES / run_minutes


def is_quick_gather(entry):
    """Check whether one quick trip's haul sells within about a day."""
    return quick_haul_items(entry) <= realistic_sales(entry["week_volume"] / 7)


def gatherable_matches(gatherable, job, min_level, max_level):
    """Check one gatherable against the job and level window filters."""
    if job != "all" and job not in gatherable["jobs"]:
        return False
    if min_level is not None and gatherable["level"] < min_level:
        return False
    if max_level is not None and gatherable["level"] > max_level:
        return False
    return True


def hourly_gathering_items(gatherable):
    """Return how many of the item one real hour of gathering yields."""
    if not gatherable["timed"]:
        return GATHERING_ITEMS_PER_RUN * UNTIMED_RUNS_PER_HOUR
    runs_per_hour = len(gatherable["windows"]) * 60 / EORZEA_DAY_REAL_MINUTES
    return GATHERING_ITEMS_PER_RUN * runs_per_hour


def best_rough_yields(candidates, overview):
    """Keep the candidates whose price and sale speed promise the best gil per hour."""
    def rough_yield(gatherable):
        market = overview.get(gatherable["item"], {})
        sellable = realistic_sales(market.get("velocity", 0) * 7)
        return market.get("price", 0) * min(hourly_gathering_items(gatherable), sellable)

    ranked = sorted(candidates, key=rough_yield, reverse=True)
    return ranked[:2 * GATHERING_RESULT_LIMIT]


def build_gathering_entries(gatherables, stats):
    """Build one yield row per gatherable that currently sells on the market."""
    entries = []
    for gatherable in gatherables:
        market = stats.get(gatherable["item"])
        if market is None or market["price"] <= 0 or market["week_volume"] <= 0:
            continue
        hourly = hourly_gathering_items(gatherable)
        entries.append({
            "game_id": gatherable["item"],
            "level": gatherable["level"],
            "stars": gatherable["stars"],
            "jobs": gatherable["jobs"],
            "timed": gatherable["timed"],
            "windows": gatherable["windows"],
            "hidden": gatherable["hidden"],
            "hourly_items": round(hourly, 1),
            "price": market["price"],
            "avg_price": market["avg_price"],
            "yield": round(market["price"] * hourly),
            "week_volume": market["week_volume"],
        })
    return entries


def build_yield_entries(offers, stats):
    """Build one yield row per offer that currently sells on the market."""
    entries = []
    for item_id, offer in offers.items():
        market = stats.get(item_id)
        if market is None or market["price"] <= 0:
            continue
        entries.append({
            "game_id": item_id,
            "cost": offer["cost"],
            "amount": offer["amount"],
            "price": market["price"],
            "avg_price": market["avg_price"],
            "min_sale": market["min_sale"],
            "max_sale": market["max_sale"],
            "yield": round(market["price"] * offer["amount"] / offer["cost"], 1),
            "week_volume": market["week_volume"],
            "locked": offer["locked"],
        })
    return entries


def alarm_sounds():
    """Return all alarm sound file names, built-in sounds first, custom ones after."""
    found = []
    for pattern in AUDIO_PATTERNS:
        found.extend(path.name for path in ALARMS_DIR.glob(pattern))
    built_in = [name for name in BUILT_IN_ALARMS if name in found]
    custom = sorted(name for name in found if name not in BUILT_IN_ALARMS)
    return built_in + custom


def fetches_running():
    """Tell whether any big data lookup is currently fetching."""
    return xivapi.fetches_running()


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
