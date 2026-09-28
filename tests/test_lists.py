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
    monkeypatch.setattr("xivapi.warm_recipes", lambda ingredients: None)
    monkeypatch.setattr("xivapi.warm_items", lambda game_ids: None)
    monkeypatch.setattr("xivapi.warm_icons", lambda game_ids: None)
    monkeypatch.setattr("xivapi.warm_gathering", lambda game_ids: None)
    monkeypatch.setattr("xivapi.warm_item_details", lambda game_ids: None)
    monkeypatch.setattr("xivapi.fetch_gathering", lambda game_id: None)
    monkeypatch.setattr("xivapi.download_craft_icon", lambda icon_id: None)
    monkeypatch.setattr("xivapi.ensure_job_type_icon", lambda type_id: None)
    monkeypatch.setattr("xivapi.fetch_item_by_id", lambda game_id: None)
    monkeypatch.setattr("xivapi.fetch_material_sources", lambda: None)
    monkeypatch.setattr("xivapi.fetch_item_offers", lambda game_id: [])
    monkeypatch.setattr("xivapi.fetch_item_details", lambda game_id: None)
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
        {"id": 1, "name": "Iron Ore", "amount": 20, "game_id": 5111, "gathering": None, "craftable": False, "done": False, "muted": False, "materials_added": False, "sticky": False, "note": "", "job_icons": [], "marketable": None, "language": "en", "crystal": False, "group": 1},
        {"id": 2, "name": "Copper Ore", "amount": 5, "game_id": None, "gathering": None, "craftable": False, "done": False, "muted": False, "materials_added": False, "sticky": False, "note": "", "job_icons": [], "marketable": None, "language": "en", "crystal": False, "group": 1},
    ]


def test_adding_same_item_sums_amounts(tmp_path, monkeypatch):
    monkeypatch.setattr("storage.DATA_DIR", tmp_path)
    lists.add_item("Ores", "Iron Ore", 20)
    lists.add_item("Ores", "Iron Ore", 5)
    assert lists.get_items("Ores") == [
        {"id": 1, "name": "Iron Ore", "amount": 25, "game_id": 5111, "gathering": None, "craftable": False, "done": False, "muted": False, "materials_added": False, "sticky": False, "note": "", "job_icons": [], "marketable": None, "language": "en", "crystal": False, "group": 1}
    ]


def test_adding_same_item_ignores_case(tmp_path, monkeypatch):
    monkeypatch.setattr("storage.DATA_DIR", tmp_path)
    lists.add_item("Ores", "Iron Ore", 20)
    lists.add_item("Ores", "iron ore", 5)
    assert lists.get_items("Ores") == [
        {"id": 1, "name": "Iron Ore", "amount": 25, "game_id": 5111, "gathering": None, "craftable": False, "done": False, "muted": False, "materials_added": False, "sticky": False, "note": "", "job_icons": [], "marketable": None, "language": "en", "crystal": False, "group": 1}
    ]


