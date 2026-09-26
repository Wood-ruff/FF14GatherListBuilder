import pytest

import lists

FAKE_GAME_IDS = {"iron ore": 5111}


@pytest.fixture(autouse=True)
def fake_xivapi(monkeypatch):
    monkeypatch.setattr("xivapi.fetch_item_id", lambda name: FAKE_GAME_IDS.get(name.lower()))


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
    lists.update_item("Ores", 1, "Iron Ore", 99)
    assert lists.get_items("Ores") == [
        {"id": 1, "name": "Iron Ore", "amount": 99, "game_id": 5111}
    ]


def test_update_item_rename_refreshes_game_id(tmp_path, monkeypatch):
    monkeypatch.setattr("storage.DATA_DIR", tmp_path)
    lists.add_item("Ores", "Copper Ore", 5)
    lists.update_item("Ores", 1, "Iron Ore", 5)
    assert lists.get_items("Ores") == [
        {"id": 1, "name": "Iron Ore", "amount": 5, "game_id": 5111}
    ]


def test_update_item_same_name_keeps_game_id_without_lookup(tmp_path, monkeypatch):
    monkeypatch.setattr("storage.DATA_DIR", tmp_path)
    lists.add_item("Ores", "Iron Ore", 20)
    calls = []
    monkeypatch.setattr("xivapi.fetch_item_id", lambda name: calls.append(name))
    lists.update_item("Ores", 1, "IRON ORE", 30)
    assert calls == []
    assert lists.get_items("Ores")[0]["game_id"] == 5111


def test_update_unknown_item_does_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr("storage.DATA_DIR", tmp_path)
    lists.add_item("Ores", "Iron Ore", 20)
    lists.update_item("Ores", 99, "Copper Ore", 5)
    assert lists.get_items("Ores")[0]["name"] == "Iron Ore"


def test_remove_item(tmp_path, monkeypatch):
    monkeypatch.setattr("storage.DATA_DIR", tmp_path)
    lists.add_item("Ores", "Iron Ore", 20)
    lists.add_item("Ores", "Copper Ore", 5)
    lists.remove_item("Ores", 1)
    items = lists.get_items("Ores")
    assert len(items) == 1
    assert items[0]["name"] == "Copper Ore"
