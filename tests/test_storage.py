import storage


def test_save_and_load_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr("storage.DATA_DIR", tmp_path)
    items = [{"name": "Maple Log", "amount": 10}]
    storage.save_items("Logs", items)
    assert storage.load_items("Logs") == items


def test_list_names_sorted(tmp_path, monkeypatch):
    monkeypatch.setattr("storage.DATA_DIR", tmp_path)
    storage.save_items("Beta", [])
    storage.save_items("Alpha", [])
    assert storage.get_list_names() == ["Alpha", "Beta"]


def test_load_missing_list_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setattr("storage.DATA_DIR", tmp_path)
    assert storage.load_items("Missing") == []
