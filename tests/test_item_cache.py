import json
from datetime import date, timedelta

import pytest

import item_cache

RESULT = {"row_id": 5111, "fields": {"Name": "Iron Ore"}}


@pytest.fixture(autouse=True)
def isolated_cache_file(tmp_path, monkeypatch):
    monkeypatch.setattr("item_cache.CACHE_FILE", tmp_path / "item_cache.json")


def test_store_and_get_round_trip():
    item_cache.store_result("Iron Ore", RESULT)
    assert item_cache.get_fresh_result("iron ore") == RESULT


def test_missing_item_returns_none():
    assert item_cache.get_fresh_result("Unknown") is None


def test_expired_entry_returns_none(monkeypatch):
    item_cache.store_result("Iron Ore", RESULT)
    cache = item_cache.load_cache()
    old_date = date.today() - timedelta(days=item_cache.MAX_AGE_DAYS + 1)
    cache["iron ore"]["fetchdate"] = old_date.isoformat()
    item_cache.CACHE_FILE.write_text(json.dumps(cache))
    assert item_cache.get_fresh_result("Iron Ore") is None


def test_entry_gets_fetchdate():
    item_cache.store_result("Iron Ore", RESULT)
    entry = item_cache.load_cache()["iron ore"]
    assert entry["fetchdate"] == date.today().isoformat()
