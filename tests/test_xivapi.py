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
    xivapi.SUGGESTIONS.clear()
    xivapi.GATHERING.clear()
    xivapi.COLLECTABLES.clear()
    xivapi.CRAFTABLES.clear()
    xivapi.API_STATUS["last_call_failed"] = False
    monkeypatch.setattr("settings.get_language", lambda: "en")


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


def test_suggestions_return_names_and_are_cached(monkeypatch):
    calls = []

    def counting_get(*args, **kwargs):
        calls.append(1)
        return item_search_response(SEARCH_RESULTS)

    monkeypatch.setattr("requests.get", counting_get)
    names = xivapi.search_item_names("iron")
    assert names == ["Iron Ore", "Doman Iron Ore"]
    xivapi.search_item_names("Iron")
    assert len(calls) == 1


def test_suggestions_use_the_higher_search_limit(monkeypatch):
    seen_params = []

    def capturing_get(url, params=None, **kwargs):
        seen_params.append(params)
        return item_search_response(SEARCH_RESULTS)

    monkeypatch.setattr("requests.get", capturing_get)
    xivapi.search_item_names("iron")
    assert seen_params[0]["limit"] == xivapi.SUGGESTION_LIMIT


def test_suggestions_are_cached_per_language(monkeypatch):
    monkeypatch.setattr("requests.get", lambda *a, **k: item_search_response(SEARCH_RESULTS))
    xivapi.search_item_names("iron")

    monkeypatch.setattr("settings.get_language", lambda: "de")
    monkeypatch.setattr("requests.get", lambda *a, **k: item_search_response([]))
    assert xivapi.search_item_names("iron") == []


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


GATHERING_ITEM_ROW = [{"row_id": 10202, "fields": {}}]

NODE_BASE_ROW = [{
    "row_id": 1029,
    "fields": {
        "Item": [
            {"row_id": 10202, "fields": {"Item": {"row_id": 43930, "fields": {"Name": "Bay Leaf"}}}},
            {"row_id": 10203, "fields": {"Item": {"row_id": 43931, "fields": {"Name": "Other Leaf"}}}},
            {"row_id": 0, "fields": {"Item": {"row_id": 0, "fields": {"Name": ""}}}},
        ],
    },
}]

NODE_POINT_ROW = [{
    "row_id": 34989,
    "fields": {
        "TerritoryType": {
            "fields": {
                "PlaceName": {"fields": {"Name": "Living Memory"}},
                "Aetheryte": {"row_id": 213, "fields": {"PlaceName": {"fields": {"Name": "Leynode Mnemo"}}}},
            },
        },
    },
}]

TRANSIENT_ROW = {
    "row_id": 34989,
    "fields": {
        "EphemeralStartTime": 65535,
        "EphemeralEndTime": 65535,
        "GatheringRarePopTimeTable": {
            "row_id": 133,
            "fields": {"StartTime": [1000, 2200, 65535], "Duration": [160, 160, 0]},
        },
    },
}


def gathering_api(url, params=None, **kwargs):
    if "sheet/GatheringPointTransient" in url:
        return FakeResponse(TRANSIENT_ROW)
    sheet = params.get("sheets") if params else None
    if sheet == "GatheringItem":
        return item_search_response(GATHERING_ITEM_ROW)
    if sheet == "GatheringPointBase":
        return item_search_response(NODE_BASE_ROW)
    if sheet == "GatheringPoint":
        return item_search_response(NODE_POINT_ROW)
    return item_search_response([])


def test_fetch_gathering_returns_timed_node_info(monkeypatch):
    monkeypatch.setattr("requests.get", gathering_api)
    info = xivapi.fetch_gathering(43930)
    assert info == {
        "timed": True,
        "times": [{"start": 600, "duration": 120}, {"start": 1320, "duration": 120}],
        "zone": "Living Memory",
        "aetheryte": "Leynode Mnemo",
    }


def test_cached_node_answers_for_other_items_in_it(monkeypatch):
    monkeypatch.setattr("requests.get", gathering_api)
    xivapi.fetch_gathering(43930)

    def no_more_calls(*args, **kwargs):
        raise AssertionError("expected no api call")

    monkeypatch.setattr("requests.get", no_more_calls)
    xivapi.GATHERING.clear()
    info = xivapi.fetch_gathering(43931)
    assert info["timed"] is True
    assert info["zone"] == "Living Memory"


