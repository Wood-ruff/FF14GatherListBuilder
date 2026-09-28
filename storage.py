import json
import logging
from pathlib import Path

import jsonfile

DATA_DIR = Path(__file__).parent / "data" / "lists"

LOG = logging.getLogger(__name__)


def get_list_names():
    """Return the names of all saved lists, sorted alphabetically."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return sorted(path.stem for path in DATA_DIR.glob("*.json"))


def load_items(list_name):
    """Return the items of the named list, or an empty list when missing or unreadable."""
    path = DATA_DIR / f"{list_name}.json"
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as file:
        try:
            return json.load(file)
        except ValueError:
            LOG.warning("list file %s is unreadable, treating the list as empty", path.name)
            return []


def delete_list(list_name):
    """Delete the JSON file of the named list."""
    path = DATA_DIR / f"{list_name}.json"
    if path.exists():
        path.unlink()


def save_items(list_name, items):
    """Write the items of the named list to its JSON file, replacing it atomically."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    jsonfile.write_json_file(DATA_DIR / f"{list_name}.json", items, indent=2)
