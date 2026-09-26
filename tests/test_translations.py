import translations


def test_english_texts_exist():
    texts = translations.all_texts("en")
    assert texts["add"] == "Add"


def test_german_overlays_english():
    texts = translations.all_texts("de")
    assert texts["add"] == "Hinzufügen"


def test_unknown_language_falls_back_to_english():
    texts = translations.all_texts("xx")
    assert texts["add"] == "Add"


def test_german_covers_every_english_code():
    english = translations.load_language("en")
    german = translations.load_language("de")
    assert sorted(english.keys()) == sorted(german.keys())


def test_template_covers_every_english_code_with_empty_translations():
    import json

    translations.write_template()
    raw = json.loads((translations.TRANSLATIONS_DIR / "_template.json").read_text(encoding="utf-8"))
    english = translations.load_language("en")
    assert sorted(raw.keys()) == sorted(english.keys())
    for code, entry in raw.items():
        assert entry["english"] == english[code]
        assert entry["translation"] == ""


def test_filled_template_entries_are_usable_and_empty_ones_fall_back():
    texts = translations.clean_texts({
        "add": {"english": "Add", "translation": "Ajouter"},
        "save": {"english": "Save", "translation": ""},
    })
    assert texts == {"add": "Ajouter"}
