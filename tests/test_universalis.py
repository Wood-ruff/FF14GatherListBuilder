import json
from datetime import datetime, timedelta

import pytest
import requests

import item_cache
import universalis


@pytest.fixture(autouse=True)
def isolated_caches(tmp_path, monkeypatch):
    monkeypatch.setattr("item_cache.CACHE_FILE", tmp_path / "item_cache.json")
    monkeypatch.setattr("item_cache.ICONS_DIR", tmp_path / "icons")


class FakeResponse:
    def __init__(self, data):
        self.data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self.data


MARKET_DATA = {
    "items": {
        "100": {"minPrice": 500, "averagePrice": 450.7, "unitsSold": 657,
                "recentHistory": [{"pricePerUnit": 480}, {"pricePerUnit": 430}, {"pricePerUnit": 610}]},
        "101": {"minPrice": 0, "averagePrice": 0, "unitsSold": 0},
    },
    "unresolvedItems": [102],
}


def market_api(url, params=None, **kwargs):
    if url.endswith("/worlds"):
        return FakeResponse([{"id": 66, "name": "Odin"}, {"id": 33, "name": "Twintania"}])
    if url.endswith("/marketable"):
        return FakeResponse([100, 101])
    return FakeResponse(MARKET_DATA)


def no_more_calls(*args, **kwargs):
    raise AssertionError("expected no api call")


def test_worlds_are_fetched_and_cached(monkeypatch):
    monkeypatch.setattr("requests.get", market_api)
    assert universalis.fetch_worlds() == [{"id": 66, "name": "Odin"}, {"id": 33, "name": "Twintania"}]
    monkeypatch.setattr("requests.get", no_more_calls)
    assert universalis.fetch_worlds()[0]["name"] == "Odin"


def test_marketable_ids_become_a_set_and_are_cached(monkeypatch):
    monkeypatch.setattr("requests.get", market_api)
    assert universalis.fetch_marketable_ids() == {100, 101}
    monkeypatch.setattr("requests.get", no_more_calls)
    assert universalis.fetch_marketable_ids() == {100, 101}


def test_market_stats_reduce_to_prices_and_week_volume(monkeypatch):
    monkeypatch.setattr("requests.get", market_api)
    stats = universalis.fetch_market_stats(66, [100, 101, 102])
    assert stats[100] == {"price": 500, "avg_price": 451, "min_sale": 430, "max_sale": 610,
                          "week_volume": 657}
    assert stats[101] == {"price": 0, "avg_price": 0, "min_sale": 0, "max_sale": 0, "week_volume": 0}
    assert stats[102] == {"price": 0, "avg_price": 0, "min_sale": 0, "max_sale": 0, "week_volume": 0}


def test_old_shape_cached_market_stats_are_refetched(monkeypatch):
    monkeypatch.setattr("requests.get", market_api)
    universalis.fetch_market_stats(66, [100])
    cache = item_cache.load_cache()
    del cache["market_stats:66:100"]["result"]["min_sale"]
    item_cache.CACHE_FILE.write_text(json.dumps(cache), encoding="utf-8")
    assert universalis.fetch_market_stats(66, [100])[100]["min_sale"] == 430


def test_market_stats_request_the_full_week_of_history(monkeypatch):
    seen = {}

    def capture(url, params=None, **kwargs):
        seen.update(params)
        return market_api(url, params, **kwargs)

    monkeypatch.setattr("requests.get", capture)
    universalis.fetch_market_stats(66, [100])
    assert seen["entries"] == universalis.MAX_HISTORY_ENTRIES
    assert seen["entriesWithin"] == universalis.HISTORY_WINDOW_SECONDS


def test_market_stats_come_from_cache_within_ttl(monkeypatch):
    monkeypatch.setattr("requests.get", market_api)
    universalis.fetch_market_stats(66, [100])
    monkeypatch.setattr("requests.get", no_more_calls)
    assert universalis.fetch_market_stats(66, [100])[100]["price"] == 500


def test_stale_market_stats_are_fetched_again(monkeypatch):
    monkeypatch.setattr("requests.get", market_api)
    universalis.fetch_market_stats(66, [100])
    cache = item_cache.load_cache()
    too_old = datetime.now() - timedelta(hours=universalis.MARKET_TTL_HOURS + 1)
    cache["market_stats:66:100"]["fetchdate"] = too_old.isoformat()
    item_cache.CACHE_FILE.write_text(json.dumps(cache), encoding="utf-8")

    def count_calls(url, params=None, **kwargs):
        count_calls.calls += 1
        return market_api(url, params, **kwargs)

    count_calls.calls = 0
    monkeypatch.setattr("requests.get", count_calls)
    assert universalis.fetch_market_stats(66, [100])[100]["price"] == 500
    assert count_calls.calls == 1


def test_single_item_response_shape(monkeypatch):
    single = {"itemID": 100, "minPrice": 250, "averagePrice": 260.2, "unitsSold": 7,
              "recentHistory": [{"pricePerUnit": 260}]}
    monkeypatch.setattr("requests.get", lambda url, params=None, **kwargs: FakeResponse(single))
    stats = universalis.fetch_market_stats(66, [100])
    assert stats[100] == {"price": 250, "avg_price": 260, "min_sale": 260, "max_sale": 260,
                          "week_volume": 7}


def test_market_stats_retry_a_failed_chunk_once(monkeypatch):
    attempts = {"count": 0}

    def flaky(url, params=None, **kwargs):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise requests.RequestException("504")
        return market_api(url, params, **kwargs)

    monkeypatch.setattr("requests.get", flaky)
    assert universalis.fetch_market_stats(66, [100])[100]["price"] == 500
    assert attempts["count"] == 2


def test_failed_lookups_return_none(monkeypatch):
    def down(url, params=None, **kwargs):
        raise requests.RequestException("down")

    monkeypatch.setattr("requests.get", down)
    assert universalis.fetch_worlds() is None
    assert universalis.fetch_marketable_ids() is None
    assert universalis.fetch_market_stats(66, [100]) is None
