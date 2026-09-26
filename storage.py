import json
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data" / "lists"


def get_list_names():
    """Return the names of all saved lists, sorted alphabetically."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return sorted(path.stem for path in DATA_DIR.glob("*.json"))


def load_items(list_name):
    """Return the items of the named list, or an empty list if it does not exist yet."""
    path = DATA_DIR / f"{list_name}.json"
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as file:
        return json.load(file)


def delete_list(list_name):
    """Delete the JSON file of the named list."""
    path = DATA_DIR / f"{list_name}.json"
    if path.exists():
        path.unlink()


def save_items(list_name, items):
    """Write the items of the named list to its JSON file."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / f"{list_name}.json"
    with open(path, "w", encoding="utf-8") as file:
        json.dump(items, file, indent=2)
