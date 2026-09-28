import pytest
import requests

import item_cache
import xivapi


@pytest.fixture(autouse=True)
def isolated_caches(tmp_path, monkeypatch):
    monkeypatch.setattr("item_cache.CACHE_FILE", tmp_path / "item_cache.json")
    monkeypatch.setattr("item_cache.ICONS_DIR", tmp_path / "icons")
    xivapi.CACHE.clear()
    xivapi.ID_CACHE.clear()
    xivapi.RECIPES.clear()
    xivapi.SUGGESTIONS.clear()
    xivapi.GATHERING.clear()
    xivapi.COLLECTABLES.clear()
    xivapi.CRAFTABLES.clear()
    xivapi.MATERIAL_SOURCES.clear()
    xivapi.CURRENCY_SHOP.clear()
    xivapi.TOMESTONES.clear()
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
        return item_search_response([
            {"row_id": 37451, "fields": {"CraftType": {"row_id": 5, "fields": {"Name": "Clothcraft"}}}},
            {"row_id": 37452, "fields": {"CraftType": {"row_id": 1, "fields": {"Name": "Smithing"}}}},
        ])
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


ITEM_ROW = {
    "row_id": 5111,
    "fields": {"Name": "Eisenerz", "Icon": {"path": "ui/icon/021000/021202.tex"}},
}


def item_by_id_api(url, params=None, **kwargs):
    if url == xivapi.ASSET_URL:
        return FakeResponse(content=b"png")
    return FakeResponse(ITEM_ROW)


def test_fetch_item_by_id_uses_the_current_language(monkeypatch):
    seen_params = []

    def capturing_get(url, params=None, **kwargs):
        seen_params.append(params)
        return item_by_id_api(url, params)

    monkeypatch.setattr("requests.get", capturing_get)
    monkeypatch.setattr("settings.get_language", lambda: "de")
    item = xivapi.fetch_item_by_id(5111)
    assert item["fields"]["Name"] == "Eisenerz"
    assert seen_params[0]["language"] == "de"
    assert item_cache.has_icon(5111)


def test_fetch_item_by_id_is_cached_per_language(monkeypatch):
    monkeypatch.setattr("requests.get", item_by_id_api)
    xivapi.fetch_item_by_id(5111)

    def no_more_calls(*args, **kwargs):
        raise AssertionError("expected no api call")

    monkeypatch.setattr("requests.get", no_more_calls)
    xivapi.ID_CACHE.clear()
    assert xivapi.fetch_item_by_id(5111)["fields"]["Name"] == "Eisenerz"
    assert "item_id:en:5111" in item_cache.load_cache()


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
        "craft_types": ["Clothcraft", "Smithing"],
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
        "GatheringType": {"row_id": 3, "fields": {"Name": "Harvesting"}},
    },
}]

NODE_POINT_ROW = [{
    "row_id": 34989,
    "fields": {
        "TerritoryType": {
            "row_id": 1192,
            "fields": {
                "PlaceName": {"fields": {"Name": "Living Memory"}},
                "Aetheryte": {"row_id": 213, "fields": {"PlaceName": {"fields": {"Name": "Leynode Mnemo"}}}},
                "Map": {"fields": {"SizeFactor": 100, "OffsetX": 0, "OffsetY": 0}},
            },
        },
    },
}]

EXPORTED_ROW = {"row_id": 1029, "fields": {"X": -637.213, "Y": -699.634}}

