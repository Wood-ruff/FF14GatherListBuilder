import pytest
import requests

import item_cache
import xivapi


@pytest.fixture(autouse=True)
def isolated_caches(tmp_path, monkeypatch):
    monkeypatch.setattr("item_cache.CACHE_FILE", tmp_path / "item_cache.json")
    monkeypatch.setattr("item_cache.ICONS_DIR", tmp_path / "icons")
    xivapi.CACHE.clear()
    xivapi.RECIPES.clear()
    xivapi.API_STATUS["last_call_failed"] = False


SEARCH_RESULTS = [
    {"row_id": 5111, "fields": {"Name": "Iron Ore"}},
    {"row_id": 19953, "fields": {"Name": "Doman Iron Ore"}},
]

HEADBAND_SEARCH = [{"row_id": 47184, "fields": {"Name": "Crested Headband"}}]

RECIPE_ROW = {
    "row_id": 37451,
    "fields": {
        "AmountResult": 1,
        "AmountIngredient": [2, 3, 0],
        "Ingredient": [
            {"row_id": 45978, "fields": {"Name": "Diatryma Felt"}},
            {"row_id": 16, "fields": {"Name": "Wind Cluster"}},
            {"row_id": 0, "fields": {"Name": ""}},
        ],
    },
}


class FakeResponse:
    def __init__(self, data=None, content=b""):
        self.data = data
        self.content = content

    def raise_for_status(self):
        pass

    def json(self):
        return self.data


def item_search_response(results):
    return FakeResponse({"results": results})


def fake_api(url, params=None, **kwargs):
    if "sheet/Recipe" in url:
        return FakeResponse(RECIPE_ROW)
    if params and params.get("sheets") == "Recipe":
        return item_search_response([{"row_id": 37451, "fields": {}}])
    return item_search_response(HEADBAND_SEARCH)


def test_fetch_item_id_matches_exact_name(monkeypatch):
    monkeypatch.setattr("requests.get", lambda *a, **k: item_search_response(SEARCH_RESULTS))
    assert xivapi.fetch_item_id("iron ore") == 5111


def test_fetch_item_id_unknown_item(monkeypatch):
    monkeypatch.setattr("requests.get", lambda *a, **k: item_search_response([]))
    assert xivapi.fetch_item_id("Not A Real Item") is None


def test_fetch_item_id_ignores_partial_matches(monkeypatch):
    monkeypatch.setattr("requests.get", lambda *a, **k: item_search_response(SEARCH_RESULTS))
    assert xivapi.fetch_item_id("Doman Iron") is None


def test_fetch_item_id_calls_api_only_once_per_name(monkeypatch):
    calls = []

    def counting_get(*args, **kwargs):
        calls.append(1)
        return item_search_response(SEARCH_RESULTS)

    monkeypatch.setattr("requests.get", counting_get)
    xivapi.fetch_item_id("Iron Ore")
    xivapi.fetch_item_id("iron ore")
    xivapi.fetch_item_id("IRON ORE")
    assert len(calls) == 1


def test_cache_file_answers_after_memory_is_cleared(monkeypatch):
    calls = []

    def counting_get(*args, **kwargs):
        calls.append(1)
        return item_search_response(SEARCH_RESULTS)

    monkeypatch.setattr("requests.get", counting_get)
    xivapi.fetch_item_id("Iron Ore")
    xivapi.CACHE.clear()
    assert xivapi.fetch_item_id("Iron Ore") == 5111
    assert len(calls) == 1


def test_failed_lookup_is_not_written_to_cache_file(monkeypatch):
    monkeypatch.setattr("requests.get", lambda *a, **k: item_search_response([]))
    xivapi.fetch_item_id("Not A Real Item")
    assert item_cache.load_cache() == {}


def test_search_uses_configured_language(monkeypatch):
    seen_params = []

    def capturing_get(url, params=None, **kwargs):
        seen_params.append(params)
        return item_search_response(SEARCH_RESULTS)

    monkeypatch.setattr("requests.get", capturing_get)
    monkeypatch.setattr("settings.get_language", lambda: "de")
    xivapi.fetch_item("Eisenerz")
    assert seen_params[0]["language"] == "de"


