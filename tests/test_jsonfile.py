import json
import os

import jsonfile


def test_write_replaces_the_target_file(tmp_path):
    target = tmp_path / "data.json"
    target.write_text("old", encoding="utf-8")
    assert jsonfile.write_json_file(target, {"fresh": True}) is True
    assert json.loads(target.read_text(encoding="utf-8")) == {"fresh": True}
    assert [path.name for path in tmp_path.iterdir()] == ["data.json"]


def test_blocked_swaps_are_retried(tmp_path, monkeypatch):
    target = tmp_path / "data.json"
    attempts = {"count": 0}
    real_replace = os.replace

    def flaky_replace(source, destination):
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise PermissionError("locked by scanner")
        return real_replace(source, destination)

    monkeypatch.setattr("jsonfile.os.replace", flaky_replace)
    monkeypatch.setattr("jsonfile.RETRY_DELAY_SECONDS", 0)
    assert jsonfile.write_json_file(target, [1, 2]) is True
    assert attempts["count"] == 3
    assert json.loads(target.read_text(encoding="utf-8")) == [1, 2]


def test_persistently_blocked_swap_keeps_the_old_file(tmp_path, monkeypatch):
    target = tmp_path / "data.json"
    target.write_text("[]", encoding="utf-8")

    def blocked_replace(source, destination):
        raise PermissionError("locked for good")

    monkeypatch.setattr("jsonfile.os.replace", blocked_replace)
    monkeypatch.setattr("jsonfile.RETRY_DELAY_SECONDS", 0)
    assert jsonfile.write_json_file(target, [1, 2]) is False
    assert target.read_text(encoding="utf-8") == "[]"
    assert [path.name for path in tmp_path.iterdir()] == ["data.json"]