MARKER_ROWS = [
    {"row_id": 700, "fields": {"X": 385, "Y": 325,
     "DataKey": {"fields": {"PlaceName": {"fields": {"Name": "Near Aetheryte"}}}}}},
    {"row_id": 700, "fields": {"X": 1800, "Y": 1800,
     "DataKey": {"fields": {"PlaceName": {"fields": {"Name": "Far Aetheryte"}}}}}},
]

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
    if "sheet/ExportedGatheringPoint/" in url:
        return FakeResponse(EXPORTED_ROW)
    if params and params.get("sheets") == "MapMarker":
        return item_search_response(MARKER_ROWS)
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
        "aetheryte": "Near Aetheryte",
        "job_ids": [3],
        "x": 8.7,
        "y": 7.5,
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
    assert info == {
        "timed": False, "times": [], "zone": None, "aetheryte": None,
        "job_ids": [], "x": None, "y": None,
    }
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
            "AmountResult": 1,
            "AmountIngredient": [2, 1, 0],
            "Ingredient": [
                {"row_id": 44137, "fields": {"Name": "Beef Skirt Steak"}},
                {"row_id": 8, "fields": {"Name": "Fire Crystal"}},
                {"row_id": 0, "fields": {"Name": ""}},
            ],
        },
    },
    {
        "row_id": 3604,
        "fields": {
            "ItemResult": {"row_id": 31100, "fields": {"Name": "Oddly Specific Lumber"}},
            "CraftType": {"row_id": 0, "fields": {"Name": "Woodworking"}},
            "RecipeLevelTable": {"fields": {"ClassJobLevel": 80, "Stars": 0}},
            "AmountResult": 1,
            "AmountIngredient": [5],
            "Ingredient": [{"row_id": 29970, "fields": {"Name": "Odd Log"}}],
        },
    },
    {
        "row_id": 3605,
        "fields": {
            "ItemResult": {"row_id": 31100, "fields": {"Name": "Oddly Specific Lumber"}},
            "CraftType": {"row_id": 1, "fields": {"Name": "Smithing"}},
            "RecipeLevelTable": {"fields": {"ClassJobLevel": 80, "Stars": 0}},
            "AmountResult": 1,
            "AmountIngredient": [5],
            "Ingredient": [{"row_id": 29970, "fields": {"Name": "Odd Log"}}],
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
            "yields": 1,
            "ingredients": [
                {"name": "Beef Skirt Steak", "game_id": 44137, "amount": 2},
                {"name": "Fire Crystal", "game_id": 8, "amount": 1},
            ],
        },
        {
            "game_id": 31100,
            "name": "Oddly Specific Lumber",
            "level": 80,
            "stars": 0,
            "jobs": ["Woodworking", "Smithing"],
            "scrips": None,
            "yields": 1,
            "ingredients": [{"name": "Odd Log", "game_id": 29970, "amount": 5}],
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


SEARCH_ITEM_ROWS = {
    "GatheringItem": {11: 101, 12: 102},
    "FishParameter": {21: 103},
    "SpearfishingItem": {31: 104},
    "GilShopItem": {262144: 201, 262145: 101},
    "GCScripShopItem": {41: 303},
}

ITEM_SEARCH_IDS = {
    "AetherialReduce>=1": [102, 401],
    'Name~"aethersand"': [410],
    "ItemUICategory=100": [26807, 33913],
}

SPECIAL_SHOP_PAGE = {"rows": [
    {"row_id": 1769601, "fields": {"Item": [
        {"Item@as(raw)": [301, 0], "Quest@as(raw)": 0, "AchievementUnlock@as(raw)": 0},
        {"Item@as(raw)": [302], "Quest@as(raw)": 70000, "AchievementUnlock@as(raw)": 0},
        {"Item@as(raw)": [301], "Quest@as(raw)": 70000, "AchievementUnlock@as(raw)": 0},
        {"Item@as(raw)": [304], "ItemCost@as(raw)": [26807, 0], "CurrencyCost": [3, 0, 0],
         "Quest@as(raw)": 0, "AchievementUnlock@as(raw)": 0},
        {"Item@as(raw)": [305], "ItemCost@as(raw)": [26807, 0], "CurrencyCost": [3, 0, 0],
         "Quest@as(raw)": 0, "AchievementUnlock@as(raw)": 0},
        {"Item@as(raw)": [305], "ItemCost@as(raw)": [1, 0, 0], "CostType": [2, 0, 0],
         "CurrencyCost": [100, 0, 0], "Quest@as(raw)": 0, "AchievementUnlock@as(raw)": 0},
        {"Item@as(raw)": [306, 0], "ItemCost@as(raw)": [2, 0, 0], "CostType": [3, 0, 0],
         "CurrencyCost": [200, 0, 0], "ReceiveCount": [1, 1],
         "Quest@as(raw)": 0, "AchievementUnlock@as(raw)": 0},
    ]}},
]}

NODE_SHEET_PAGES = {
    "GatheringPointBase": {"rows": [
        {"row_id": 500, "fields": {"Item@as(raw)": [11, 0]}},
        {"row_id": 501, "fields": {"Item@as(raw)": [12, 0]}},
    ]},
    "GatheringPointTransient": {"rows": [
        {"row_id": 900, "fields": {"EphemeralStartTime": 65535, "GatheringRarePopTimeTable@as(raw)": 5}},
        {"row_id": 901, "fields": {"EphemeralStartTime": 65535, "GatheringRarePopTimeTable@as(raw)": 0}},
    ]},
    "GatheringPoint": {"rows": [
        {"row_id": 900, "fields": {"GatheringPointBase@as(raw)": 500}},
        {"row_id": 901, "fields": {"GatheringPointBase@as(raw)": 501}},
    ]},
    "TomestonesItem": {"rows": [
        {"row_id": 0, "fields": {"Item@as(raw)": 23, "Tomestones@as(raw)": 0}},
        {"row_id": 3, "fields": {"Item@as(raw)": 28, "Tomestones@as(raw)": 1}},
    ]},
}


def material_sources_api(url, params=None, **kwargs):
    for sheet, page in NODE_SHEET_PAGES.items():
        if url.endswith("/" + sheet):
            return FakeResponse(page)
    if url.endswith("/SpecialShop"):
        return FakeResponse(SPECIAL_SHOP_PAGE)
    if params["sheets"] == "Item":
        return FakeResponse({"results": [
            {"row_id": item_id, "fields": {"Name": ""}} for item_id in ITEM_SEARCH_IDS[params["query"]]
        ]})
    rows = SEARCH_ITEM_ROWS[params["sheets"]]
    return FakeResponse({"results": [
        {"row_id": row_id, "fields": {"Item@as(raw)": item_id}} for row_id, item_id in rows.items()
    ]})


def test_fetch_material_sources_classifies_item_ids(monkeypatch):
    monkeypatch.setattr("requests.get", material_sources_api)
    sources = xivapi.fetch_material_sources()
    assert sources["gatherable"] == [101, 102, 103, 104]
    assert sources["timed"] == [101]
    assert sources["reducible"] == [102, 401]
    assert sources["reduction"] == [410]
    assert sources["gil"] == [101, 201]
    assert sources["special"] == [301, 302, 303, 304, 305, 306]
    assert sources["locked"] == [302]
    assert sources["gemstone"] == [304]
    assert sources["scrip"] == {"306": {"price": 200, "bundle": 1, "currency": 33913}}
    assert sources["currency"] == {"304": 26807, "305": 26807, "306": 33913}
    assert sources["prices"] == {"304": 3, "305": 3, "306": 200}


def test_fetch_currency_shop_collects_single_currency_trades(monkeypatch):
    monkeypatch.setattr("requests.get", material_sources_api)
    shop = xivapi.fetch_currency_shop()
    assert shop == {
        "26807": {"304": {"cost": 3, "amount": 1, "locked": False},
                  "305": {"cost": 3, "amount": 1, "locked": False}},
        "28": {"305": {"cost": 100, "amount": 1, "locked": False}},
        "33913": {"306": {"cost": 200, "amount": 1, "locked": False}},
    }


def test_currency_shop_is_cached(monkeypatch):
    monkeypatch.setattr("requests.get", material_sources_api)
    xivapi.fetch_currency_shop()

    def no_more_calls(*args, **kwargs):
        raise AssertionError("expected no api call")

    monkeypatch.setattr("requests.get", no_more_calls)
    xivapi.CURRENCY_SHOP.clear()
    assert xivapi.fetch_currency_shop()["28"]["305"]["cost"] == 100


def item_names_api(url, params=None, **kwargs):
    ids = params["rows"].split(",")
    return FakeResponse({"rows": [
        {"row_id": int(game_id), "fields": {"Name": f"Item {game_id}"}} for game_id in ids
    ]})


def test_fetch_item_names_batches_and_caches(monkeypatch):
    monkeypatch.setattr("requests.get", item_names_api)
    assert xivapi.fetch_item_names([5111, 16]) == {5111: "Item 5111", 16: "Item 16"}

    def no_more_calls(*args, **kwargs):
        raise AssertionError("expected no api call")

    monkeypatch.setattr("requests.get", no_more_calls)
    assert xivapi.fetch_item_names([5111, 16]) == {5111: "Item 5111", 16: "Item 16"}


def test_timed_items_need_all_their_nodes_timed(monkeypatch):
    monkeypatch.setitem(NODE_SHEET_PAGES, "GatheringPointBase", {"rows": [
        {"row_id": 500, "fields": {"Item@as(raw)": [11, 0]}},
        {"row_id": 501, "fields": {"Item@as(raw)": [12, 11]}},
    ]})
    monkeypatch.setattr("requests.get", material_sources_api)
    sources = xivapi.fetch_material_sources()
    assert sources["timed"] == []


def test_bases_without_gathering_points_do_not_vote_untimed(monkeypatch):
    monkeypatch.setitem(NODE_SHEET_PAGES, "GatheringPointBase", {"rows": [
        {"row_id": 500, "fields": {"Item@as(raw)": [11, 0]}},
        {"row_id": 502, "fields": {"Item@as(raw)": [11, 0]}},
    ]})
    monkeypatch.setattr("requests.get", material_sources_api)
    assert xivapi.fetch_material_sources()["timed"] == [101]


def vendor_api(url, params=None, **kwargs):
    if "ENpcResident" in url:
        return FakeResponse({"row_id": 1000236, "fields": {"Singular": "O'rhoyod"}})
    if "TerritoryType" in url:
        return FakeResponse({"fields": {
            "PlaceName": {"fields": {"Name": "Limsa Lominsa"}},
            "Aetheryte": {"row_id": 8, "fields": {"PlaceName": {"fields": {"Name": "Limsa Plaza"}}}},
            "Map": {"fields": {"SizeFactor": 100, "OffsetX": 0, "OffsetY": 0}},
        }})
    if "/Item/" in url:
        return FakeResponse({"fields": {"PriceMid": 108, "ItemSearchCategory@as(raw)": 53}})
    sheet = params["sheets"]
    if sheet == "GilShopItem":
        return FakeResponse({"results": [{"row_id": 262144, "subrow_id": 0, "fields": {}}]})
    if sheet == "SpecialShop":
        return FakeResponse({"results": []})
    if sheet == "ENpcBase":
        return FakeResponse({"results": [{"row_id": 1000236, "fields": {}}]})
    if sheet == "Level":
        return FakeResponse({"results": [{"row_id": 1, "fields": {"X": 0.0, "Z": 0.0, "Territory@as(raw)": 128}}]})
    raise AssertionError(sheet)


def test_fetch_item_offers_resolve_price_and_vendor(monkeypatch):
    monkeypatch.setattr("requests.get", vendor_api)
    monkeypatch.setattr("xivapi.closest_aetheryte", lambda *args: "Limsa Plaza")
    offers = xivapi.fetch_item_offers(4594)
    assert offers == [{
        "shop": None,
        "currency": 1,
        "price": 108,
        "vendor": {
            "name": "O'rhoyod",
            "zone": "Limsa Lominsa",
            "aetheryte": "Limsa Plaza",
            "x": 21.5,
            "y": 21.5,
        },
    }]

    def no_more_calls(*args, **kwargs):
        raise AssertionError("expected no api call")

    monkeypatch.setattr("requests.get", no_more_calls)
    assert xivapi.fetch_item_offers(4594)[0]["price"] == 108


def test_item_details_are_cached(monkeypatch):
    monkeypatch.setattr("requests.get", vendor_api)
    assert xivapi.fetch_item_details(46243) == {"price": 108, "marketable": True}

    def no_more_calls(*args, **kwargs):
        raise AssertionError("expected no api call")

    monkeypatch.setattr("requests.get", no_more_calls)
    assert xivapi.fetch_item_details(46243)["marketable"] is True


def test_distinct_offers_prefer_located_vendors():
    located = {"shop": None, "currency": 1, "price": 108, "vendor": {"name": "A"}}
    anonymous = {"shop": None, "currency": 1, "price": 108, "vendor": None}
    named_shop = {"shop": "Exchange", "currency": 2, "price": 5, "vendor": None}
    assert xivapi.distinct_offers([anonymous, located, named_shop]) == [located, named_shop]


def test_old_shape_cached_material_sources_are_refetched(monkeypatch):
    old = {"gatherable": [], "gil": [], "special": [], "locked": []}
    item_cache.store_result("all", old, "material_sources")
    monkeypatch.setattr("requests.get", material_sources_api)
    assert xivapi.fetch_material_sources()["timed"] == [101]


def test_fetch_material_sources_is_cached(monkeypatch):
    monkeypatch.setattr("requests.get", material_sources_api)
    xivapi.fetch_material_sources()
    assert item_cache.load_cache()["material_sources:all"]["type"] == "material_sources"

    def no_more_calls(*args, **kwargs):
        raise AssertionError("expected no api call")

    monkeypatch.setattr("requests.get", no_more_calls)
    xivapi.MATERIAL_SOURCES.clear()
    assert xivapi.fetch_material_sources()["locked"] == [302]


def test_old_shape_cached_craftables_are_refetched(monkeypatch):
    old_entry = {"game_id": 1, "name": "Old", "level": 100, "stars": 0, "jobs": [], "scrips": None}
    item_cache.store_result("en", [old_entry], "craftables")
    monkeypatch.setattr("requests.get", craftables_api)
    assert xivapi.fetch_craftables()[0]["ingredients"] == [
        {"name": "Beef Skirt Steak", "game_id": 44137, "amount": 2},
        {"name": "Fire Crystal", "game_id": 8, "amount": 1},
    ]


def test_missing_recipes_are_cached_and_not_looked_up_again(monkeypatch):
    monkeypatch.setattr("requests.get", fake_api)
    assert xivapi.fetch_recipe("Iron Ore") is None

    def no_more_calls(*args, **kwargs):
        raise AssertionError("expected no api call")

    monkeypatch.setattr("requests.get", no_more_calls)
    xivapi.RECIPES.clear()
    xivapi.CACHE.clear()
    assert xivapi.fetch_recipe("Iron Ore") is None


def test_failed_recipe_lookups_are_not_cached_as_missing(monkeypatch):
    def broken_api(*args, **kwargs):
        raise requests.ConnectionError("offline")

    monkeypatch.setattr("requests.get", broken_api)
    assert xivapi.fetch_recipe("Crested Headband") is None

    monkeypatch.setattr("requests.get", fake_api)
    xivapi.RECIPES.clear()
    xivapi.CACHE.clear()
    assert xivapi.fetch_recipe("Crested Headband") is not None


def test_old_shape_cached_recipe_is_refetched(monkeypatch):
    item_cache.store_result("crested headband", {"yields": 1, "ingredients": []}, "recipe")
    monkeypatch.setattr("requests.get", fake_api)
    assert xivapi.fetch_recipe("Crested Headband")["craft_types"] == ["Clothcraft", "Smithing"]


def test_crystal_with_one_gathering_job_is_refetched(monkeypatch):
    single = {"timed": False, "times": [], "zone": None, "aetheryte": None,
              "job_ids": [3], "x": None, "y": None}
    item_cache.store_result("16", single, "gathering")
    calls = []

    def counting_get(url, params=None, **kwargs):
        calls.append(url)
        return gathering_api(url, params, **kwargs)

    monkeypatch.setattr("requests.get", counting_get)
    xivapi.fetch_gathering(16)
    assert len(calls) > 0

    item_cache.store_result("43930", single, "gathering")
    calls.clear()
    xivapi.fetch_gathering(43930)
    assert calls == []


def test_crystals_skip_the_cached_node_shortcut(monkeypatch):
    node = {"base_id": 1029, "items": [16, 43930], "zone": "Somewhere",
            "aetheryte": None, "times": [], "job_id": 3, "x": 8.7, "y": 7.5}
    item_cache.store_result("1029", node, "node")
    monkeypatch.setattr("requests.get", gathering_api)
    assert xivapi.fetch_gathering(16)["job_ids"] == [3]

    def no_more_calls(*args, **kwargs):
        raise AssertionError("expected no api call")

    monkeypatch.setattr("requests.get", no_more_calls)
    xivapi.GATHERING.clear()
    assert xivapi.fetch_gathering(43930)["job_ids"] == [3]


def test_broken_cached_gathering_with_none_jobs_is_refetched(monkeypatch):
    broken = {"timed": False, "times": [], "zone": None, "aetheryte": None, "job_ids": None}
    item_cache.store_result("19", broken, "gathering")
    monkeypatch.setattr("requests.get", gathering_api)
    assert xivapi.fetch_gathering(19)["job_ids"] == [3]


def test_old_shape_cached_gathering_is_refetched(monkeypatch):
    old = {"timed": True, "times": [], "zone": "Somewhere", "aetheryte": None}
    item_cache.store_result("43930", old, "gathering")
    monkeypatch.setattr("requests.get", gathering_api)
    assert xivapi.fetch_gathering(43930)["job_ids"] == [3]


def test_fetch_recipe_for_uncraftable_item(monkeypatch):
    def no_recipe_api(url, params=None, **kwargs):
        if params and params.get("sheets") == "Recipe":
            return item_search_response([])
        return item_search_response(HEADBAND_SEARCH)

    monkeypatch.setattr("requests.get", no_recipe_api)
    assert xivapi.fetch_recipe("Crested Headband") is None
    assert item_cache.load_cache()["recipe:crested headband"]["result"] == {"no_recipe": True}