def test_ungatherable_item_is_marked_in_cache(monkeypatch):
    monkeypatch.setattr("requests.get", lambda *a, **k: item_search_response([]))
    info = xivapi.fetch_gathering(5111)
    assert info == {"timed": False, "times": [], "zone": None, "aetheryte": None}
    assert item_cache.load_cache()["gathering:5111"]["result"]["timed"] is False


def test_gathering_network_error_is_not_cached(monkeypatch):
    def broken_get(*args, **kwargs):
        raise requests.ConnectionError()

    monkeypatch.setattr("requests.get", broken_get)
    assert xivapi.fetch_gathering(43930) is None
    assert "gathering:43930" not in item_cache.load_cache()


COLLECTABLE_ITEMS_PAGE = {"results": [
    {
        "row_id": 10202,
        "fields": {
            "Item": {"row_id": 43930, "fields": {"Name": "Rarefied Windsbalm Bay Leaf"}},
            "GatheringItemLevel": {"fields": {"GatheringItemLevel": 100, "Stars": 2}},
        },
    },
]}

SHOP_PAGE = {"results": [
    {
        "row_id": 1,
        "fields": {
            "Item": {"row_id": 43930, "fields": {}},
            "CollectablesShopRewardScrip": {"fields": {"LowReward": 16, "MidReward": 23, "HighReward": 38}},
        },
    },
]}

BASES_PAGE = {"results": [
    {
        "row_id": 1029,
        "fields": {
            "GatheringType": {"row_id": 3, "fields": {"Name": "Harvesting"}},
            "Item": [
                {"row_id": 10202, "fields": {"IsHidden": False}},
                {"row_id": 0, "fields": {"IsHidden": False}},
            ],
        },
    },
]}

POINTS_PAGE = {"results": [
    {
        "row_id": 34989,
        "fields": {
            "GatheringPointBase": {"row_id": 1029, "fields": {"GatheringLevel": 100}},
            "TerritoryType": {"fields": {
                "PlaceName": {"fields": {"Name": "Living Memory"}},
                "Aetheryte": {"row_id": 213, "fields": {"PlaceName": {"fields": {"Name": "Leynode Mnemo"}}}},
                "Map": {"fields": {"SizeFactor": 100, "OffsetX": 0, "OffsetY": 0}},
            }},
        },
    },
]}

EXPORTED_ROWS = {"rows": [{"row_id": 1029, "fields": {"X": -637.213, "Y": -699.634}}]}

TRANSIENT_BATCH = {"rows": [{
    "row_id": 34989,
    "fields": {
        "EphemeralStartTime": 65535,
        "EphemeralEndTime": 65535,
        "GatheringRarePopTimeTable": {
            "fields": {"StartTime": [1000, 2200, 65535], "Duration": [160, 160, 0]},
        },
    },
}]}

GTYPE_ROWS = {"rows": [{"row_id": 3, "fields": {"IconMain": {"path": "ui/icon/060000/060432.tex"}}}]}


def collectables_api(url, params=None, **kwargs):
    if url == xivapi.ASSET_URL:
        return FakeResponse(content=b"job-icon")
    if "sheet/ExportedGatheringPoint" in url:
        return FakeResponse(EXPORTED_ROWS)
    if "sheet/GatheringPointTransient" in url:
        return FakeResponse(TRANSIENT_BATCH)
    if "sheet/GatheringType" in url:
        return FakeResponse(GTYPE_ROWS)
    pages = {
        "GatheringItem": COLLECTABLE_ITEMS_PAGE,
        "CollectablesShopItem": SHOP_PAGE,
        "GatheringPointBase": BASES_PAGE,
        "GatheringPoint": POINTS_PAGE,
    }
    return FakeResponse(pages[params["sheets"]])


def test_fetch_collectables_builds_full_entries(monkeypatch):
    monkeypatch.setattr("requests.get", collectables_api)
    assert xivapi.fetch_collectables() == [{
        "game_id": 43930,
        "name": "Rarefied Windsbalm Bay Leaf",
        "level": 100,
        "stars": 2,
        "scrips": {"low": 16, "mid": 23, "high": 38},
        "job": "Harvesting",
        "job_id": 3,
        "zone": "Living Memory",
        "aetheryte": "Leynode Mnemo",
        "x": 8.7,
        "y": 7.5,
        "times": [{"start": 600, "duration": 120}, {"start": 1320, "duration": 120}],
        "timed": True,
    }]
    assert item_cache.has_icon("jobtype_3")


