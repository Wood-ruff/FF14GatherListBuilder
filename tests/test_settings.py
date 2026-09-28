import pytest

import settings


@pytest.fixture(autouse=True)
def isolated_settings_file(tmp_path, monkeypatch):
    monkeypatch.setattr("settings.SETTINGS_FILE", tmp_path / "settings.json")


def test_default_language_is_english():
    assert settings.get_language() == "en"


def test_set_and_get_language():
    settings.set_language("de")
    assert settings.get_language() == "de"


def test_unsupported_language_is_rejected():
    settings.set_language("klingon")
    assert settings.get_language() == "en"


def test_unreadable_settings_count_as_empty():
    settings.SETTINGS_FILE.write_text("", encoding="utf-8")
    assert settings.get_language() == "en"