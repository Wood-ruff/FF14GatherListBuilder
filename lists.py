import math
import re

import settings
import storage
import xivapi

VALID_LIST_NAME = re.compile(r"^[A-Za-z0-9 _-]{1,50}$")
MAX_RECIPE_DEPTH = 10


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
    if game_item:
        item_name = game_item["fields"]["Name"]
        game_id = game_item["row_id"]
    return {
        "id": next_item_id(items),
        "name": item_name,
        "amount": amount,
        "game_id": game_id,
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
