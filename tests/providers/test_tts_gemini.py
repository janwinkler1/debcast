from unittest.mock import MagicMock, patch

import pytest

from debcast.providers.tts.gemini import GeminiTTSProvider
from debcast.types import AudioArtifact, Script, Turn


def make_script(n_turns: int = 4) -> Script:
    speakers = ["A", "B"] * (n_turns // 2)
    turns = tuple(Turn(speaker=s, text=f"Turn {i}.") for i, s in enumerate(speakers))
    return Script(topic="test", turns=turns)


def test_synthesize_calls_api_once_and_converts_to_mp3():
    fake_wav = b"RIFF\x00\x00\x00\x00WAVEfmt " + b"\x00" * 100

    mock_part = MagicMock()
    mock_part.inline_data.data = fake_wav
    mock_part.inline_data.mime_type = "audio/wav"
    mock_candidate = MagicMock()
    mock_candidate.content.parts = [mock_part]
    mock_response = MagicMock()
    mock_response.candidates = [mock_candidate]

    with patch("google.genai.Client") as MockClient:
        instance = MockClient.return_value
        instance.models.generate_content.return_value = mock_response

        provider = GeminiTTSProvider(api_key="fake-key")
        with patch.object(
            provider,
            "_to_mp3",
            return_value=AudioArtifact(b"mp3", "audio/mpeg", "mp3"),
        ) as mock_convert:
            result = provider.synthesize(make_script())

    instance.models.generate_content.assert_called_once()
    mock_convert.assert_called_once_with(fake_wav, "audio/wav")
    assert result.format == "mp3"


@pytest.mark.integration
def test_real_synthesis(gemini_api_key):
    provider = GeminiTTSProvider(api_key=gemini_api_key)
    audio = provider.synthesize(make_script(4))
    assert audio.format == "mp3"
    assert audio.mime_type == "audio/mpeg"
    assert len(audio.data) > 1000
