import json
from pathlib import Path

CONFIG_PATH = Path(__file__).parent / "config.json"
DEFAULT_CONFIG = {"daily_post_count": 3}


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        save_config(DEFAULT_CONFIG)
        return dict(DEFAULT_CONFIG)
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_config(config_data: dict) -> None:
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config_data, f, ensure_ascii=False, indent=2)


def get_daily_post_count() -> int:
    return load_config().get("daily_post_count", DEFAULT_CONFIG["daily_post_count"])


def set_daily_post_count(count: int) -> None:
    data = load_config()
    data["daily_post_count"] = count
    save_config(data)
