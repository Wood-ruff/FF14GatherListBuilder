import json
from pathlib import Path

TRANSLATIONS_DIR = Path(__file__).parent / "translations"
FALLBACK_LANGUAGE = "en"


def all_texts(language):
    """Return the english texts overlaid with the given language."""
    merged = dict(load_language(FALLBACK_LANGUAGE))
    merged.update(load_language(language))
    return merged


def write_template():
    """Regenerate the template file so it always matches the english texts."""
    english = load_language(FALLBACK_LANGUAGE)
    template = {code: {"english": text, "translation": ""} for code, text in english.items()}
    path = TRANSLATIONS_DIR / "_template.json"
    with open(path, "w", encoding="utf-8") as file:
        json.dump(template, file, indent=2, ensure_ascii=False)


def load_language(language):
    """Return all texts of one language file."""
    path = TRANSLATIONS_DIR / f"{language}.json"
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as file:
        return clean_texts(json.load(file))


def clean_texts(raw):
    """Return code to text, accepting plain strings or filled template entries."""
    texts = {}
    for code, value in raw.items():
        if isinstance(value, dict):
            value = value.get("translation", "")
        if value:
            texts[code] = value
    return texts
