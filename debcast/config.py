from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field
from pydantic_settings import (
    BaseSettings,
    EnvSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)

CONFIG_PATH = Path.home() / ".debcast" / "config.toml"


class ProvidersConfig(BaseModel):
    tts: Literal["gemini", "google_cloud", "elevenlabs", "kokoro"] = "gemini"
    hosting: Literal["podclaw", "local"] = "local"


class ResearchConfig(BaseModel):
    rounds: int = Field(default=3, ge=1, le=10)


class AnthropicConfig(BaseModel):
    api_key: str = ""


class ElevenLabsConfig(BaseModel):
    api_key: str = ""


class GoogleCloudConfig(BaseModel):
    credentials_path: str = "~/.config/gcloud/application_default_credentials.json"


class GeminiConfig(BaseModel):
    api_key: str = ""


class PodClawConfig(BaseModel):
    api_key: str = ""
    show_id: int = 0
    audio_output_dir: str = ""
    audio_base_url: str = ""
    s3_bucket: str = ""
    s3_prefix: str = ""
    s3_endpoint_url: str = ""
    s3_region: str = ""
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""


class LocalConfig(BaseModel):
    output_dir: str = "~/debcast-episodes"
    rss_path: str = "~/debcast-episodes/feed.xml"


class Config(BaseSettings):
    model_config = SettingsConfigDict(
        toml_file=str(CONFIG_PATH),
        env_prefix="DEBCAST_",
        env_nested_delimiter="__",
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
        # Read CONFIG_PATH at call time so tests can patch debcast.config.CONFIG_PATH
        import debcast.config as _conf

        return (
            EnvSettingsSource(settings_cls),
            TomlConfigSettingsSource(settings_cls, toml_file=str(_conf.CONFIG_PATH)),
        )


@lru_cache(maxsize=1)
def get_config() -> Config:
    return Config()


def reset_config_cache() -> None:
    get_config.cache_clear()
