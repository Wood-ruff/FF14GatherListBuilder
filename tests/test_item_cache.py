import json
from datetime import date, timedelta

import pytest

import item_cache
import storage

RESULT = {"row_id": 5111, "fields": {"Name": "Iron Ore"}}


@pytest.fixture(autouse=True)
def isolated_cache_file(tmp_path, monkeypatch):
    monkeypatch.setattr("item_cache.CACHE_FILE", tmp_path / "item_cache.json")
    monkeypatch.setattr("item_cache.ICONS_DIR", tmp_path / "icons")


def test_cache_lives_outside_the_lists_folder():
    assert item_cache.CACHE_FILE.parent != storage.DATA_DIR
    assert item_cache.ICONS_DIR != storage.DATA_DIR


def test_store_and_get_round_trip():
    item_cache.store_result("Iron Ore", RESULT)
    assert item_cache.get_fresh_result("iron ore") == RESULT


def test_missing_item_returns_none():
    assert item_cache.get_fresh_result("Unknown") is None


def test_expired_entry_returns_none(monkeypatch):
    item_cache.store_result("Iron Ore", RESULT)
    cache = item_cache.load_cache()
    old_date = date.today() - timedelta(days=item_cache.MAX_AGE_DAYS + 1)
    cache["item:iron ore"]["fetchdate"] = old_date.isoformat()
    item_cache.CACHE_FILE.write_text(json.dumps(cache))
    assert item_cache.get_fresh_result("Iron Ore") is None


def test_entry_gets_fetchdate_and_type():
    item_cache.store_result("Iron Ore", RESULT)
    entry = item_cache.load_cache()["item:iron ore"]
    assert entry["fetchdate"] == date.today().isoformat()
    assert entry["type"] == "item"


def test_icon_store_and_check():
    assert not item_cache.has_icon(5111)
    item_cache.store_icon(5111, b"png-bytes")
    assert item_cache.has_icon(5111)


def test_clear_removes_file_and_icons():
    item_cache.store_result("Iron Ore", RESULT)
    item_cache.store_icon(5111, b"png-bytes")
    item_cache.clear()
    assert item_cache.load_cache() == {}
    assert not item_cache.has_icon(5111)


def test_item_and_recipe_entries_are_separate():
    recipe = {"yields": 1, "ingredients": []}
    item_cache.store_result("Iron Ore", RESULT, "item")
    item_cache.store_result("Iron Ore", recipe, "recipe")
    assert item_cache.get_fresh_result("Iron Ore", "item") == RESULT
    assert item_cache.get_fresh_result("Iron Ore", "recipe") == recipe
    assert item_cache.load_cache()["recipe:iron ore"]["type"] == "recipe"
