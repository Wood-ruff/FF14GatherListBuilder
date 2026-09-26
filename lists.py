import re

import storage
import xivapi

VALID_LIST_NAME = re.compile(r"^[A-Za-z0-9 _-]{1,50}$")


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
        items.append({
            "id": next_item_id(items),
            "name": item_name,
            "amount": amount,
            "game_id": xivapi.fetch_item_id(item_name),
        })
    storage.save_items(list_name, items)


def update_item(list_name, item_id, item_name, amount):
    """Change name and amount of an item, refreshing its game id when renamed."""
    list_name = normalize_spaces(list_name)
    item_name = normalize_spaces(item_name)
    if not is_valid_list_name(list_name):
        return
    items = storage.load_items(list_name)
    item = find_item_by_id(items, item_id)
    if not item:
        return
    if item["name"].lower() != item_name.lower():
        item["game_id"] = xivapi.fetch_item_id(item_name)
    item["name"] = item_name
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


def find_item(items, item_name):
    """Return the item with the given name, ignoring case, or None."""
    for item in items:
        if item["name"].lower() == item_name.lower():
            return item
    return None