def test_search_survives_network_error(monkeypatch):
    def broken_get(*args, **kwargs):
        raise requests.ConnectionError()

    monkeypatch.setattr("requests.get", broken_get)
    assert xivapi.fetch_item_id("Iron Ore") is None


def test_network_error_sets_and_success_clears_failure_flag(monkeypatch):
    def broken_get(*args, **kwargs):
        raise requests.ConnectionError()

    monkeypatch.setattr("requests.get", broken_get)
    xivapi.fetch_item_id("Iron Ore")
    assert xivapi.last_call_failed()

    monkeypatch.setattr("requests.get", lambda *a, **k: item_search_response(SEARCH_RESULTS))
    xivapi.CACHE.clear()
    xivapi.fetch_item_id("Iron Ore")
    assert not xivapi.last_call_failed()


ICON_ITEM = [
    {"row_id": 5111, "fields": {"Name": "Iron Ore", "Icon": {"path": "ui/icon/021000/021202.tex"}}}
]


def icon_api(url, params=None, **kwargs):
    if url == xivapi.ASSET_URL:
        return FakeResponse(content=b"png-bytes")
    return item_search_response(ICON_ITEM)


def test_icon_is_downloaded_and_cached(monkeypatch):
    monkeypatch.setattr("requests.get", icon_api)
    xivapi.fetch_item("Iron Ore")
    assert item_cache.has_icon(5111)
    assert (item_cache.ICONS_DIR / "5111.png").read_bytes() == b"png-bytes"


def test_icon_is_downloaded_only_once(monkeypatch):
    asset_calls = []

    def counting_icon_api(url, params=None, **kwargs):
        if url == xivapi.ASSET_URL:
            asset_calls.append(1)
            return FakeResponse(content=b"png-bytes")
        return item_search_response(ICON_ITEM)

    monkeypatch.setattr("requests.get", counting_icon_api)
    xivapi.fetch_item("Iron Ore")
    xivapi.CACHE.clear()
    xivapi.fetch_item("Iron Ore")
    assert len(asset_calls) == 1


def test_clear_cache_removes_icons(monkeypatch):
    monkeypatch.setattr("requests.get", icon_api)
    xivapi.fetch_item("Iron Ore")
    xivapi.clear_cache()
    assert not item_cache.has_icon(5111)


def test_fetch_recipe_returns_clean_ingredients(monkeypatch):
    monkeypatch.setattr("requests.get", fake_api)
    recipe = xivapi.fetch_recipe("Crested Headband")
    assert recipe == {
        "yields": 1,
        "ingredients": [
            {"name": "Diatryma Felt", "game_id": 45978, "amount": 2},
            {"name": "Wind Cluster", "game_id": 16, "amount": 3},
        ],
    }


def test_fetch_recipe_is_cached_with_recipe_type(monkeypatch):
    monkeypatch.setattr("requests.get", fake_api)
    xivapi.fetch_recipe("Crested Headband")
    entry = item_cache.load_cache()["recipe:crested headband"]
    assert entry["type"] == "recipe"


def test_clear_cache_wipes_memory_and_file(monkeypatch):
    monkeypatch.setattr("requests.get", fake_api)
    xivapi.fetch_recipe("Crested Headband")
    xivapi.clear_cache()
    assert xivapi.CACHE == {}
    assert xivapi.RECIPES == {}
    assert item_cache.load_cache() == {}


def test_fetch_recipe_for_uncraftable_item(monkeypatch):
    def no_recipe_api(url, params=None, **kwargs):
        if params and params.get("sheets") == "Recipe":
            return item_search_response([])
        return item_search_response(HEADBAND_SEARCH)

    monkeypatch.setattr("requests.get", no_recipe_api)
    assert xivapi.fetch_recipe("Crested Headband") is None
    assert "recipe:crested headband" not in item_cache.load_cache()
