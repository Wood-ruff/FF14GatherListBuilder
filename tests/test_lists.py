import pytest

import lists

FAKE_ITEMS = {"iron ore": {"row_id": 5111, "fields": {"Name": "Iron Ore"}}}


FAKE_RECIPES = {
    "crested headband": {
        "yields": 1,
        "ingredients": [
            {"name": "Diatryma Felt", "game_id": 45978, "amount": 2},
            {"name": "Wind Cluster", "game_id": 16, "amount": 3},
        ],
    },
    "diatryma felt": {
        "yields": 2,
        "ingredients": [
            {"name": "Iron Ore", "game_id": 5111, "amount": 4},
        ],
    },
}


@pytest.fixture(autouse=True)
def fake_xivapi(monkeypatch):
    monkeypatch.setattr("xivapi.fetch_item", lambda name: FAKE_ITEMS.get(name.lower()))
    monkeypatch.setattr("xivapi.fetch_recipe", lambda name: FAKE_RECIPES.get(name.lower()))
    monkeypatch.setattr("xivapi.fetch_gathering", lambda game_id: None)
    monkeypatch.setattr("xivapi.download_craft_icon", lambda icon_id: None)


def test_valid_list_names():
    assert lists.is_valid_list_name("My List_1-a")
    assert lists.is_valid_list_name("a")
    assert lists.is_valid_list_name("Kräuter für Montag")
    assert lists.is_valid_list_name("Léo's Liste")


def test_invalid_list_names():
    assert not lists.is_valid_list_name("")
    assert not lists.is_valid_list_name("../evil")
    assert not lists.is_valid_list_name("name/with/slashes")
    assert not lists.is_valid_list_name("name\\with\\backslashes")
    assert not lists.is_valid_list_name("dots.are.out")
    assert not lists.is_valid_list_name("x" * 51)


def test_add_and_get_items(tmp_path, monkeypatch):
    monkeypatch.setattr("storage.DATA_DIR", tmp_path)
    lists.add_item("Ores", "Iron Ore", 20)
    lists.add_item("Ores", "Copper Ore", 5)
    assert lists.get_items("Ores") == [
        {"id": 1, "name": "Iron Ore", "amount": 20, "game_id": 5111, "gathering": None},
        {"id": 2, "name": "Copper Ore", "amount": 5, "game_id": None, "gathering": None},
    ]


def test_adding_same_item_sums_amounts(tmp_path, monkeypatch):
    monkeypatch.setattr("storage.DATA_DIR", tmp_path)
    lists.add_item("Ores", "Iron Ore", 20)
    lists.add_item("Ores", "Iron Ore", 5)
    assert lists.get_items("Ores") == [
        {"id": 1, "name": "Iron Ore", "amount": 25, "game_id": 5111, "gathering": None}
    ]


def test_adding_same_item_ignores_case(tmp_path, monkeypatch):
    monkeypatch.setattr("storage.DATA_DIR", tmp_path)
    lists.add_item("Ores", "Iron Ore", 20)
    lists.add_item("Ores", "iron ore", 5)
    assert lists.get_items("Ores") == [
        {"id": 1, "name": "Iron Ore", "amount": 25, "game_id": 5111, "gathering": None}
    ]


def test_spaces_are_normalized(tmp_path, monkeypatch):
    monkeypatch.setattr("storage.DATA_DIR", tmp_path)
    lists.add_item("  My   Ores ", "  Iron   Ore ", 20)
    lists.add_item("My Ores", "Iron Ore", 5)
    assert lists.get_list_names() == ["My Ores"]
    assert lists.get_items(" My   Ores  ") == [
        {"id": 1, "name": "Iron Ore", "amount": 25, "game_id": 5111, "gathering": None}
    ]


def test_item_ids_stay_unique_and_increasing(tmp_path, monkeypatch):
    monkeypatch.setattr("storage.DATA_DIR", tmp_path)
    lists.add_item("Ores", "Iron Ore", 1)
    lists.add_item("Ores", "Copper Ore", 1)
    lists.add_item("Ores", "Iron Ore", 1)
    lists.add_item("Ores", "Maple Log", 1)
    ids = [item["id"] for item in lists.get_items("Ores")]
    assert ids == [1, 2, 3]


