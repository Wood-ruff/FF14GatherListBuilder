import json
from pathlib import Path

import jsonfile

SETTINGS_FILE = Path(__file__).parent / "data" / "settings.json"
LANGUAGES = ["en", "de", "fr", "ja"]
DEFAULT_LANGUAGE = "en"


def get_language():
    """Return the configured game data language."""
    return load_settings().get("language", DEFAULT_LANGUAGE)


def set_language(language):
    """Save the game data language if it is a supported one."""
    if language not in LANGUAGES:
        return
    all_settings = load_settings()
    all_settings["language"] = language
    save_settings(all_settings)


def load_settings():
    """Return the settings file contents, or an empty dict when missing or unreadable."""
    if not SETTINGS_FILE.exists():
        return {}
    with open(SETTINGS_FILE, encoding="utf-8") as file:
        try:
            return json.load(file)
        except ValueError:
            return {}


def save_settings(all_settings):
    """Write all settings to the settings file, replacing it atomically."""
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    jsonfile.write_json_file(SETTINGS_FILE, all_settings, indent=2)
