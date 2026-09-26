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
