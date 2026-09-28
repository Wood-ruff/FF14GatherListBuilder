import json
from datetime import date, datetime, timedelta

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
    assert entry["fetchdate"].startswith(date.today().isoformat())
    assert entry["type"] == "item"


def test_hour_based_expiry_only_affects_short_lived_kinds():
    item_cache.store_result("Iron Ore", RESULT)
    cache = item_cache.load_cache()
    cache["item:iron ore"]["fetchdate"] = (datetime.now() - timedelta(hours=4)).isoformat()
    item_cache.CACHE_FILE.write_text(json.dumps(cache))
    assert item_cache.get_fresh_result("Iron Ore", max_age_hours=3) is None
    assert item_cache.get_fresh_result("Iron Ore") == RESULT


def test_get_fresh_results_reads_many_in_one_go():
    item_cache.store_results({"66:100": {"price": 5}, "66:101": {"price": 7}}, "market_stats")
    results = item_cache.get_fresh_results(["66:100", "66:101", "66:102"], "market_stats")
    assert results == {"66:100": {"price": 5}, "66:101": {"price": 7}}


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


def test_damaged_cache_file_salvages_the_first_document():
    item_cache.store_result("Iron Ore", RESULT)
    with open(item_cache.CACHE_FILE, "a", encoding="utf-8") as file:
        file.write("    }\n  }\n}")
    assert item_cache.get_fresh_result("Iron Ore") == RESULT


def test_unreadable_cache_file_counts_as_empty():
    item_cache.CACHE_FILE.write_text("no json at all", encoding="utf-8")
    assert item_cache.load_cache() == {}
    item_cache.CACHE_FILE.write_text("42 garbage", encoding="utf-8")
    assert item_cache.load_cache() == {}


def test_storing_heals_a_damaged_cache_file():
    item_cache.store_result("Iron Ore", RESULT)
    with open(item_cache.CACHE_FILE, "a", encoding="utf-8") as file:
        file.write("}}}")
    item_cache.store_result("Coke", {"row_id": 1})
    healed = json.loads(item_cache.CACHE_FILE.read_text(encoding="utf-8"))
    assert healed["item:iron ore"]["result"] == RESULT
    assert healed["item:coke"]["result"] == {"row_id": 1}


def test_item_and_recipe_entries_are_separate():
    recipe = {"yields": 1, "ingredients": []}
    item_cache.store_result("Iron Ore", RESULT, "item")
    item_cache.store_result("Iron Ore", recipe, "recipe")
    assert item_cache.get_fresh_result("Iron Ore", "item") == RESULT
    assert item_cache.get_fresh_result("Iron Ore", "recipe") == recipe
    assert item_cache.load_cache()["recipe:iron ore"]["type"] == "recipe"
