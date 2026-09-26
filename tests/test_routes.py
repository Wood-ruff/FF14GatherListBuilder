import pytest

from app import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr("storage.DATA_DIR", tmp_path)
    monkeypatch.setattr("xivapi.fetch_item", lambda name: None)
    monkeypatch.setattr("xivapi.fetch_recipe", lambda name: None)
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
    assert "Could not reach xivapi" in page


def test_no_banner_when_api_works(client):
    page = client.get("/").get_data(as_text=True)
    assert "Could not reach xivapi" not in page


def test_language_can_be_changed_via_post(client):
    response = client.post("/language", data={"language": "de", "list": ""})
    assert response.status_code == 302
    page = client.get("/").get_data(as_text=True)
    assert '<option value="de" selected>' in page


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
