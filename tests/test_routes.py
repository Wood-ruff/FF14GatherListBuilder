import pytest

from app import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr("storage.DATA_DIR", tmp_path)
    monkeypatch.setattr("xivapi.fetch_item", lambda name: None)
    monkeypatch.setattr("xivapi.fetch_recipe", lambda name: None)
    monkeypatch.setattr("xivapi.fetch_gathering", lambda game_id: None)
    monkeypatch.setattr("xivapi.download_craft_icon", lambda icon_id: None)
    monkeypatch.setattr("xivapi.ensure_job_type_icon", lambda type_id: None)
    monkeypatch.setattr("settings.SETTINGS_FILE", tmp_path / "settings.json")
    return app.test_client()


def test_start_page_loads(client):
    response = client.get("/")
    assert response.status_code == 200


def test_add_item_shows_up_in_list(client):
    response = client.post("/add", data={"list": "Demo", "item": "Iron Ore", "amount": "20"})
    assert response.status_code == 302
    page = client.get("/?list=Demo").get_data(as_text=True)
    assert "Iron Ore" in page
    assert "20" in page


def test_add_rejects_non_numeric_amount(client):
    client.post("/add", data={"list": "Demo", "item": "Iron Ore", "amount": "abc"})
    page = client.get("/?list=Demo").get_data(as_text=True)
    assert "Iron Ore" not in page


def test_add_rejects_missing_fields(client):
    client.post("/add", data={"list": "Demo", "item": "", "amount": "5"})
    page = client.get("/?list=Demo").get_data(as_text=True)
    assert "<td>" not in page


def test_materials_button_only_for_craftable_items(client, monkeypatch):
    item = {"row_id": 47184, "fields": {"Name": "Crested Headband"}}
    recipe = {"yields": 1, "ingredients": [{"name": "Iron Ore", "game_id": 5111, "amount": 4}]}
    monkeypatch.setattr("xivapi.fetch_item", lambda name: item)
    monkeypatch.setattr("xivapi.fetch_recipe", lambda name: recipe)
    client.post("/add", data={"list": "Demo", "item": "Crested Headband", "amount": "1"})

    monkeypatch.setattr("xivapi.fetch_item", lambda name: None)
    monkeypatch.setattr("xivapi.fetch_recipe", lambda name: None)
    client.post("/add", data={"list": "Demo", "item": "Mystery Rock", "amount": "1"})

    page = client.get("/?list=Demo").get_data(as_text=True)
    assert 'form="mats-1"' in page
    assert 'form="mats-2"' not in page


def test_add_materials_via_post(client, monkeypatch):
    recipe = {"yields": 1, "ingredients": [{"name": "Iron Ore", "game_id": 5111, "amount": 4}]}
    recipes = {"crested headband": recipe}
    monkeypatch.setattr("xivapi.fetch_recipe", lambda name: recipes.get(name.lower()))
    client.post("/add", data={"list": "Demo", "item": "Crested Headband", "amount": "2"})
    response = client.post("/add-materials", data={"list": "Demo", "id": "1"})
    assert response.status_code == 302
    page = client.get("/?list=Demo").get_data(as_text=True)
    assert "Iron Ore" in page
    assert 'value="8"' in page


def test_crystals_show_no_timer_and_timed_items_get_mute_toggle(client, monkeypatch):
    gathering = {
        "timed": True,
        "times": [{"start": 600, "duration": 120}],
        "zone": "Living Memory",
        "aetheryte": None,
    }
    cluster = {"row_id": 16, "fields": {"Name": "Wind Cluster"}}
    leaf = {"row_id": 43930, "fields": {"Name": "Bay Leaf"}}
    monkeypatch.setattr("xivapi.fetch_gathering", lambda game_id: gathering)
    monkeypatch.setattr("xivapi.fetch_item", lambda name: cluster)
    client.post("/add", data={"list": "Demo", "item": "Wind Cluster", "amount": "3"})
    page = client.get("/?list=Demo").get_data(as_text=True)
    assert "node-timer" not in page

    monkeypatch.setattr("xivapi.fetch_item", lambda name: leaf)
    client.post("/add", data={"list": "Demo", "item": "Bay Leaf", "amount": "1"})
    page = client.get("/?list=Demo").get_data(as_text=True)
    assert "node-timer" in page
    assert page.count('class="mute-toggle"') == 1


