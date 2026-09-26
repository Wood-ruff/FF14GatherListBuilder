import pytest

from app import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr("storage.DATA_DIR", tmp_path)
    monkeypatch.setattr("xivapi.fetch_item_id", lambda name: None)
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
    response = client.post(
        "/update", data={"list": "Demo", "id": "1", "item": "Iron Ore", "amount": "50"}
    )
    assert response.status_code == 302
    page = client.get("/?list=Demo").get_data(as_text=True)
    assert 'value="50"' in page


def test_delete_item_via_post(client):
    client.post("/add", data={"list": "Demo", "item": "Iron Ore", "amount": "20"})
    response = client.post("/delete", data={"list": "Demo", "id": "1"})
    assert response.status_code == 302
    page = client.get("/?list=Demo").get_data(as_text=True)
    assert "Iron Ore" not in page


def test_delete_rejects_bad_id(client):
    client.post("/add", data={"list": "Demo", "item": "Iron Ore", "amount": "20"})
    client.post("/delete", data={"list": "Demo", "id": "abc"})
    page = client.get("/?list=Demo").get_data(as_text=True)
    assert "Iron Ore" in page
