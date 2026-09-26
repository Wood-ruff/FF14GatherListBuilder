import pytest
import requests

import item_cache
import xivapi


@pytest.fixture(autouse=True)
def isolated_caches(tmp_path, monkeypatch):
    monkeypatch.setattr("item_cache.CACHE_FILE", tmp_path / "item_cache.json")
    xivapi.CACHE.clear()


SEARCH_RESULTS = [
    {"row_id": 5111, "fields": {"Name": "Iron Ore"}},
    {"row_id": 19953, "fields": {"Name": "Doman Iron Ore"}},
]


class FakeResponse:
    def __init__(self, results):
        self.results = results

    def raise_for_status(self):
        pass

    def json(self):
        return {"results": self.results}


def test_fetch_item_id_matches_exact_name(monkeypatch):
    monkeypatch.setattr("requests.get", lambda *a, **k: FakeResponse(SEARCH_RESULTS))
    assert xivapi.fetch_item_id("iron ore") == 5111


def test_fetch_item_id_unknown_item(monkeypatch):
    monkeypatch.setattr("requests.get", lambda *a, **k: FakeResponse([]))
    assert xivapi.fetch_item_id("Not A Real Item") is None


def test_fetch_item_id_ignores_partial_matches(monkeypatch):
    monkeypatch.setattr("requests.get", lambda *a, **k: FakeResponse(SEARCH_RESULTS))
    assert xivapi.fetch_item_id("Doman Iron") is None


def test_fetch_item_id_calls_api_only_once_per_name(monkeypatch):
    calls = []

    def counting_get(*args, **kwargs):
        calls.append(1)
        return FakeResponse(SEARCH_RESULTS)

    monkeypatch.setattr("requests.get", counting_get)
    xivapi.fetch_item_id("Iron Ore")
    xivapi.fetch_item_id("iron ore")
    xivapi.fetch_item_id("IRON ORE")
    assert len(calls) == 1


def test_cache_file_answers_after_memory_is_cleared(monkeypatch):
    calls = []

    def counting_get(*args, **kwargs):
        calls.append(1)
        return FakeResponse(SEARCH_RESULTS)

    monkeypatch.setattr("requests.get", counting_get)
    xivapi.fetch_item_id("Iron Ore")
    xivapi.CACHE.clear()
    assert xivapi.fetch_item_id("Iron Ore") == 5111
    assert len(calls) == 1


def test_failed_lookup_is_not_written_to_cache_file(monkeypatch):
    monkeypatch.setattr("requests.get", lambda *a, **k: FakeResponse([]))
    xivapi.fetch_item_id("Not A Real Item")
    assert item_cache.load_cache() == {}


def test_search_survives_network_error(monkeypatch):
    def broken_get(*args, **kwargs):
        raise requests.ConnectionError()

    monkeypatch.setattr("requests.get", broken_get)
    assert xivapi.fetch_item_id("Iron Ore") is None
