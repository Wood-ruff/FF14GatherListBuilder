import pytest

import lists

FAKE_ITEMS = {
    "iron ore": {"row_id": 5111, "fields": {"Name": "Iron Ore"}},
    "crested headband": {"row_id": 47184, "fields": {"Name": "Crested Headband"}},
    "wind cluster": {"row_id": 16, "fields": {"Name": "Wind Cluster"}},
}


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
    monkeypatch.setattr("xivapi.fetch_item_by_id", lambda game_id: None)
    monkeypatch.setattr("settings.get_language", lambda: "en")


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
        {"id": 1, "name": "Iron Ore", "amount": 20, "game_id": 5111, "gathering": None, "craftable": False, "done": False, "muted": False, "materials_added": False, "sticky": False, "language": "en", "crystal": False, "group": 1},
        {"id": 2, "name": "Copper Ore", "amount": 5, "game_id": None, "gathering": None, "craftable": False, "done": False, "muted": False, "materials_added": False, "sticky": False, "language": "en", "crystal": False, "group": 1},
    ]


def test_adding_same_item_sums_amounts(tmp_path, monkeypatch):
    monkeypatch.setattr("storage.DATA_DIR", tmp_path)
    lists.add_item("Ores", "Iron Ore", 20)
    lists.add_item("Ores", "Iron Ore", 5)
    assert lists.get_items("Ores") == [
        {"id": 1, "name": "Iron Ore", "amount": 25, "game_id": 5111, "gathering": None, "craftable": False, "done": False, "muted": False, "materials_added": False, "sticky": False, "language": "en", "crystal": False, "group": 1}
    ]


def test_adding_same_item_ignores_case(tmp_path, monkeypatch):
    monkeypatch.setattr("storage.DATA_DIR", tmp_path)
    lists.add_item("Ores", "Iron Ore", 20)
    lists.add_item("Ores", "iron ore", 5)
    assert lists.get_items("Ores") == [
        {"id": 1, "name": "Iron Ore", "amount": 25, "game_id": 5111, "gathering": None, "craftable": False, "done": False, "muted": False, "materials_added": False, "sticky": False, "language": "en", "crystal": False, "group": 1}
    ]


