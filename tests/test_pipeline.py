from unittest.mock import MagicMock, patch

import pytest

from debcast.pipeline import RunOptions, _build_episode, run
from debcast.types import (
    Argument,
    AudioArtifact,
    ResearchResult,
    ResearchRound,
    Script,
    Source,
    Turn,
)


def make_research() -> ResearchResult:
    r = ResearchRound(
        round=1,
        pro=(Argument("pro arg"),),
        con=(Argument("con arg", (Source(url="http://example.com"),)),),
    )
    return ResearchResult.from_rounds("AI regulation", [r])


def make_script() -> Script:
    return Script("AI regulation", (Turn("A", "Hello"), Turn("B", "Hi")))


def make_audio() -> AudioArtifact:
    return AudioArtifact(
        data=b"\xff\xfb" + b"\x00" * 100, mime_type="audio/mpeg", format="mp3"
    )


def test_dry_run_skips_tts_and_hosting():
    cfg = MagicMock()
    cfg.providers.tts = "gemini"
    cfg.providers.hosting = "local"
    cfg.research.rounds = 1
    cfg.anthropic.api_key = "fake"

    with (
        patch("debcast.pipeline.run_research_loop", return_value=make_research()),
        patch("debcast.pipeline._build_script_provider") as mock_script_prov,
        patch("debcast.pipeline._build_tts_provider") as mock_tts,
        patch("debcast.pipeline._build_hosting_provider") as mock_hosting,
    ):
        mock_script_prov.return_value.generate.return_value = make_script()
        options = RunOptions(topic="AI regulation", dry_run=True)
        result = run(options, cfg)

    assert result == "(dry run — no audio produced)"
    mock_tts.assert_not_called()
    mock_hosting.assert_not_called()


def test_build_episode_collects_sources():
    research = make_research()
    script = make_script()
    audio = make_audio()
    episode = _build_episode("AI regulation", script, audio, research)
    assert "http://example.com" in episode.sources
    assert episode.title == "Ai Regulation: A Debate"
    assert episode.audio.data == audio.data


def test_unknown_tts_provider_raises():
    from debcast.pipeline import _build_tts_provider

    with pytest.raises(ValueError, match="Unknown TTS provider"):
        _build_tts_provider("nonexistent", MagicMock())


def test_unknown_hosting_provider_raises():
    from debcast.pipeline import _build_hosting_provider

    with pytest.raises(ValueError, match="Unknown hosting provider"):
        _build_hosting_provider("nonexistent", MagicMock())


def test_build_podclaw_hosting_provider_passes_config():
    from debcast.pipeline import _build_hosting_provider

    cfg = MagicMock()
    cfg.podclaw.api_key = "pc_live_test"
    cfg.podclaw.show_id = 7
    cfg.podclaw.audio_output_dir = "~/debcast-podclaw-audio"
    cfg.podclaw.audio_base_url = "https://cdn.example.com/debcast"
    cfg.podclaw.s3_bucket = "debcast-audio"
    cfg.podclaw.s3_prefix = "episodes"
    cfg.podclaw.s3_endpoint_url = "https://example.r2.cloudflarestorage.com"
    cfg.podclaw.s3_region = "auto"
    cfg.podclaw.s3_access_key_id = "access"
    cfg.podclaw.s3_secret_access_key = "secret"

    with patch("debcast.providers.hosting.podclaw.PodClawHostingProvider") as provider:
        _build_hosting_provider("podclaw", cfg)

    provider.assert_called_once_with(
        api_key="pc_live_test",
        show_id=7,
        audio_output_dir="~/debcast-podclaw-audio",
        audio_base_url="https://cdn.example.com/debcast",
        s3_bucket="debcast-audio",
        s3_prefix="episodes",
        s3_endpoint_url="https://example.r2.cloudflarestorage.com",
        s3_region="auto",
        s3_access_key_id="access",
        s3_secret_access_key="secret",
    )