def test_craftable_item_shows_materials_toggle(client, monkeypatch):
    item = {"row_id": 47184, "fields": {"Name": "Crested Headband"}}
    recipe = {"yields": 1, "ingredients": [{"name": "Iron Ore", "game_id": 5111, "amount": 4}]}
    monkeypatch.setattr("xivapi.fetch_item", lambda name: item)
    monkeypatch.setattr("xivapi.fetch_recipe", lambda name: recipe)
    client.post("/add", data={"list": "Demo", "item": "Crested Headband", "amount": "1"})
    page = client.get("/?list=Demo").get_data(as_text=True)
    assert 'class="materials-toggle"' in page

    response = client.post("/toggle-materials", data={"list": "Demo", "id": "1", "added": "1"})
    assert response.status_code == 204
    page = client.get("/?list=Demo").get_data(as_text=True)
    assert "checked" in page


def test_toggle_mute_via_post(client):
    client.post("/add", data={"list": "Demo", "item": "Iron Ore", "amount": "5"})
    response = client.post("/toggle-mute", data={"list": "Demo", "id": "1", "muted": "1"})
    assert response.status_code == 204
    items = client.get("/?list=Demo").get_data(as_text=True)
    assert items


def test_language_switch_translates_the_open_list_immediately(client, monkeypatch):
    item = {"row_id": 5111, "fields": {"Name": "Iron Ore"}}
    monkeypatch.setattr("xivapi.fetch_item", lambda name: item)
    client.post("/add", data={"list": "Demo", "item": "Iron Ore", "amount": "5"})

    german = {"row_id": 5111, "fields": {"Name": "Eisenerz"}}
    monkeypatch.setattr("xivapi.fetch_item_by_id", lambda game_id: german)
    client.post("/language", data={"language": "de", "list": "Demo"})
    page = client.get("/?list=Demo").get_data(as_text=True)
    assert "Eisenerz" in page


def test_opening_a_list_in_a_new_language_localizes_it(client, monkeypatch):
    item = {"row_id": 5111, "fields": {"Name": "Iron Ore"}}
    monkeypatch.setattr("xivapi.fetch_item", lambda name: item)
    client.post("/add", data={"list": "Demo", "item": "Iron Ore", "amount": "5"})

    client.post("/language", data={"language": "de", "list": "Demo"})
    german = {"row_id": 5111, "fields": {"Name": "Eisenerz"}}
    monkeypatch.setattr("xivapi.fetch_item_by_id", lambda game_id: german)
    monkeypatch.setattr("routes.run_in_background", lambda task: task())
    client.get("/?list=Demo")
    page = client.get("/?list=Demo").get_data(as_text=True)
    assert "Eisenerz" in page


def test_set_note_via_post(client):
    client.post("/add", data={"list": "Demo", "item": "Iron Ore", "amount": "5"})
    response = client.post("/set-note", data={"list": "Demo", "id": "1", "note": "west of camp"})
    assert response.status_code == 204
    page = client.get("/?list=Demo").get_data(as_text=True)
    assert 'value="west of camp"' in page


def test_toggle_sticky_via_post(client):
    client.post("/add", data={"list": "Demo", "item": "Iron Ore", "amount": "5"})
    response = client.post("/toggle-sticky", data={"list": "Demo", "id": "1", "sticky": "1"})
    assert response.status_code == 204
    page = client.get("/?list=Demo").get_data(as_text=True)
    first_row_tag = page.split("<tbody>")[1].split(">")[0]
    assert "sticky" in first_row_tag
    assert 'class="sticky-toggle"' in page