def test_collectables_build_stores_gathering_markers(monkeypatch):
    monkeypatch.setattr("requests.get", collectables_api)
    xivapi.fetch_collectables()

    def no_more_calls(*args, **kwargs):
        raise AssertionError("expected no api call")

    monkeypatch.setattr("requests.get", no_more_calls)
    info = xivapi.fetch_gathering(43930)
    assert info["timed"] is True
    assert info["zone"] == "Living Memory"
    assert info["aetheryte"] == "Leynode Mnemo"


def test_fetch_collectables_is_cached(monkeypatch):
    monkeypatch.setattr("requests.get", collectables_api)
    xivapi.fetch_collectables()
    assert item_cache.load_cache()["collectables:en"]["type"] == "collectables"

    def no_more_calls(*args, **kwargs):
        raise AssertionError("expected no api call")

    monkeypatch.setattr("requests.get", no_more_calls)
    xivapi.COLLECTABLES.clear()
    assert xivapi.fetch_collectables()[0]["zone"] == "Living Memory"


RECIPE_PAGE = {"results": [
    {
        "row_id": 3603,
        "fields": {
            "ItemResult": {"row_id": 43954, "fields": {"Name": "Rarefied Tacos de Carne Asada"}},
            "CraftType": {"row_id": 7, "fields": {"Name": "Cooking"}},
            "RecipeLevelTable": {"fields": {"ClassJobLevel": 100, "Stars": 1}},
        },
    },
    {
        "row_id": 3604,
        "fields": {
            "ItemResult": {"row_id": 31100, "fields": {"Name": "Oddly Specific Lumber"}},
            "CraftType": {"row_id": 0, "fields": {"Name": "Woodworking"}},
            "RecipeLevelTable": {"fields": {"ClassJobLevel": 80, "Stars": 0}},
        },
    },
    {
        "row_id": 3605,
        "fields": {
            "ItemResult": {"row_id": 31100, "fields": {"Name": "Oddly Specific Lumber"}},
            "CraftType": {"row_id": 1, "fields": {"Name": "Smithing"}},
            "RecipeLevelTable": {"fields": {"ClassJobLevel": 80, "Stars": 0}},
        },
    },
]}

CRAFT_SHOP_PAGE = {"results": [
    {
        "row_id": 2,
        "fields": {
            "Item": {"row_id": 43954, "fields": {}},
            "CollectablesShopRewardScrip": {"fields": {"LowReward": 12, "MidReward": 18, "HighReward": 27}},
        },
    },
]}


def craftables_api(url, params=None, **kwargs):
    if params["sheets"] == "Recipe":
        return FakeResponse(RECIPE_PAGE)
    return FakeResponse(CRAFT_SHOP_PAGE)


def test_fetch_craftables_groups_jobs_per_item(monkeypatch):
    monkeypatch.setattr("requests.get", craftables_api)
    craftables = xivapi.fetch_craftables()
    assert craftables == [
        {
            "game_id": 43954,
            "name": "Rarefied Tacos de Carne Asada",
            "level": 100,
            "stars": 1,
            "jobs": ["Cooking"],
            "scrips": {"low": 12, "mid": 18, "high": 27},
        },
        {
            "game_id": 31100,
            "name": "Oddly Specific Lumber",
            "level": 80,
            "stars": 0,
            "jobs": ["Woodworking", "Smithing"],
            "scrips": None,
        },
    ]


def test_fetch_craftables_is_cached(monkeypatch):
    monkeypatch.setattr("requests.get", craftables_api)
    xivapi.fetch_craftables()
    assert item_cache.load_cache()["craftables:en"]["type"] == "craftables"

    def no_more_calls(*args, **kwargs):
        raise AssertionError("expected no api call")

    monkeypatch.setattr("requests.get", no_more_calls)
    xivapi.CRAFTABLES.clear()
    assert len(xivapi.fetch_craftables()) == 2


def test_fetch_recipe_for_uncraftable_item(monkeypatch):
    def no_recipe_api(url, params=None, **kwargs):
        if params and params.get("sheets") == "Recipe":
            return item_search_response([])
        return item_search_response(HEADBAND_SEARCH)

    monkeypatch.setattr("requests.get", no_recipe_api)
    assert xivapi.fetch_recipe("Crested Headband") is None
    assert "recipe:crested headband" not in item_cache.load_cache()
