# Implementation Plan: Config

**File:** `debcast/config.py`

## Purpose

Load, validate, and expose all configuration. Uses Pydantic Settings to read from `~/.debcast/config.toml`. Provides a single `get_config()` function used by the pipeline and CLI.

## Complete implementation

```python
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import (
    BaseSettings,
    EnvSettingsSource,
    TomlConfigSettingsSource,
    SettingsConfigDict,
)


CONFIG_PATH = Path.home() / ".debcast" / "config.toml"


class ProvidersConfig(BaseSettings):
    tts: Literal["gemini", "google_cloud", "elevenlabs", "kokoro"] = "gemini"
    hosting: Literal["podclaw", "local"] = "local"


class ResearchConfig(BaseSettings):
    rounds: int = Field(default=3, ge=1, le=10)


class AnthropicConfig(BaseSettings):
    api_key: str = ""
    # Not validated here — validated in ClaudeResearchProvider / ClaudeScriptProvider
    # constructors so that --list, local-only paths, and offline tests don't fail
    # when the key is absent.


class ElevenLabsConfig(BaseSettings):
    api_key: str = ""


class GoogleCloudConfig(BaseSettings):
    credentials_path: str = "~/.config/gcloud/application_default_credentials.json"


class GeminiConfig(BaseSettings):
    api_key: str = ""   # falls back to GOOGLE_API_KEY env var if empty


class PodClawConfig(BaseSettings):
    api_key: str = ""
    show_id: int = 0


class LocalConfig(BaseSettings):
    output_dir: str = "~/debcast-episodes"
    rss_path: str = "~/debcast-episodes/feed.xml"


class Config(BaseSettings):
    model_config = SettingsConfigDict(
        toml_file=str(CONFIG_PATH),
        env_prefix="DEBCAST_",
        env_nested_delimiter="__",   # enables DEBCAST_RESEARCH__ROUNDS=5
    )

    providers: ProvidersConfig = Field(default_factory=ProvidersConfig)
    research: ResearchConfig = Field(default_factory=ResearchConfig)
    anthropic: AnthropicConfig = Field(default_factory=AnthropicConfig)
    elevenlabs: ElevenLabsConfig = Field(default_factory=ElevenLabsConfig)
    google_cloud: GoogleCloudConfig = Field(default_factory=GoogleCloudConfig)
    gemini: GeminiConfig = Field(default_factory=GeminiConfig)
    podclaw: PodClawConfig = Field(default_factory=PodClawConfig)
    local: LocalConfig = Field(default_factory=LocalConfig)

    @classmethod
    def settings_customise_sources(cls, settings_cls, **kwargs):
        # Return both env and TOML sources so that environment variables override
        # the TOML file (e.g. DEBCAST_ANTHROPIC__API_KEY in CI).
        # Omitting EnvSettingsSource here would silently drop all env overrides.
        return (
            EnvSettingsSource(settings_cls),
            TomlConfigSettingsSource(settings_cls),
        )


@lru_cache(maxsize=1)
def get_config() -> Config:
    return Config()


def reset_config_cache() -> None:
    """Clear the cached config. Used in tests only."""
    get_config.cache_clear()
```

## config.example.toml

```toml
# ~/.debcast/config.toml

[providers]
tts      = "gemini"       # gemini | google_cloud | elevenlabs | kokoro
hosting  = "podclaw"      # podclaw | local

[research]
rounds = 3                # number of research exchange rounds (1–10)

[anthropic]
api_key = "sk-ant-..."    # required for research and script generation

[gemini]
api_key = ""              # optional; falls back to GOOGLE_API_KEY env var

[elevenlabs]
api_key = ""              # only needed if tts = "elevenlabs"

[google_cloud]
credentials_path = "~/.config/gcloud/application_default_credentials.json"

[podclaw]
api_key = ""
show_id = 0

[local]
output_dir = "~/debcast-episodes"
rss_path   = "~/debcast-episodes/feed.xml"
```

## Design notes

- `@lru_cache` means config is read once per process. `reset_config_cache()` lets tests swap the config file between test cases.
- **No API key validation at config-load time.** `AnthropicConfig.api_key` is allowed to be empty. Validation happens in `ClaudeResearchProvider.__init__` and `ClaudeScriptProvider.__init__` — only when a provider that actually needs the key is constructed. This means `debcast --list`, the local-only hosting path, and all offline unit tests work without a configured key.
- `env_nested_delimiter="__"` lets env vars reach nested config sections: `DEBCAST_RESEARCH__ROUNDS=5` overrides `config.research.rounds`.
- `settings_customise_sources` returns both `EnvSettingsSource` (higher priority) and `TomlConfigSettingsSource` (lower priority). Without the env source, `DEBCAST_*` overrides would be silently ignored.
- `env_prefix="DEBCAST_"` avoids collisions with other tools' env vars.

## CLI integration

The pipeline always calls `get_config()`. CLI flags that override config (e.g. `--tts elevenlabs`) should use `model_copy` rather than mutating the global config:

```python
# cli.py pattern
cfg = get_config().model_copy(
    update={"providers": cfg.providers.model_copy(update={"tts": tts_override})}
)
```

## Testing

```python
# tests/test_config.py
from pathlib import Path
from unittest.mock import patch
import pytest
from debcast.config import Config, reset_config_cache


def test_defaults_load_without_config_file():
    """Config loads with defaults even if no TOML file exists."""
    reset_config_cache()
    with patch("debcast.config.CONFIG_PATH", new=Path("/nonexistent")):
        cfg = Config()
    assert cfg.research.rounds == 3
    assert cfg.anthropic.api_key == ""   # empty, not an error at load time


def test_api_key_from_toml(tmp_path):
    toml = tmp_path / "config.toml"
    toml.write_text('[anthropic]\napi_key = "sk-ant-test"')
    with patch("debcast.config.CONFIG_PATH", new=toml):
        cfg = Config()
    assert cfg.anthropic.api_key == "sk-ant-test"


def test_env_override_takes_priority(tmp_path, monkeypatch):
    toml = tmp_path / "config.toml"
    toml.write_text('[research]\nrounds = 3')
    monkeypatch.setenv("DEBCAST_RESEARCH__ROUNDS", "7")
    with patch("debcast.config.CONFIG_PATH", new=toml):
        cfg = Config()
    assert cfg.research.rounds == 7
```
