import json
from pathlib import Path

TRANSLATIONS_DIR = Path(__file__).parent / "translations"
FALLBACK_LANGUAGE = "en"
LOADED = {}


def all_texts(language):
    """Return the english texts overlaid with the given language."""
    merged = dict(load_language(FALLBACK_LANGUAGE))
    merged.update(load_language(language))
    return merged


def load_language(language):
    """Return all texts of one language file, remembering them per run."""
    if language not in LOADED:
        path = TRANSLATIONS_DIR / f"{language}.json"
        if path.exists():
            with open(path, encoding="utf-8") as file:
                LOADED[language] = json.load(file)
        else:
            LOADED[language] = {}
    return LOADED[language]
