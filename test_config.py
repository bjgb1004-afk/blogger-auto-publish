import json
import config


def test_default_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CONFIG_PATH", tmp_path / "config.json")
    assert config.get_daily_post_count("blogspot") == 2
    assert config.get_daily_post_count("tistory") == 3
    assert (tmp_path / "config.json").exists()


def test_set_and_get_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CONFIG_PATH", tmp_path / "config.json")
    config.set_daily_post_count("tistory", 8)
    assert config.get_daily_post_count("tistory") == 8
    assert config.get_daily_post_count("blogspot") == 2  # 다른 트랙은 안 건드린다
    data = json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))
    assert data["daily_post_count"]["tistory"] == 8