def test_toggle_done_via_post(client):
    client.post("/add", data={"list": "Demo", "item": "Iron Ore", "amount": "5"})
    response = client.post("/toggle-done", data={"list": "Demo", "id": "1", "done": "1"})
    assert response.status_code == 204
    page = client.get("/?list=Demo").get_data(as_text=True)
    assert 'class="done' in page
    assert "checked" in page


def test_update_item_via_post(client):
    client.post("/add", data={"list": "Demo", "item": "Iron Ore", "amount": "20"})
    response = client.post("/update", data={"list": "Demo", "id": "1", "amount": "50"})
    assert response.status_code == 302
    page = client.get("/?list=Demo").get_data(as_text=True)
    assert 'value="50"' in page


def test_delete_item_via_post(client):
    client.post("/add", data={"list": "Demo", "item": "Iron Ore", "amount": "20"})
    response = client.post("/delete", data={"list": "Demo", "id": "1"})
    assert response.status_code == 302
    page = client.get("/?list=Demo").get_data(as_text=True)
    assert "Iron Ore" not in page


def test_item_name_is_marked_for_chat_copy(client):
    client.post("/add", data={"list": "Demo", "item": "Iron Ore", "amount": "20"})
    page = client.get("/?list=Demo").get_data(as_text=True)
    assert 'class="copy-name" data-name="Iron Ore"' in page


def test_timed_item_shows_node_timer(client, monkeypatch):
    item = {"row_id": 43930, "fields": {"Name": "Bay Leaf"}}
    gathering = {
        "timed": True,
        "times": [{"start": 600, "duration": 120}],
        "zone": "Living Memory",
        "aetheryte": "Leynode Mnemo",
    }
    monkeypatch.setattr("xivapi.fetch_item", lambda name: item)
    monkeypatch.setattr("xivapi.fetch_gathering", lambda game_id: gathering)
    client.post("/add", data={"list": "Demo", "item": "Bay Leaf", "amount": "1"})
    page = client.get("/?list=Demo").get_data(as_text=True)
    assert 'class="node-timer"' in page
    assert 'data-alarm="1"' in page
    assert 'data-zone="Living Memory"' in page
    assert 'data-aetheryte="Leynode Mnemo"' in page


def test_untimed_item_shows_no_timer(client):
    client.post("/add", data={"list": "Demo", "item": "Iron Ore", "amount": "1"})
    page = client.get("/?list=Demo").get_data(as_text=True)
    assert "node-timer" not in page


def test_known_item_links_to_garland_tools(client, monkeypatch):
    item = {"row_id": 5111, "fields": {"Name": "Iron Ore"}}
    monkeypatch.setattr("xivapi.fetch_item", lambda name: item)
    client.post("/add", data={"list": "Demo", "item": "Iron Ore", "amount": "20"})
    page = client.get("/?list=Demo").get_data(as_text=True)
    assert 'href="https://www.garlandtools.org/db/#item/5111"' in page


def test_unknown_item_has_no_garland_link(client):
    client.post("/add", data={"list": "Demo", "item": "Mystery Rock", "amount": "1"})
    page = client.get("/?list=Demo").get_data(as_text=True)
    assert "garlandtools.org" not in page


def test_craft_via_post_adds_materials(client, monkeypatch):
    recipe = {"yields": 1, "ingredients": [{"name": "Iron Ore", "game_id": 5111, "amount": 4}]}
    recipes = {"crested headband": recipe}
    monkeypatch.setattr("xivapi.fetch_recipe", lambda name: recipes.get(name.lower()))
    response = client.post("/craft", data={"list": "Demo", "item": "Crested Headband", "amount": "1"})
    assert response.status_code == 302
    page = client.get("/?list=Demo").get_data(as_text=True)
    assert "Iron Ore" in page
    assert "Crested Headband" not in page.split("</h2>")[1]


