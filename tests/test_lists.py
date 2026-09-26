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


def test_valid_list_names():
    assert lists.is_valid_list_name("My List_1-a")
    assert lists.is_valid_list_name("a")


def test_invalid_list_names():
    assert not lists.is_valid_list_name("")
    assert not lists.is_valid_list_name("../evil")
    assert not lists.is_valid_list_name("name/with/slashes")
    assert not lists.is_valid_list_name("x" * 51)


def test_add_and_get_items(tmp_path, monkeypatch):
    monkeypatch.setattr("storage.DATA_DIR", tmp_path)
    lists.add_item("Ores", "Iron Ore", 20)
    lists.add_item("Ores", "Copper Ore", 5)
    assert lists.get_items("Ores") == [
        {"id": 1, "name": "Iron Ore", "amount": 20, "game_id": 5111},
        {"id": 2, "name": "Copper Ore", "amount": 5, "game_id": None},
    ]


def test_adding_same_item_sums_amounts(tmp_path, monkeypatch):
    monkeypatch.setattr("storage.DATA_DIR", tmp_path)
    lists.add_item("Ores", "Iron Ore", 20)
    lists.add_item("Ores", "Iron Ore", 5)
    assert lists.get_items("Ores") == [
        {"id": 1, "name": "Iron Ore", "amount": 25, "game_id": 5111}
    ]


def test_adding_same_item_ignores_case(tmp_path, monkeypatch):
    monkeypatch.setattr("storage.DATA_DIR", tmp_path)
    lists.add_item("Ores", "Iron Ore", 20)
    lists.add_item("Ores", "iron ore", 5)
    assert lists.get_items("Ores") == [
        {"id": 1, "name": "Iron Ore", "amount": 25, "game_id": 5111}
    ]


def test_spaces_are_normalized(tmp_path, monkeypatch):
    monkeypatch.setattr("storage.DATA_DIR", tmp_path)
    lists.add_item("  My   Ores ", "  Iron   Ore ", 20)
    lists.add_item("My Ores", "Iron Ore", 5)
    assert lists.get_list_names() == ["My Ores"]
    assert lists.get_items(" My   Ores  ") == [
        {"id": 1, "name": "Iron Ore", "amount": 25, "game_id": 5111}
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


def test_unknown_list_is_empty(tmp_path, monkeypatch):
    monkeypatch.setattr("storage.DATA_DIR", tmp_path)
    assert lists.get_items("DoesNotExist") == []


def test_update_item_changes_amount(tmp_path, monkeypatch):
    monkeypatch.setattr("storage.DATA_DIR", tmp_path)
    lists.add_item("Ores", "Iron Ore", 20)
    lists.update_item("Ores", 1, 99)
    assert lists.get_items("Ores") == [
        {"id": 1, "name": "Iron Ore", "amount": 99, "game_id": 5111}
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
        {"id": 1, "name": "Iron Ore", "amount": 20, "game_id": 5111}
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
        {"id": 1, "name": "Mystery Rock", "amount": 3, "game_id": None}
    ]


def test_remove_item(tmp_path, monkeypatch):
    monkeypatch.setattr("storage.DATA_DIR", tmp_path)
    lists.add_item("Ores", "Iron Ore", 20)
    lists.add_item("Ores", "Copper Ore", 5)
    lists.remove_item("Ores", 1)
    items = lists.get_items("Ores")
    assert len(items) == 1
    assert items[0]["name"] == "Copper Ore"