def test_spaces_are_normalized(tmp_path, monkeypatch):
    monkeypatch.setattr("storage.DATA_DIR", tmp_path)
    lists.add_item("  My   Ores ", "  Iron   Ore ", 20)
    lists.add_item("My Ores", "Iron Ore", 5)
    assert lists.get_list_names() == ["My Ores"]
    assert lists.get_items(" My   Ores  ") == [
        {"id": 1, "name": "Iron Ore", "amount": 25, "game_id": 5111, "gathering": None, "craftable": False, "done": False, "muted": False, "materials_added": False, "sticky": False, "language": "en", "crystal": False, "group": 1}
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


def test_paginate_slices_and_clamps():
    entries = list(range(60))
    page_entries, page, page_count = lists.paginate(entries, 2, 25)
    assert page_entries == list(range(25, 50))
    assert (page, page_count) == (2, 3)
    page_entries, page, page_count = lists.paginate(entries, 99, 25)
    assert page == 3
    assert page_entries == list(range(50, 60))
    page_entries, page, page_count = lists.paginate(entries, 0, 7)
    assert page == 1
    assert len(page_entries) == lists.DEFAULT_PAGE_SIZE


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
    assert len(lists.get_craftables(scrip_mode="all")) == 2


def test_craftables_job_filter_uses_real_job_names(monkeypatch):
    monkeypatch.setattr("xivapi.fetch_craftables", lambda: FAKE_CRAFTABLES)
    kept = lists.get_craftables(job="blacksmith", scrip_mode="all")
    assert [c["name"] for c in kept] == ["Lumber"]


def test_craft_types_are_mapped_to_job_names(monkeypatch):
    monkeypatch.setattr("xivapi.fetch_craftables", lambda: FAKE_CRAFTABLES)
    tacos = lists.get_craftables(scrip_mode="scrip")[0]
    assert tacos["jobs"] == [{"name": "Culinarian", "icon_id": 62015}]


def test_collectables_min_scrips_filter(monkeypatch):
    entries = [
        {"game_id": 1, "name": "Rich", "level": 100, "stars": 0, "job": "Mining",
         "scrips": {"low": 120, "mid": 134, "high": 144}},
        {"game_id": 2, "name": "Poor", "level": 100, "stars": 0, "job": "Mining",
         "scrips": {"low": 16, "mid": 23, "high": 38}},
        {"game_id": 3, "name": "NoScrips", "level": 100, "stars": 0, "job": "Mining",
         "scrips": None},
    ]
    monkeypatch.setattr("xivapi.fetch_collectables", lambda: entries)
    kept = lists.get_collectables(min_scrips=100)
    assert [c["name"] for c in kept] == ["Rich"]


def test_collectables_scrip_mode_filter(monkeypatch):
    entries = [
        {"game_id": 1, "name": "Rich", "level": 100, "stars": 0, "job": "Mining",
         "scrips": {"low": 120, "mid": 134, "high": 144}},
        {"game_id": 3, "name": "NoScrips", "level": 100, "stars": 0, "job": "Mining",
         "scrips": None},
    ]
    monkeypatch.setattr("xivapi.fetch_collectables", lambda: entries)
    assert len(lists.get_collectables(scrip_mode="all")) == 2
    assert [c["name"] for c in lists.get_collectables(scrip_mode="scrip")] == ["Rich"]
    assert [c["name"] for c in lists.get_collectables(scrip_mode="noscrip")] == ["NoScrips"]


def test_craftables_min_scrips_filter(monkeypatch):
    monkeypatch.setattr("xivapi.fetch_craftables", lambda: FAKE_CRAFTABLES)
    kept = lists.get_craftables(min_scrips=20, scrip_mode="all")
    assert kept == []
    kept = lists.get_craftables(min_scrips=10, scrip_mode="all")
    assert [c["name"] for c in kept] == ["Tacos"]


def test_name_filter_matches_substrings(monkeypatch):
    monkeypatch.setattr("xivapi.fetch_craftables", lambda: FAKE_CRAFTABLES)
    kept = lists.get_craftables(name_filter="umb", scrip_mode="all")
    assert [c["name"] for c in kept] == ["Lumber"]
    assert lists.get_craftables(name_filter="TACOS", scrip_mode="all")[0]["name"] == "Tacos"


def test_craftables_no_scrip_mode(monkeypatch):
    monkeypatch.setattr("xivapi.fetch_craftables", lambda: FAKE_CRAFTABLES)
    kept = lists.get_craftables(scrip_mode="noscrip")
    assert [c["name"] for c in kept] == ["Lumber"]


def test_craftables_level_filter(monkeypatch):
    monkeypatch.setattr("xivapi.fetch_craftables", lambda: FAKE_CRAFTABLES)
    kept = lists.get_craftables(min_level=90, scrip_mode="all")
    assert [c["name"] for c in kept] == ["Tacos"]


def test_add_craft_with_materials_adds_both(tmp_path, monkeypatch):
    monkeypatch.setattr("storage.DATA_DIR", tmp_path)
    lists.add_craft_with_materials("Crafts", "Crested Headband", 1)
    names = {item["name"]: item["amount"] for item in lists.get_items("Crafts")}
    assert names == {"Crested Headband": 1, "Iron Ore": 4, "Wind Cluster": 3}


def test_craftable_items_are_listed_first(tmp_path, monkeypatch):
    monkeypatch.setattr("storage.DATA_DIR", tmp_path)
    lists.add_item("Mix", "Iron Ore", 1)
    lists.add_item("Mix", "Crested Headband", 1)
    lists.add_item("Mix", "Copper Ore", 1)
    names = [item["name"] for item in lists.get_items("Mix")]
    assert names == ["Crested Headband", "Iron Ore", "Copper Ore"]


def test_set_done_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr("storage.DATA_DIR", tmp_path)
    lists.add_item("Mats", "Iron Ore", 5)
    lists.set_done("Mats", 1, True)
    assert lists.get_items("Mats")[0]["done"] is True
    lists.set_done("Mats", 1, False)
    assert lists.get_items("Mats")[0]["done"] is False


def test_adding_materials_marks_the_item(tmp_path, monkeypatch):
    monkeypatch.setattr("storage.DATA_DIR", tmp_path)
    lists.add_item("Crafts", "Crested Headband", 1)
    assert lists.get_items("Crafts")[0]["materials_added"] is False
    lists.add_materials_for("Crafts", 1)
    assert lists.get_items("Crafts")[0]["materials_added"] is True


def test_craft_with_materials_marks_the_item(tmp_path, monkeypatch):
    monkeypatch.setattr("storage.DATA_DIR", tmp_path)
    lists.add_craft_with_materials("Crafts", "Crested Headband", 1)
    headband = [item for item in lists.get_items("Crafts") if item["name"] == "Crested Headband"][0]
    assert headband["materials_added"] is True


def test_add_all_materials_covers_unmarked_craftables_only(tmp_path, monkeypatch):
    monkeypatch.setattr("storage.DATA_DIR", tmp_path)
    lists.add_item("Crafts", "Crested Headband", 1)
    lists.add_item("Crafts", "Copper Ore", 3)

    lists.add_all_materials("Crafts")
    items = lists.get_items("Crafts")
    assert lists.find_item(items, "Iron Ore")["amount"] == 4
    assert lists.find_item(items, "Wind Cluster")["amount"] == 3
    assert lists.find_item(items, "Crested Headband")["materials_added"] is True

    lists.add_all_materials("Crafts")
    assert lists.find_item(lists.get_items("Crafts"), "Iron Ore")["amount"] == 4


def test_remove_materials_keeps_craftables_and_resets_markers(tmp_path, monkeypatch):
    monkeypatch.setattr("storage.DATA_DIR", tmp_path)
    lists.add_item("Crafts", "Crested Headband", 1)
    lists.add_materials_for("Crafts", 1)
    lists.add_item("Crafts", "Copper Ore", 3)
    assert lists.get_items("Crafts")[0]["materials_added"] is True

    lists.remove_materials("Crafts")
    items = lists.get_items("Crafts")
    assert [item["name"] for item in items] == ["Crested Headband"]
    assert items[0]["materials_added"] is False


def test_set_muted_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr("storage.DATA_DIR", tmp_path)
    lists.add_item("Mats", "Iron Ore", 5)
    lists.set_muted("Mats", 1, True)
    assert lists.get_items("Mats")[0]["muted"] is True
    lists.set_muted("Mats", 1, False)
    assert lists.get_items("Mats")[0]["muted"] is False


def test_crystals_are_listed_last(tmp_path, monkeypatch):
    monkeypatch.setattr("storage.DATA_DIR", tmp_path)
    lists.add_item("Mix", "Wind Cluster", 3)
    lists.add_item("Mix", "Iron Ore", 1)
    lists.add_item("Mix", "Crested Headband", 1)
    names = [item["name"] for item in lists.get_items("Mix")]
    assert names == ["Crested Headband", "Iron Ore", "Wind Cluster"]


def test_add_materials_for_list_item(tmp_path, monkeypatch):
    monkeypatch.setattr("storage.DATA_DIR", tmp_path)
    lists.add_item("Crafts", "Crested Headband", 2)
    lists.add_materials_for("Crafts", 1)
    names = {item["name"]: item["amount"] for item in lists.get_items("Crafts")}
    assert names == {"Crested Headband": 2, "Iron Ore": 8, "Wind Cluster": 6}


def test_add_materials_for_uncraftable_item_does_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr("storage.DATA_DIR", tmp_path)
    lists.add_item("Mats", "Iron Ore", 5)
    lists.add_materials_for("Mats", 1)
    names = {item["name"]: item["amount"] for item in lists.get_items("Mats")}
    assert names == {"Iron Ore": 5}


def test_add_materials_for_unknown_id_does_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr("storage.DATA_DIR", tmp_path)
    lists.add_item("Mats", "Iron Ore", 5)
    lists.add_materials_for("Mats", 99)
    assert len(lists.get_items("Mats")) == 1


def test_add_craft_without_recipe_adds_item_once(tmp_path, monkeypatch):
    monkeypatch.setattr("storage.DATA_DIR", tmp_path)
    lists.add_craft_with_materials("Crafts", "Iron Ore", 5)
    names = {item["name"]: item["amount"] for item in lists.get_items("Crafts")}
    assert names == {"Iron Ore": 5}


def test_import_list_sanitizes_and_keeps_settings(tmp_path, monkeypatch):
    monkeypatch.setattr("storage.DATA_DIR", tmp_path)
    raw = [
        {"name": "Iron Ore", "amount": 5, "done": True, "muted": 1, "evil": "field", "game_id": "x"},
        {"name": "", "amount": 5},
        {"amount": 5},
        "junk",
        {"name": "Bay Leaf", "amount": -2},
    ]
    name = lists.import_list("Shared", raw)
    assert name == "Shared"
    items = lists.get_items("Shared")
    assert len(items) == 1
    assert items[0]["name"] == "Iron Ore"
    assert items[0]["done"] is True
    assert items[0]["muted"] is True
    assert items[0]["game_id"] is None
    assert "evil" not in items[0]


def test_import_list_finds_a_free_name(tmp_path, monkeypatch):
    monkeypatch.setattr("storage.DATA_DIR", tmp_path)
    lists.create_list("Shared")
    name = lists.import_list("Shared", [{"name": "Iron Ore", "amount": 1}])
    assert name == "Shared 2"


def test_refresh_list_data_fills_game_data(tmp_path, monkeypatch):
    monkeypatch.setattr("storage.DATA_DIR", tmp_path)
    lists.import_list("Shared", [{"name": "iron ore", "amount": 5, "done": True}])
    lists.refresh_list_data("Shared")
    item = lists.get_items("Shared")[0]
    assert item["name"] == "Iron Ore"
    assert item["game_id"] == 5111
    assert item["done"] is True


def test_localize_list_switches_names_by_id(tmp_path, monkeypatch):
    monkeypatch.setattr("storage.DATA_DIR", tmp_path)
    lists.add_item("Erze", "Iron Ore", 5)
    assert not lists.needs_localization(lists.get_items("Erze"))

    monkeypatch.setattr("settings.get_language", lambda: "de")
    items = lists.get_items("Erze")
    assert lists.needs_localization(items)

    german = {"row_id": 5111, "fields": {"Name": "Eisenerz"}}
    monkeypatch.setattr("xivapi.fetch_item_by_id", lambda game_id: german)
    lists.localize_list("Erze")
    item = lists.get_items("Erze")[0]
    assert item["name"] == "Eisenerz"
    assert item["language"] == "de"
    assert not lists.needs_localization(lists.get_items("Erze"))


def test_refresh_prefers_the_id_lookup_for_localization(tmp_path, monkeypatch):
    monkeypatch.setattr("storage.DATA_DIR", tmp_path)
    lists.import_list("Shared", [{"name": "Iron Ore", "amount": 5, "game_id": 5111}])
    german = {"row_id": 5111, "fields": {"Name": "Eisenerz"}}
    monkeypatch.setattr("xivapi.fetch_item_by_id", lambda game_id: german)
    lists.refresh_list_data("Shared")
    item = lists.get_items("Shared")[0]
    assert item["name"] == "Eisenerz"
    assert item["game_id"] == 5111


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
        {"id": 1, "name": "Iron Ore", "amount": 99, "game_id": 5111, "gathering": None, "craftable": False, "done": False, "muted": False, "materials_added": False, "sticky": False, "language": "en", "crystal": False, "group": 1}
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
        {"id": 1, "name": "Iron Ore", "amount": 20, "game_id": 5111, "gathering": None, "craftable": False, "done": False, "muted": False, "materials_added": False, "sticky": False, "language": "en", "crystal": False, "group": 1}
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
        {"id": 1, "name": "Mystery Rock", "amount": 3, "game_id": None, "gathering": None, "craftable": False, "done": False, "muted": False, "materials_added": False, "sticky": False, "language": "en", "crystal": False, "group": 1}
    ]


def test_remove_item(tmp_path, monkeypatch):
    monkeypatch.setattr("storage.DATA_DIR", tmp_path)
    lists.add_item("Ores", "Iron Ore", 20)
    lists.add_item("Ores", "Copper Ore", 5)
    lists.remove_item("Ores", 1)
    items = lists.get_items("Ores")
    assert len(items) == 1
    assert items[0]["name"] == "Copper Ore"