def test_spaces_are_normalized(tmp_path, monkeypatch):
    monkeypatch.setattr("storage.DATA_DIR", tmp_path)
    lists.add_item("  My   Ores ", "  Iron   Ore ", 20)
    lists.add_item("My Ores", "Iron Ore", 5)
    assert lists.get_list_names() == ["My Ores"]
    assert lists.get_items(" My   Ores  ") == [
        {"id": 1, "name": "Iron Ore", "amount": 25, "game_id": 5111, "gathering": None, "craftable": False, "done": False, "muted": False, "materials_added": False, "sticky": False, "note": "", "job_icons": [], "marketable": None, "language": "en", "crystal": False, "group": 1}
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


def test_crafted_item_gets_the_crafter_symbols(tmp_path, monkeypatch):
    monkeypatch.setattr("storage.DATA_DIR", tmp_path)
    recipe = dict(FAKE_RECIPES["crested headband"], craft_types=["Clothcraft", "Smithing"])
    monkeypatch.setattr("xivapi.fetch_recipe", lambda name: recipe if "headband" in name.lower() else None)
    lists.add_item("Gear", "Crested Headband", 1)
    assert lists.get_items("Gear")[0]["job_icons"] == [
        {"type": "craft", "icon": 62013},
        {"type": "craft", "icon": 62009},
    ]


def test_gathered_item_gets_the_gatherer_symbols(tmp_path, monkeypatch):
    monkeypatch.setattr("storage.DATA_DIR", tmp_path)
    gathering = {"timed": False, "times": [], "zone": None, "aetheryte": None, "job_ids": [0, 3]}
    monkeypatch.setattr("xivapi.fetch_gathering", lambda game_id: gathering)
    lists.add_item("Ores", "Iron Ore", 1)
    assert lists.get_items("Ores")[0]["job_icons"] == [
        {"type": "gather", "icon": 0},
        {"type": "gather", "icon": 3},
    ]


def test_set_note_round_trip_and_cap(tmp_path, monkeypatch):
    monkeypatch.setattr("storage.DATA_DIR", tmp_path)
    lists.add_item("Mats", "Iron Ore", 5)
    lists.set_note("Mats", 1, "north camp first")
    assert lists.get_items("Mats")[0]["note"] == "north camp first"
    lists.set_note("Mats", 1, "x" * 300)
    assert len(lists.get_items("Mats")[0]["note"]) == 200


def test_set_muted_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr("storage.DATA_DIR", tmp_path)
    lists.add_item("Mats", "Iron Ore", 5)
    lists.set_muted("Mats", 1, True)
    assert lists.get_items("Mats")[0]["muted"] is True
    lists.set_muted("Mats", 1, False)
    assert lists.get_items("Mats")[0]["muted"] is False


def test_timed_first_sorting(tmp_path, monkeypatch):
    monkeypatch.setattr("storage.DATA_DIR", tmp_path)
    timed = {"timed": True, "times": [{"start": 600, "duration": 120}], "zone": None, "aetheryte": None}
    lists.add_item("Mix", "Crested Headband", 1)
    lists.add_item("Mix", "Copper Ore", 1)
    monkeypatch.setattr("xivapi.fetch_gathering", lambda game_id: timed)
    lists.add_item("Mix", "Iron Ore", 1)

    names = [item["name"] for item in lists.get_items("Mix")]
    assert names == ["Crested Headband", "Copper Ore", "Iron Ore"]

    names = [item["name"] for item in lists.get_items("Mix", timed_first=True)]
    assert names == ["Iron Ore", "Crested Headband", "Copper Ore"]


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


def test_item_model_matches_new_items(tmp_path, monkeypatch):
    monkeypatch.setattr("storage.DATA_DIR", tmp_path)
    lists.add_item("Model", "Iron Ore", 1)
    item = lists.get_items("Model")[0]
    display_only = {"id", "group", "crystal"}
    assert set(item.keys()) - display_only == set(lists.load_item_model().keys())


def test_items_with_old_gathering_shape_need_data():
    old_shape = {
        "game_id": 43930,
        "job_icons": [{"type": "gather", "icon": 3}],
        "marketable": False,
        "gathering": {"timed": True, "times": [], "zone": "Somewhere", "aetheryte": None},
    }
    new_shape = dict(old_shape, gathering=dict(old_shape["gathering"], x=8.7, y=7.5))
    assert lists.item_needs_data(old_shape)
    assert not lists.item_needs_data(new_shape)


def test_crystals_need_data_until_both_jobs_are_known():
    one_job = {"game_id": 16, "job_icons": [{"type": "gather", "icon": 3}], "marketable": True}
    both_jobs = {"game_id": 16, "job_icons": [{"type": "gather", "icon": 0}, {"type": "gather", "icon": 3}], "marketable": True}
    plain = {"game_id": 5111, "job_icons": [{"type": "gather", "icon": 0}], "marketable": True}
    assert lists.item_needs_data(one_job)
    assert not lists.item_needs_data(both_jobs)
    assert not lists.item_needs_data(plain)


def test_migrate_lists_fills_missing_fields(tmp_path, monkeypatch):
    import json

    monkeypatch.setattr("storage.DATA_DIR", tmp_path)
    legacy = [{"id": 1, "name": "Iron Ore", "amount": 5, "game_id": 5111}]
    (tmp_path / "Old.json").write_text(json.dumps(legacy), encoding="utf-8")

    assert lists.migrate_lists() == ["Old"]
    item = lists.get_items("Old")[0]
    assert item["done"] is False
    assert item["note"] == ""
    assert item["job_icons"] == []
    assert item["amount"] == 5

    assert lists.migrate_lists() == ["Old"]

    lists.set_item_flag("Old", 1, "job_icons", [{"type": "gather", "icon": 0}])
    assert lists.migrate_lists() == ["Old"]

    lists.set_item_flag("Old", 1, "marketable", True)
    assert lists.migrate_lists() == []


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


ROTATION_ENTRIES = [
    {"game_id": 1, "name": "Purple Leaf", "level": 95, "job": "Harvesting", "timed": True,
     "scrips": {"low": 16, "mid": 23, "high": 38}, "times": [{"start": 600, "duration": 120}]},
    {"game_id": 2, "name": "Orange Ore", "level": 100, "job": "Mining", "timed": True,
     "scrips": {"low": 120, "mid": 134, "high": 144}, "times": [{"start": 0, "duration": 120}]},
    {"game_id": 3, "name": "Untimed Sand", "level": 100, "job": "Mining", "timed": False,
     "scrips": {"low": 120, "mid": 134, "high": 144}, "times": []},
    {"game_id": 4, "name": "No Scrips", "level": 100, "job": "Mining", "timed": True,
     "scrips": None, "times": [{"start": 0, "duration": 120}]},
]


def test_rotation_filters_by_scrip_tier_level_and_jobs(monkeypatch):
    monkeypatch.setattr("xivapi.fetch_collectables", lambda: ROTATION_ENTRIES)
    purple = lists.get_rotation(100, ["miner", "botanist"], False)
    assert [entry["name"] for entry in purple] == ["Purple Leaf"]

    orange = lists.get_rotation(100, ["miner", "botanist"], True)
    assert [entry["name"] for entry in orange] == ["Orange Ore"]

    assert lists.get_rotation(90, ["botanist"], False) == []
    assert lists.get_rotation(100, ["botanist"], True) == []


COST_CRAFTABLES = [
    {"game_id": 1, "name": "One Type", "level": 100, "stars": 1, "jobs": ["Cooking"],
     "scrips": {"low": 20, "mid": 35, "high": 50}, "yields": 1,
     "ingredients": [{"name": "Meat", "game_id": 100, "amount": 100}]},
    {"game_id": 2, "name": "Five Types", "level": 100, "stars": 1, "jobs": ["Woodworking"],
     "scrips": {"low": 20, "mid": 35, "high": 50}, "yields": 1,
     "ingredients": [{"name": f"Mat {n}", "game_id": 100 + n, "amount": 20} for n in range(1, 6)]},
    {"game_id": 3, "name": "Purple Craft", "level": 90, "stars": 0, "jobs": ["Smithing"],
     "scrips": {"low": 10, "mid": 15, "high": 20}, "yields": 1,
     "ingredients": [{"name": "Ore", "game_id": 200, "amount": 4},
                     {"name": "Fire Crystal", "game_id": 8, "amount": 8}]},
    {"game_id": 4, "name": "No Recipe Data", "level": 100, "stars": 0, "jobs": ["Alchemy"],
     "scrips": {"low": 20, "mid": 35, "high": 50}},
    {"game_id": 5, "name": "No Scrips", "level": 100, "stars": 0, "jobs": ["Alchemy"],
     "scrips": None, "yields": 1,
     "ingredients": [{"name": "Herb", "game_id": 300, "amount": 1}]},
]


def test_craft_costs_prefer_fewer_unique_materials(monkeypatch):
    monkeypatch.setattr("xivapi.fetch_craftables", lambda: COST_CRAFTABLES)
    entries = lists.get_craft_costs(100, "all", True)
    assert [entry["name"] for entry in entries] == ["One Type", "Five Types"]
    assert entries[0]["cost"] == 110
    assert entries[1]["cost"] == 150
    assert entries[0]["score"] == 2.2
    assert entries[0]["unique_materials"] == 1
    assert entries[1]["unique_materials"] == 5
    assert entries[0]["total_materials"] == entries[1]["total_materials"] == 100


def test_craft_costs_weigh_crystals_low_and_skip_incomplete_entries(monkeypatch):
    monkeypatch.setattr("xivapi.fetch_craftables", lambda: COST_CRAFTABLES)
    entries = lists.get_craft_costs(100, "all", False)
    assert [entry["name"] for entry in entries] == ["Purple Craft"]
    assert entries[0]["cost"] == 16
    assert entries[0]["unique_materials"] == 1
    assert entries[0]["materials"][1]["source"] == "crystal"


def source_craftable(game_id, name, mat_id):
    return {"game_id": game_id, "name": name, "level": 100, "stars": 0, "jobs": ["Cooking"],
            "scrips": {"low": 20, "mid": 35, "high": 50}, "yields": 1,
            "ingredients": [{"name": name + " Mat", "game_id": mat_id, "amount": 10}]}


def fake_sources(**overrides):
    sources = {"gatherable": [], "timed": [], "gil": [], "special": [], "locked": [],
               "gemstone": [], "reducible": [], "reduction": [],
               "scrip": {}, "currency": {}, "prices": {}}
    sources.update(overrides)
    return sources


def test_craft_costs_weigh_and_mark_material_sources(monkeypatch):
    craftables = [
        source_craftable(1, "Gathered", 100),
        source_craftable(2, "Looted", 101),
        source_craftable(3, "Bought", 102),
        source_craftable(4, "Traded", 103),
        source_craftable(5, "Locked Trade", 104),
    ]
    sources = fake_sources(gatherable=[100], gil=[102], special=[103, 104], locked=[104])
    monkeypatch.setattr("xivapi.fetch_craftables", lambda: craftables)
    monkeypatch.setattr("xivapi.fetch_material_sources", lambda: sources)
    entries = lists.get_craft_costs(100, "all", True)
    assert [(e["name"], e["cost"]) for e in entries] == [
        ("Traded", 15), ("Bought", 15), ("Gathered", 20), ("Locked Trade", 70), ("Looted", 90),
    ]
    flags = {e["name"]: (e["has_loot"], e["has_locked"]) for e in entries}
    assert flags == {"Gathered": (False, False), "Looted": (True, False),
                     "Bought": (False, False), "Traded": (False, False),
                     "Locked Trade": (False, True)}
    by_name = {e["name"]: e["materials"][0] for e in entries}
    assert by_name["Looted"]["source"] == "loot"
    assert by_name["Bought"]["source"] == "gil"
    assert by_name["Traded"]["locked"] is False
    assert by_name["Locked Trade"]["locked"] is True


def test_craft_costs_expand_crafted_intermediates_to_base_materials(monkeypatch):
    craftable = dict(source_craftable(1, "Hat", 45978),
                     ingredients=[{"name": "Diatryma Felt", "game_id": 45978, "amount": 3}])
    sources = fake_sources(gatherable=[5111])
    monkeypatch.setattr("xivapi.fetch_craftables", lambda: [craftable])
    monkeypatch.setattr("xivapi.fetch_material_sources", lambda: sources)
    entry = lists.get_craft_costs(100, "all", True)[0]
    assert entry["materials"] == [
        {"name": "Iron Ore", "game_id": 5111, "amount": 8, "source": "gather",
         "locked": False, "timed": False, "scrip": None, "currency": None}
    ]
    assert entry["has_loot"] is False
    assert entry["cost"] == 18


def test_craft_costs_treat_gemstone_items_like_loot(monkeypatch):
    craftables = [source_craftable(1, "Hide Craft", 100), source_craftable(2, "Token Craft", 101)]
    sources = fake_sources(special=[100, 101], gemstone=[100])
    monkeypatch.setattr("xivapi.fetch_craftables", lambda: craftables)
    monkeypatch.setattr("xivapi.fetch_material_sources", lambda: sources)
    entries = lists.get_craft_costs(100, "all", True)
    assert [(e["name"], e["cost"]) for e in entries] == [("Token Craft", 15), ("Hide Craft", 90)]
    assert entries[1]["materials"][0]["source"] == "gemstone"
    assert entries[1]["has_loot"] is True
    assert entries[0]["has_loot"] is False


def test_craft_costs_gemstone_toggle_makes_them_cheap(monkeypatch):
    craftables = [source_craftable(1, "Hide Craft", 100)]
    sources = fake_sources(special=[100], gemstone=[100])
    monkeypatch.setattr("xivapi.fetch_craftables", lambda: craftables)
    monkeypatch.setattr("xivapi.fetch_material_sources", lambda: sources)
    entry = lists.get_craft_costs(100, "all", True, gemstones_unlocked=True)[0]
    assert entry["cost"] == 15
    assert entry["has_loot"] is False
    assert entry["materials"][0]["source"] == "gemstone"


def test_craft_costs_raise_effort_for_timed_nodes(monkeypatch):
    craftables = [source_craftable(1, "Timed", 100), source_craftable(2, "Untimed", 101)]
    sources = fake_sources(gatherable=[100, 101], timed=[100])
    monkeypatch.setattr("xivapi.fetch_craftables", lambda: craftables)
    monkeypatch.setattr("xivapi.fetch_material_sources", lambda: sources)
    entries = lists.get_craft_costs(100, "all", True)
    assert [(e["name"], e["cost"]) for e in entries] == [("Untimed", 20), ("Timed", 30)]
    assert entries[1]["materials"][0]["timed"] is True
    assert entries[0]["materials"][0]["timed"] is False


def test_craft_costs_subtract_scrips_paid_for_materials(monkeypatch):
    craftables = [source_craftable(1, "Scrip Craft", 100)]
    sources = fake_sources(special=[100], scrip={"100": {"price": 2, "bundle": 1, "currency": 33913}})
    monkeypatch.setattr("xivapi.fetch_craftables", lambda: craftables)
    monkeypatch.setattr("xivapi.fetch_material_sources", lambda: sources)
    entry = lists.get_craft_costs(100, "all", True)[0]
    assert entry["scrips"] == 50
    assert entry["scrip_paid"] == 20
    assert entry["net_scrips"] == 30
    assert entry["cost"] == 15
    assert entry["score"] == 0.5
    assert entry["materials"][0]["source"] == "scrip"
    assert entry["materials"][0]["currency"] == 33913


def test_craft_costs_skip_recipes_that_pay_more_scrips_than_they_yield(monkeypatch):
    craftables = [source_craftable(1, "Bad Deal", 100)]
    sources = fake_sources(special=[100], scrip={"100": {"price": 5, "bundle": 1, "currency": 33913}})
    monkeypatch.setattr("xivapi.fetch_craftables", lambda: craftables)
    monkeypatch.setattr("xivapi.fetch_material_sources", lambda: sources)
    assert lists.get_craft_costs(100, "all", True) == []


def test_craft_costs_scrip_bundles_are_paid_whole(monkeypatch):
    craftables = [source_craftable(1, "Bundle Craft", 100)]
    sources = fake_sources(special=[100], scrip={"100": {"price": 9, "bundle": 3, "currency": 33913}})
    monkeypatch.setattr("xivapi.fetch_craftables", lambda: craftables)
    monkeypatch.setattr("xivapi.fetch_material_sources", lambda: sources)
    entry = lists.get_craft_costs(100, "all", True)[0]
    assert entry["scrip_paid"] == 36
    assert entry["net_scrips"] == 14


def test_craft_costs_hide_filters_drop_unobtainable_recipes(monkeypatch):
    craftables = [
        source_craftable(1, "Gathered", 100),
        source_craftable(2, "Looted", 101),
        source_craftable(3, "Locked Trade", 102),
        source_craftable(4, "Gemstone", 103),
    ]
    sources = fake_sources(gatherable=[100], special=[102, 103], locked=[102], gemstone=[103])
    monkeypatch.setattr("xivapi.fetch_craftables", lambda: craftables)
    monkeypatch.setattr("xivapi.fetch_material_sources", lambda: sources)

    def names(**kwargs):
        return sorted(e["name"] for e in lists.get_craft_costs(100, "all", True, **kwargs))

    assert names(hide_loot=True) == ["Gathered", "Gemstone", "Locked Trade"]
    assert names(hide_locked=True) == ["Gathered", "Gemstone", "Looted"]
    assert names(hide_loot=True, hide_locked=True) == ["Gathered"]
    assert names(hide_loot=True, hide_locked=True, gemstones_unlocked=True) == ["Gathered", "Gemstone"]


def test_item_sources_collect_all_known_ways(tmp_path, monkeypatch):
    monkeypatch.setattr("storage.DATA_DIR", tmp_path)
    lists.add_item("Mats", "Iron Ore", 1)
    sources = fake_sources(gatherable=[5111], timed=[5111], gil=[5111])
    monkeypatch.setattr("xivapi.fetch_material_sources", lambda: sources)
    vendor = {"name": "O'rhoyod", "zone": "Limsa", "aetheryte": "Plaza", "x": 9.1, "y": 7.5}
    offers = [{"shop": None, "currency": 1, "price": 250, "vendor": vendor}]
    monkeypatch.setattr("xivapi.fetch_item_offers", lambda game_id: offers)
    monkeypatch.setattr("xivapi.fetch_item_details", lambda game_id: {"price": 250, "marketable": True})
    info = lists.get_item_sources("Mats", 1)
    assert info["gatherable"] is True
    assert info["timed"] is True
    assert info["gil"] is True
    assert info["loot"] is False
    assert info["game_id"] == 5111
    assert info["offers"] == [
        {"shop": None, "currency": 1, "price": 250, "vendor": vendor, "currency_name": None}
    ]


def test_item_sources_mark_reduction_results_as_sourced(tmp_path, monkeypatch):
    monkeypatch.setattr("storage.DATA_DIR", tmp_path)
    lists.add_item("Mats", "Iron Ore", 1)
    monkeypatch.setattr("xivapi.fetch_material_sources", lambda: fake_sources(reduction=[5111]))
    info = lists.get_item_sources("Mats", 1)
    assert info["reduction"] is True
    assert info["loot"] is False


def test_item_sources_mark_reducible_items(tmp_path, monkeypatch):
    monkeypatch.setattr("storage.DATA_DIR", tmp_path)
    lists.add_item("Mats", "Iron Ore", 1)
    sources = fake_sources(gatherable=[5111], reducible=[5111])
    monkeypatch.setattr("xivapi.fetch_material_sources", lambda: sources)
    info = lists.get_item_sources("Mats", 1)
    assert info["reducible"] is True
    assert info["reduction"] is False


def test_item_sources_infer_loot_and_reject_unknown_items(tmp_path, monkeypatch):
    monkeypatch.setattr("storage.DATA_DIR", tmp_path)
    lists.add_item("Mats", "Iron Ore", 1)
    monkeypatch.setattr("xivapi.fetch_material_sources", lambda: fake_sources())
    info = lists.get_item_sources("Mats", 1)
    assert info["loot"] is True
    assert info["offers"] == []
    assert lists.get_item_sources("Mats", 99) is None


def fake_currency_shop():
    return {"26807": {
        "100": {"cost": 2, "amount": 1, "locked": False},
        "101": {"cost": 4, "amount": 2, "locked": True},
        "102": {"cost": 1, "amount": 1, "locked": False},
        "103": {"cost": 1, "amount": 1, "locked": False},
    }}


def test_currency_yields_rank_by_gil_per_unit(monkeypatch):
    monkeypatch.setattr("xivapi.fetch_currency_shop", fake_currency_shop)
    monkeypatch.setattr("universalis.fetch_marketable_ids", lambda: {100, 101, 103})
    stats = {
        100: {"price": 500, "avg_price": 480, "min_sale": 450, "max_sale": 520, "week_volume": 70},
        101: {"price": 2000, "avg_price": 2400, "min_sale": 1800, "max_sale": 2900, "week_volume": 7},
        103: {"price": 0, "avg_price": 0, "min_sale": 0, "max_sale": 0, "week_volume": 0},
    }
    monkeypatch.setattr("universalis.fetch_market_stats",
                        lambda world, ids: {item_id: stats[item_id] for item_id in ids})
    monkeypatch.setattr("xivapi.fetch_item_names",
                        lambda ids: {item_id: f"Item {item_id}" for item_id in ids})
    entries = lists.get_currency_yields(26807, 66)
    assert [entry["game_id"] for entry in entries] == [101, 100]
    assert entries[0]["yield"] == 1000.0
    assert entries[0]["avg_price"] == 2400
    assert entries[0]["min_sale"] == 1800
    assert entries[0]["max_sale"] == 2900
    assert entries[0]["locked"] is True
    assert entries[0]["name"] == "Item 101"
    assert entries[1]["yield"] == 250.0
    assert entries[1]["week_volume"] == 70


def test_currency_yields_fail_without_market_data(monkeypatch):
    monkeypatch.setattr("xivapi.fetch_currency_shop", fake_currency_shop)
    monkeypatch.setattr("universalis.fetch_marketable_ids", lambda: None)
    assert lists.get_currency_yields(26807, 66) is None


def test_currency_options_are_sorted_by_name(monkeypatch):
    monkeypatch.setattr("xivapi.fetch_currency_shop", lambda: {"33913": {}, "26807": {}})
    names = {26807: "Bicolor Gemstone", 33913: "Purple Crafters' Scrip"}
    monkeypatch.setattr("xivapi.fetch_item_names", lambda ids: names)
    assert lists.get_currency_options() == [
        {"id": 26807, "name": "Bicolor Gemstone"},
        {"id": 33913, "name": "Purple Crafters' Scrip"},
    ]


def fake_ventures():
    return [
        {"item": 100, "level": 10, "cost": 1, "job": "miner",
         "quantities": [5, 7, 10, 12, 15], "breakpoints": [20, 29, 32, 35]},
        {"item": 101, "level": 80, "cost": 2, "job": "miner",
         "quantities": [1, 2, 3, 4, 5], "breakpoints": [500, 600, 700, 800]},
        {"item": 102, "level": 50, "cost": 1, "job": "botanist",
         "quantities": [1, 1, 1, 1, 1], "breakpoints": [0, 0, 0, 0]},
        {"item": 103, "level": 10, "cost": 1, "job": "miner",
         "quantities": [5, 7, 10, 12, 15], "breakpoints": [20, 29, 32, 35]},
    ]


VENTURE_STATS = {
    100: {"price": 100, "avg_price": 95, "min_sale": 90, "max_sale": 110, "week_volume": 200},
    101: {"price": 4000, "avg_price": 3900, "min_sale": 3800, "max_sale": 4100, "week_volume": 12},
}


def stub_venture_market(monkeypatch):
    monkeypatch.setattr("xivapi.fetch_ventures", fake_ventures)
    monkeypatch.setattr("universalis.fetch_marketable_ids", lambda: {100, 101, 102})
    monkeypatch.setattr("universalis.fetch_market_stats",
                        lambda world, ids: {item_id: VENTURE_STATS[item_id] for item_id in ids})
    monkeypatch.setattr("xivapi.fetch_item_names",
                        lambda ids: {item_id: f"Item {item_id}" for item_id in ids})


def test_venture_yields_rank_by_gil_at_the_stat_tier(monkeypatch):
    stub_venture_market(monkeypatch)
    entries = lists.get_venture_yields(66, "miner", None, 30)
    assert [entry["game_id"] for entry in entries] == [101, 100]
    assert entries[0]["quantity"] == 1
    assert entries[0]["yield"] == 2000.0
    assert entries[1]["quantity"] == 10
    assert entries[1]["yield"] == 1000.0
    assert entries[1]["name"] == "Item 100"


def test_venture_yields_filter_by_level_and_default_to_best_tier(monkeypatch):
    stub_venture_market(monkeypatch)
    entries = lists.get_venture_yields(66, "miner", 20, None)
    assert [entry["game_id"] for entry in entries] == [100]
    assert entries[0]["quantity"] == 15


def test_venture_yields_fail_without_market_data(monkeypatch):
    monkeypatch.setattr("xivapi.fetch_ventures", fake_ventures)
    monkeypatch.setattr("universalis.fetch_marketable_ids", lambda: None)
    assert lists.get_venture_yields(66, "miner", None, None) is None


def test_worlds_are_sorted_by_name(monkeypatch):
    worlds = [{"id": 66, "name": "Odin"}, {"id": 33, "name": "Twintania"}, {"id": 39, "name": "Alpha"}]
    monkeypatch.setattr("universalis.fetch_worlds", lambda: worlds)
    assert [world["name"] for world in lists.get_worlds()] == ["Alpha", "Odin", "Twintania"]


def test_craft_costs_sort_crystals_last(monkeypatch):
    craftable = dict(source_craftable(1, "Mixed", 100), ingredients=[
        {"name": "Ice Crystal", "game_id": 9, "amount": 8},
        {"name": "Ore", "game_id": 100, "amount": 4},
        {"name": "Fire Crystal", "game_id": 8, "amount": 8},
        {"name": "Log", "game_id": 101, "amount": 5},
    ])
    monkeypatch.setattr("xivapi.fetch_craftables", lambda: [craftable])
    monkeypatch.setattr("xivapi.fetch_material_sources", lambda: fake_sources(gatherable=[100, 101]))
    entry = lists.get_craft_costs(100, "all", True)[0]
    assert [m["name"] for m in entry["materials"]] == ["Ore", "Log", "Ice Crystal", "Fire Crystal"]


def test_craft_costs_treat_everything_as_gathered_without_sources(monkeypatch):
    monkeypatch.setattr("xivapi.fetch_craftables", lambda: [source_craftable(1, "Unknown", 999)])
    entries = lists.get_craft_costs(100, "all", True)
    assert entries[0]["materials"][0]["source"] == "gather"
    assert entries[0]["has_loot"] is False
    assert entries[0]["cost"] == 20


def test_craft_costs_filter_by_level_and_job(monkeypatch):
    monkeypatch.setattr("xivapi.fetch_craftables", lambda: COST_CRAFTABLES)
    assert lists.get_craft_costs(89, "all", False) == []
    assert lists.get_craft_costs(99, "all", True) == []
    by_job = lists.get_craft_costs(100, "culinarian", True)
    assert [entry["name"] for entry in by_job] == ["One Type"]


def test_alarm_sounds_list_built_in_first_and_custom_last():
    sounds = lists.alarm_sounds()
    built_in_count = len(lists.BUILT_IN_ALARMS)
    assert sounds[:built_in_count] == lists.BUILT_IN_ALARMS
    for custom in sounds[built_in_count:]:
        assert custom not in lists.BUILT_IN_ALARMS


def test_unknown_list_is_empty(tmp_path, monkeypatch):
    monkeypatch.setattr("storage.DATA_DIR", tmp_path)
    assert lists.get_items("DoesNotExist") == []


def test_update_item_changes_amount(tmp_path, monkeypatch):
    monkeypatch.setattr("storage.DATA_DIR", tmp_path)
    lists.add_item("Ores", "Iron Ore", 20)
    lists.update_item("Ores", 1, 99)
    assert lists.get_items("Ores") == [
        {"id": 1, "name": "Iron Ore", "amount": 99, "game_id": 5111, "gathering": None, "craftable": False, "done": False, "muted": False, "materials_added": False, "sticky": False, "note": "", "job_icons": [], "marketable": None, "language": "en", "crystal": False, "group": 1}
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
        {"id": 1, "name": "Iron Ore", "amount": 20, "game_id": 5111, "gathering": None, "craftable": False, "done": False, "muted": False, "materials_added": False, "sticky": False, "note": "", "job_icons": [], "marketable": None, "language": "en", "crystal": False, "group": 1}
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
        {"id": 1, "name": "Mystery Rock", "amount": 3, "game_id": None, "gathering": None, "craftable": False, "done": False, "muted": False, "materials_added": False, "sticky": False, "note": "", "job_icons": [], "marketable": None, "language": "en", "crystal": False, "group": 1}
    ]


def test_remove_item(tmp_path, monkeypatch):
    monkeypatch.setattr("storage.DATA_DIR", tmp_path)
    lists.add_item("Ores", "Iron Ore", 20)
    lists.add_item("Ores", "Copper Ore", 5)
    lists.remove_item("Ores", 1)
    items = lists.get_items("Ores")
    assert len(items) == 1
    assert items[0]["name"] == "Copper Ore"
