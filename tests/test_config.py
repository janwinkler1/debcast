from pathlib import Path
from unittest.mock import patch

from debcast.config import Config, reset_config_cache


def test_defaults_load_without_config_file():
    reset_config_cache()
    with patch("debcast.config.CONFIG_PATH", new=Path("/nonexistent")):
        cfg = Config()
    assert cfg.research.rounds == 3
    assert cfg.anthropic.api_key == ""


def test_api_key_from_toml(tmp_path):
    toml = tmp_path / "config.toml"
    toml.write_text('[anthropic]\napi_key = "sk-ant-test"')
    with patch("debcast.config.CONFIG_PATH", new=toml):
        cfg = Config()
    assert cfg.anthropic.api_key == "sk-ant-test"


def test_env_override_takes_priority(tmp_path, monkeypatch):
    toml = tmp_path / "config.toml"
    toml.write_text("[research]\nrounds = 3")
    monkeypatch.setenv("DEBCAST_RESEARCH__ROUNDS", "7")
    with patch("debcast.config.CONFIG_PATH", new=toml):
        cfg = Config()
    assert cfg.research.rounds == 7