def test_icon_route_serves_cached_icon(client, tmp_path, monkeypatch):
    icons = tmp_path / "icons"
    icons.mkdir()
    (icons / "5111.png").write_bytes(b"png-bytes")
    monkeypatch.setattr("item_cache.ICONS_DIR", icons)
    response = client.get("/icons/5111")
    assert response.status_code == 200
    assert response.data == b"png-bytes"


def test_icon_route_missing_icon_is_404(client, tmp_path, monkeypatch):
    monkeypatch.setattr("item_cache.ICONS_DIR", tmp_path / "icons")
    assert client.get("/icons/999").status_code == 404


def test_export_downloads_the_list_file(client):
    client.post("/add", data={"list": "Demo", "item": "Iron Ore", "amount": "5"})
    response = client.get("/export?list=Demo")
    assert response.status_code == 200
    assert "attachment" in response.headers["Content-Disposition"]
    assert b"Iron Ore" in response.data


def test_export_unknown_list_redirects(client):
    assert client.get("/export?list=Nope").status_code == 302


def test_import_creates_the_list(client, monkeypatch):
    import io
    import json as jsonlib

    monkeypatch.setattr("routes.run_in_background", lambda task: task())
    payload = jsonlib.dumps([{"name": "Iron Ore", "amount": 7}]).encode("utf-8")
    response = client.post(
        "/import",
        data={"file": (io.BytesIO(payload), "Friends List.json")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 302
    page = client.get("/?list=Friends List").get_data(as_text=True)
    assert "Iron Ore" in page


def test_import_rejects_broken_files(client):
    import io

    response = client.post(
        "/import",
        data={"file": (io.BytesIO(b"not json"), "broken.json")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 302
    page = client.get("/").get_data(as_text=True)
    assert "broken" not in page


def test_long_list_names_are_shortened_in_display_only(client):
    long_name = "My Extremely Long Gathering List Name"
    client.post("/create-list", data={"list": long_name, "next": "/"})
    page = client.get(f"/?list={long_name}").get_data(as_text=True)
    assert f'value="{long_name}"' in page
    assert "My Extremely Long Gathe…" in page
    assert f">{long_name}</h2>" not in page


def test_create_list_makes_an_empty_list(client):
    response = client.post("/create-list", data={"list": "gather items", "next": "/"})
    assert response.status_code == 302
    page = client.get("/").get_data(as_text=True)
    assert '<option value="gather items"' in page


def test_create_list_from_collectables_returns_there(client, monkeypatch):
    monkeypatch.setattr("xivapi.fetch_collectables", lambda: [])
    response = client.post("/create-list", data={"list": "Demo", "next": "/collectables"})
    assert response.headers["Location"].startswith("/collectables")


def test_create_list_rejects_bad_names(client):
    client.post("/create-list", data={"list": "../evil", "next": "/"})
    page = client.get("/").get_data(as_text=True)
    assert "evil" not in page


def test_timed_first_toggle_reorders_the_list(client, monkeypatch):
    timed = {"timed": True, "times": [{"start": 600, "duration": 120}], "zone": None, "aetheryte": None}
    client.post("/add", data={"list": "Demo", "item": "Maple Log", "amount": "1"})
    monkeypatch.setattr("xivapi.fetch_gathering", lambda game_id: timed)
    monkeypatch.setattr("xivapi.fetch_item", lambda name: {"row_id": 43930, "fields": {"Name": "Bay Leaf"}})
    client.post("/add", data={"list": "Demo", "item": "Bay Leaf", "amount": "1"})

    page = client.get("/?list=Demo&timed=1").get_data(as_text=True)
    assert page.find("Bay Leaf") < page.find("Maple Log")


def test_list_name_filter_narrows_the_items(client):
    client.post("/add", data={"list": "Demo", "item": "Iron Ore", "amount": "5"})
    client.post("/add", data={"list": "Demo", "item": "Maple Log", "amount": "2"})
    page = client.get("/?list=Demo&q=iron").get_data(as_text=True)
    assert "Iron Ore" in page
    assert "Maple Log" not in page


def test_add_all_materials_via_post(client, monkeypatch):
    items = {
        "crested headband": {"row_id": 47184, "fields": {"Name": "Crested Headband"}},
        "iron ore": {"row_id": 5111, "fields": {"Name": "Iron Ore"}},
    }
    recipes = {
        "crested headband": {
            "yields": 1,
            "ingredients": [{"name": "Iron Ore", "game_id": 5111, "amount": 4}],
        },
    }
    monkeypatch.setattr("xivapi.fetch_item", lambda name: items.get(name.lower()))
    monkeypatch.setattr("xivapi.fetch_recipe", lambda name: recipes.get(name.lower()))
    monkeypatch.setattr("routes.run_in_background", lambda task: task())
    client.post("/add", data={"list": "Demo", "item": "Crested Headband", "amount": "2"})

    response = client.post("/add-all-materials", data={"list": "Demo"})
    assert response.status_code == 302
    page = client.get("/?list=Demo").get_data(as_text=True)
    assert "Iron Ore" in page
    assert 'value="8"' in page


def test_remove_materials_via_post(client, monkeypatch):
    item = {"row_id": 47184, "fields": {"Name": "Crested Headband"}}
    recipe = {"yields": 1, "ingredients": [{"name": "Iron Ore", "game_id": 5111, "amount": 4}]}
    monkeypatch.setattr("xivapi.fetch_item", lambda name: item)
    monkeypatch.setattr("xivapi.fetch_recipe", lambda name: recipe)
    client.post("/add", data={"list": "Demo", "item": "Crested Headband", "amount": "1"})
    client.post("/add-materials", data={"list": "Demo", "id": "1"})

    response = client.post("/remove-materials", data={"list": "Demo"})
    assert response.status_code == 302
    page = client.get("/?list=Demo").get_data(as_text=True)
    assert "Crested Headband" in page
    assert "Iron Ore" not in page


def test_clear_list_empties_but_keeps_the_list(client):
    client.post("/add", data={"list": "Demo", "item": "Iron Ore", "amount": "20"})
    response = client.post("/clear-list", data={"list": "Demo"})
    assert response.status_code == 302
    page = client.get("/?list=Demo").get_data(as_text=True)
    assert "Iron Ore" not in page
    assert '<option value="Demo"' in page


def test_delete_list_via_post(client):
    client.post("/add", data={"list": "Demo", "item": "Iron Ore", "amount": "20"})
    response = client.post("/delete-list", data={"list": "Demo"})
    assert response.status_code == 302
    page = client.get("/").get_data(as_text=True)
    assert "Demo" not in page


def test_suggest_returns_json_names(client, monkeypatch):
    monkeypatch.setattr("xivapi.search_item_names", lambda text: ["Iron Ore", "Iron Ingot"])
    response = client.get("/suggest?q=iron")
    assert response.status_code == 200
    assert response.get_json() == ["Iron Ore", "Iron Ingot"]


def test_banner_shows_when_api_is_unreachable(client, monkeypatch):
    monkeypatch.setattr("lists.last_lookup_failed", lambda: True)
    page = client.get("/").get_data(as_text=True)
    assert 'class="banner"' in page


def test_no_banner_when_api_works(client):
    page = client.get("/").get_data(as_text=True)
    assert 'class="banner"' not in page


def test_collectables_tab_lists_items(client, monkeypatch):
    collectables = [{
        "game_id": 43930, "name": "Rarefied Windsbalm Bay Leaf", "level": 100, "stars": 2,
        "scrips": {"low": 16, "mid": 23, "high": 38},
        "job": "Harvesting", "job_id": 3, "zone": "Living Memory", "aetheryte": "Leynode Mnemo",
        "x": 8.7, "y": 7.5, "times": [{"start": 600, "duration": 120}], "timed": True,
    }]
    monkeypatch.setattr("xivapi.fetch_collectables", lambda: collectables)
    page = client.get("/collectables").get_data(as_text=True)
    assert "Rarefied Windsbalm Bay Leaf" in page
    assert "16 / 23 / 38" in page
    assert ">Living Memory</a>, <a" in page
    assert 'href="https://ffxiv.consolegameswiki.com/wiki/Leynode_Mnemo"' in page
    assert ">Leynode Mnemo</a> (8.7, 7.5)" in page
    assert 'src="/job-icons/3"' in page
    assert "Harvesting" in page
    assert 'class="node-timer"' in page
    assert "data-alarm" not in page
    assert 'href="https://www.garlandtools.org/db/#item/43930"' in page
    assert 'href="https://ffxiv.consolegameswiki.com/wiki/Living_Memory"' in page
    assert 'data-store="collectables"' in page
    assert 'class="alarm-mark" data-id="43930"' in page
    assert 'id="marked-alarm-toggle"' in page
    assert 'id="marked-filter"' in page


def test_list_picker_is_on_both_tabs(client, monkeypatch):
    monkeypatch.setattr("xivapi.fetch_collectables", lambda: [])
    main_page = client.get("/").get_data(as_text=True)
    collectables_page = client.get("/collectables").get_data(as_text=True)
    assert 'placeholder="New list name"' in main_page
    assert 'placeholder="New list name"' in collectables_page


def test_collectables_filters_via_query(client, monkeypatch):
    collectables = [
        {"game_id": 1, "name": "Ore Thing", "level": 90, "stars": 0, "job": "Mining",
         "job_id": 0, "zone": None, "x": None, "y": None, "scrips": None},
        {"game_id": 2, "name": "Leafy Thing", "level": 90, "stars": 0, "job": "Logging",
         "job_id": 2, "zone": None, "x": None, "y": None, "scrips": None},
    ]
    monkeypatch.setattr("xivapi.fetch_collectables", lambda: collectables)
    page = client.get("/collectables?job=miner").get_data(as_text=True)
    assert "Ore Thing" in page
    assert "Leafy Thing" not in page
    assert 'src="/job-icons/0"' in page


def test_collectables_are_paginated(client, monkeypatch):
    entries = [
        {"game_id": n, "name": f"Item {n:03d}", "level": 50, "stars": 0, "job": "Mining",
         "job_id": 0, "zone": None, "aetheryte": None, "x": None, "y": None,
         "scrips": None, "times": [], "timed": False}
        for n in range(1, 31)
    ]
    monkeypatch.setattr("xivapi.fetch_collectables", lambda: entries)
    page = client.get("/collectables?sort=name&size=25").get_data(as_text=True)
    assert "Item 001" in page
    assert "Item 026" not in page
    assert "1 / 2" in page

    page = client.get("/collectables?sort=name&size=25&page=2").get_data(as_text=True)
    assert "Item 026" in page
    assert "Item 001" not in page
    assert "2 / 2" in page


def test_pinned_items_persist_through_filters_and_paging(client, monkeypatch):
    entries = [
        {"game_id": n, "name": f"Item {n:03d}", "level": 50, "stars": 0, "job": "Mining",
         "job_id": 0, "zone": None, "aetheryte": None, "x": None, "y": None,
         "scrips": None, "times": [], "timed": False}
        for n in range(1, 31)
    ]
    monkeypatch.setattr("xivapi.fetch_collectables", lambda: entries)
    client.set_cookie("pin-persist-collectables", "1")
    client.set_cookie("pins-collectables", "30")

    page = client.get("/collectables?sort=name&size=25").get_data(as_text=True)
    assert "Item 030" in page

    page = client.get("/collectables?sort=name&q=Item 001").get_data(as_text=True)
    assert page.count(">Item 030</a>") == 1
    assert page.count(">Item 001</a>") == 1

    client.set_cookie("pin-persist-collectables", "0")
    page = client.get("/collectables?sort=name&q=Item 001").get_data(as_text=True)
    assert "Item 030" not in page


def test_collectable_can_be_added_to_list(client, monkeypatch):
    monkeypatch.setattr("xivapi.fetch_collectables", lambda: [])
    response = client.post(
        "/collectables/add",
        data={"list": "Demo", "item": "Rarefied Manasilver Sand", "amount": "3", "sort": "level"},
    )
    assert response.status_code == 302
    page = client.get("/?list=Demo").get_data(as_text=True)
    assert "Rarefied Manasilver Sand" in page


def test_craftables_tab_lists_items(client, monkeypatch):
    craftables = [{
        "game_id": 43954, "name": "Rarefied Tacos de Carne Asada", "level": 100, "stars": 1,
        "jobs": ["Cooking"], "scrips": {"low": 12, "mid": 18, "high": 27},
    }]
    monkeypatch.setattr("xivapi.fetch_craftables", lambda: craftables)
    page = client.get("/craftables").get_data(as_text=True)
    assert "Rarefied Tacos de Carne Asada" in page
    assert "Culinarian" in page
    assert 'src="/craft-icons/62015"' in page
    assert "12 / 18 / 27" in page
    assert 'href="https://www.garlandtools.org/db/#item/43954"' in page
    assert 'data-store="craftables"' in page


def test_craftable_add_puts_item_and_materials_in_list(client, monkeypatch):
    recipe = {"yields": 1, "ingredients": [{"name": "Iron Ore", "game_id": 5111, "amount": 4}]}
    recipes = {"rarefied tacos": recipe}
    monkeypatch.setattr("xivapi.fetch_recipe", lambda name: recipes.get(name.lower()))
    monkeypatch.setattr("routes.run_in_background", lambda task: task())
    response = client.post(
        "/craftables/add", data={"list": "Demo", "item": "Rarefied Tacos", "amount": "2"}
    )
    assert response.status_code == 302
    page = client.get("/?list=Demo").get_data(as_text=True)
    assert "Rarefied Tacos" in page
    assert "Iron Ore" in page


def test_run_in_background_executes_the_task():
    import threading

    import routes

    done = threading.Event()
    routes.run_in_background(done.set)
    assert done.wait(timeout=5)


def test_pending_counter_returns_to_zero(client):
    import threading
    import time

    import routes

    done = threading.Event()
    routes.run_in_background(done.wait)
    assert client.get("/pending").get_json() == 1
    done.set()
    for _ in range(50):
        if client.get("/pending").get_json() == 0:
            break
        time.sleep(0.1)
    assert client.get("/pending").get_json() == 0


def test_backgrounds_are_passed_to_the_page(client):
    page = client.get("/").get_data(as_text=True)
    assert "window.BACKGROUNDS" in page


def test_alarm_dropdown_is_rendered(client):
    page = client.get("/").get_data(as_text=True)
    assert 'id="alarm-sound"' in page
    assert 'value="classic-beep.wav"' in page


def test_language_can_be_changed_via_post(client):
    response = client.post("/language", data={"language": "de", "list": ""})
    assert response.status_code == 302
    page = client.get("/").get_data(as_text=True)
    assert '<option value="de" selected>' in page


def test_ui_texts_follow_the_language(client):
    page = client.get("/").get_data(as_text=True)
    assert "New list name" in page
    client.post("/language", data={"language": "de", "list": ""})
    page = client.get("/").get_data(as_text=True)
    assert "Name der neuen Liste" in page
    assert "Öffnen" in page
    page = client.get("/?list=Demo").get_data(as_text=True)
    assert "Hinzufügen" in page


def test_clear_cache_via_post(client, monkeypatch):
    calls = []
    monkeypatch.setattr("lists.clear_caches", lambda: calls.append(1))
    response = client.post("/clear-cache", data={"list": "Demo"})
    assert response.status_code == 302
    assert calls == [1]


def test_delete_rejects_bad_id(client):
    client.post("/add", data={"list": "Demo", "item": "Iron Ore", "amount": "20"})
    client.post("/delete", data={"list": "Demo", "id": "abc"})
    page = client.get("/?list=Demo").get_data(as_text=True)
    assert "Iron Ore" in page