def test_invalid_list_name_is_ignored(tmp_path, monkeypatch):
    monkeypatch.setattr("storage.DATA_DIR", tmp_path)
    lists.add_item("../evil", "Iron Ore", 1)
    assert lists.get_list_names() == []
    assert lists.get_items("../evil") == []


def test_short_suggestion_queries_are_not_searched(monkeypatch):
    calls = []
    monkeypatch.setattr("xivapi.search_item_names", lambda text: calls.append(text))
    assert lists.suggest_item_names("ir") == []
    assert lists.suggest_item_names("  a ") == []
    assert calls == []


FAKE_COLLECTABLES = [
    {"game_id": 1, "name": "Beta", "level": 90, "stars": 1, "job": "Quarrying"},
    {"game_id": 2, "name": "Alpha", "level": 100, "stars": 0, "job": "Harvesting"},
    {"game_id": 3, "name": "Gamma", "level": 50, "stars": 0, "job": "Logging"},
]


def test_collectables_are_sorted(monkeypatch):
    monkeypatch.setattr("xivapi.fetch_collectables", lambda: FAKE_COLLECTABLES)
    assert lists.get_collectables("level")[0]["name"] == "Alpha"
    assert lists.get_collectables("stars")[0]["name"] == "Beta"
    assert lists.get_collectables("name")[0]["name"] == "Alpha"


def test_collectables_sort_direction_can_be_flipped(monkeypatch):
    monkeypatch.setattr("xivapi.fetch_collectables", lambda: FAKE_COLLECTABLES)
    assert lists.get_collectables("level", "asc")[0]["name"] == "Gamma"
    assert lists.get_collectables("name", "desc")[0]["name"] == "Gamma"


def test_collectables_job_filter_groups_by_class(monkeypatch):
    monkeypatch.setattr("xivapi.fetch_collectables", lambda: FAKE_COLLECTABLES)
    miner = lists.get_collectables(job="miner")
    botanist = lists.get_collectables(job="botanist")
    assert [c["name"] for c in miner] == ["Beta"]
    assert sorted(c["name"] for c in botanist) == ["Alpha", "Gamma"]


def test_collectables_level_filter(monkeypatch):
    monkeypatch.setattr("xivapi.fetch_collectables", lambda: FAKE_COLLECTABLES)
    kept = lists.get_collectables(min_level=60, max_level=95)
    assert [c["name"] for c in kept] == ["Beta"]


FAKE_CRAFTABLES = [
    {"game_id": 1, "name": "Tacos", "level": 100, "stars": 1, "jobs": ["Cooking"],
     "scrips": {"low": 12, "mid": 18, "high": 27}},
    {"game_id": 2, "name": "Lumber", "level": 80, "stars": 0, "jobs": ["Woodworking", "Smithing"],
     "scrips": None},
]


def test_craftables_scrip_filter_is_on_by_default(monkeypatch):
    monkeypatch.setattr("xivapi.fetch_craftables", lambda: FAKE_CRAFTABLES)
    assert [c["name"] for c in lists.get_craftables()] == ["Tacos"]
    assert len(lists.get_craftables(scrip_only=False)) == 2


def test_craftables_job_filter_uses_real_job_names(monkeypatch):
    monkeypatch.setattr("xivapi.fetch_craftables", lambda: FAKE_CRAFTABLES)
    kept = lists.get_craftables(job="blacksmith", scrip_only=False)
    assert [c["name"] for c in kept] == ["Lumber"]


def test_craft_types_are_mapped_to_job_names(monkeypatch):
    monkeypatch.setattr("xivapi.fetch_craftables", lambda: FAKE_CRAFTABLES)
    tacos = lists.get_craftables(scrip_only=True)[0]
    assert tacos["jobs"] == [{"name": "Culinarian", "icon_id": 62015}]


def test_craftables_level_filter(monkeypatch):
    monkeypatch.setattr("xivapi.fetch_craftables", lambda: FAKE_CRAFTABLES)
    kept = lists.get_craftables(min_level=90, scrip_only=False)
    assert [c["name"] for c in kept] == ["Tacos"]


def test_add_craft_with_materials_adds_both(tmp_path, monkeypatch):
    monkeypatch.setattr("storage.DATA_DIR", tmp_path)
    lists.add_craft_with_materials("Crafts", "Crested Headband", 1)
    names = {item["name"]: item["amount"] for item in lists.get_items("Crafts")}
    assert names == {"Crested Headband": 1, "Iron Ore": 4, "Wind Cluster": 3}


