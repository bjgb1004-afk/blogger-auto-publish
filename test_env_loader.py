import os
import env_loader


def test_load_env_sets_missing_vars(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("FOO_TEST_KEY=bar\n# comment\n\nBAZ=qux\n", encoding="utf-8")
    monkeypatch.setattr(env_loader, "ENV_PATH", env_file)
    monkeypatch.delenv("FOO_TEST_KEY", raising=False)
    monkeypatch.delenv("BAZ", raising=False)
    env_loader.load_env()
    assert os.environ["FOO_TEST_KEY"] == "bar"
    assert os.environ["BAZ"] == "qux"


def test_load_env_does_not_override_existing(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("FOO_TEST_KEY=fromfile\n", encoding="utf-8")
    monkeypatch.setattr(env_loader, "ENV_PATH", env_file)
    monkeypatch.setenv("FOO_TEST_KEY", "already_set")
    env_loader.load_env()
    assert os.environ["FOO_TEST_KEY"] == "already_set"
