import settings
import storage


def test_lists_live_in_their_own_folder():
    assert storage.DATA_DIR.name == "lists"
    assert settings.SETTINGS_FILE.parent != storage.DATA_DIR


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


def test_delete_list(tmp_path, monkeypatch):
    monkeypatch.setattr("storage.DATA_DIR", tmp_path)
    storage.save_items("Ores", [{"id": 1, "name": "Iron Ore", "amount": 1}])
    storage.delete_list("Ores")
    assert storage.get_list_names() == []


def test_delete_missing_list_is_harmless(tmp_path, monkeypatch):
    monkeypatch.setattr("storage.DATA_DIR", tmp_path)
    storage.delete_list("Nope")


def test_load_missing_list_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setattr("storage.DATA_DIR", tmp_path)
    assert storage.load_items("Missing") == []


def test_load_unreadable_list_counts_as_empty(tmp_path, monkeypatch):
    monkeypatch.setattr("storage.DATA_DIR", tmp_path)
    (tmp_path / "Broken.json").write_text("", encoding="utf-8")
    assert storage.load_items("Broken") == []


def test_saving_leaves_no_temp_file_behind(tmp_path, monkeypatch):
    monkeypatch.setattr("storage.DATA_DIR", tmp_path)
    storage.save_items("Logs", [{"name": "Maple Log", "amount": 10}])
    assert [path.name for path in tmp_path.iterdir()] == ["Logs.json"]
