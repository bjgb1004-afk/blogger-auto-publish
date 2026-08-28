import json
import config


def test_default_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CONFIG_PATH", tmp_path / "config.json")
    assert config.get_daily_post_count() == 3
    assert (tmp_path / "config.json").exists()


def test_set_and_get_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CONFIG_PATH", tmp_path / "config.json")
    config.set_daily_post_count(8)
    assert config.get_daily_post_count() == 8
    data = json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))
    assert data["daily_post_count"] == 8