def test_add_craft_without_recipe_adds_item_once(tmp_path, monkeypatch):
    monkeypatch.setattr("storage.DATA_DIR", tmp_path)
    lists.add_craft_with_materials("Crafts", "Iron Ore", 5)
    names = {item["name"]: item["amount"] for item in lists.get_items("Crafts")}
    assert names == {"Iron Ore": 5}


def test_alarm_sounds_list_built_in_first_and_custom_last():
    sounds = lists.alarm_sounds()
    assert sounds[:3] == ["classic-beep.wav", "chime.wav", "buzzer.wav"]
    for custom in sounds[3:]:
        assert custom not in lists.BUILT_IN_ALARMS


def test_unknown_list_is_empty(tmp_path, monkeypatch):
    monkeypatch.setattr("storage.DATA_DIR", tmp_path)
    assert lists.get_items("DoesNotExist") == []


def test_update_item_changes_amount(tmp_path, monkeypatch):
    monkeypatch.setattr("storage.DATA_DIR", tmp_path)
    lists.add_item("Ores", "Iron Ore", 20)
    lists.update_item("Ores", 1, 99)
    assert lists.get_items("Ores") == [
        {"id": 1, "name": "Iron Ore", "amount": 99, "game_id": 5111, "gathering": None}
    ]


def test_update_unknown_item_does_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr("storage.DATA_DIR", tmp_path)
    lists.add_item("Ores", "Iron Ore", 20)
    lists.update_item("Ores", 99, 5)
    assert lists.get_items("Ores")[0]["amount"] == 20


def test_added_item_takes_name_from_api(tmp_path, monkeypatch):
    monkeypatch.setattr("storage.DATA_DIR", tmp_path)
    lists.add_item("Ores", "iRoN oRe", 20)
    assert lists.get_items("Ores") == [
        {"id": 1, "name": "Iron Ore", "amount": 20, "game_id": 5111, "gathering": None}
    ]


def test_craft_resolves_recipes_down_to_base_items(tmp_path, monkeypatch):
    monkeypatch.setattr("storage.DATA_DIR", tmp_path)
    lists.add_crafted_item("Gear", "Crested Headband", 1)
    items = {item["name"]: item["amount"] for item in lists.get_items("Gear")}
    assert items == {"Iron Ore": 4, "Wind Cluster": 3}


def test_craft_multiplies_by_requested_amount(tmp_path, monkeypatch):
    monkeypatch.setattr("storage.DATA_DIR", tmp_path)
    lists.add_crafted_item("Gear", "Crested Headband", 2)
    items = {item["name"]: item["amount"] for item in lists.get_items("Gear")}
    assert items == {"Iron Ore": 8, "Wind Cluster": 6}


def test_craft_respects_recipe_yield(tmp_path, monkeypatch):
    monkeypatch.setattr("storage.DATA_DIR", tmp_path)
    lists.add_crafted_item("Mats", "Diatryma Felt", 3)
    items = {item["name"]: item["amount"] for item in lists.get_items("Mats")}
    assert items == {"Iron Ore": 8}


def test_craft_without_recipe_adds_item_itself(tmp_path, monkeypatch):
    monkeypatch.setattr("storage.DATA_DIR", tmp_path)
    lists.add_crafted_item("Mats", "Iron Ore", 5)
    items = {item["name"]: item["amount"] for item in lists.get_items("Mats")}
    assert items == {"Iron Ore": 5}


def test_unknown_item_keeps_typed_name(tmp_path, monkeypatch):
    monkeypatch.setattr("storage.DATA_DIR", tmp_path)
    lists.add_item("Ores", "Mystery Rock", 3)
    assert lists.get_items("Ores") == [
        {"id": 1, "name": "Mystery Rock", "amount": 3, "game_id": None, "gathering": None}
    ]


def test_remove_item(tmp_path, monkeypatch):
    monkeypatch.setattr("storage.DATA_DIR", tmp_path)
    lists.add_item("Ores", "Iron Ore", 20)
    lists.add_item("Ores", "Copper Ore", 5)
    lists.remove_item("Ores", 1)
    items = lists.get_items("Ores")
    assert len(items) == 1
    assert items[0]["name"] == "Copper Ore"
