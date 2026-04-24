# Implementation Plan: TTS Providers

**Files:**
- `debcast/providers/tts/gemini.py` (default)
- `debcast/providers/tts/google_cloud.py`
- `debcast/providers/tts/elevenlabs.py`
- `debcast/providers/tts/kokoro.py`
- `debcast/utils/audio.py`

All `TTSProvider` implementations return an `AudioArtifact(data, mime_type, format)`. The hosting providers and audio utilities use `mime_type`/`format` to handle the bytes correctly.

---

## Audio utilities

**File:** `debcast/utils/audio.py`

```python
from __future__ import annotations
import io
from pydub import AudioSegment
from debcast.types import AudioArtifact


PAUSE_MS = 500   # silence between turns


def stitch_audio_segments(segments: list[AudioArtifact]) -> AudioArtifact:
    """Concatenate audio segments with a brief pause between each. Returns MP3."""
    if not segments:
        raise ValueError("No audio segments to stitch")
    combined = AudioSegment.empty()
    pause = AudioSegment.silent(duration=PAUSE_MS)
    for i, seg in enumerate(segments):
        track = _load_segment(seg)
        combined += track
        if i < len(segments) - 1:
            combined += pause
    buf = io.BytesIO()
    combined.export(buf, format="mp3")
    return AudioArtifact(data=buf.getvalue(), mime_type="audio/mpeg", format="mp3")


def pcm_to_mp3(pcm_data: bytes, sample_rate: int = 24000, channels: int = 1) -> AudioArtifact:
    """Convert raw 16-bit PCM bytes to MP3."""
    seg = AudioSegment(
        data=pcm_data,
        sample_width=2,           # 16-bit
        frame_rate=sample_rate,
        channels=channels,
    )
    buf = io.BytesIO()
    seg.export(buf, format="mp3")
    return AudioArtifact(data=buf.getvalue(), mime_type="audio/mpeg", format="mp3")


def wav_to_mp3(wav_data: bytes) -> AudioArtifact:
    """Convert WAV bytes to MP3."""
    seg = AudioSegment.from_wav(io.BytesIO(wav_data))
    buf = io.BytesIO()
    seg.export(buf, format="mp3")
    return AudioArtifact(data=buf.getvalue(), mime_type="audio/mpeg", format="mp3")


def _load_segment(artifact: AudioArtifact) -> AudioSegment:
    buf = io.BytesIO(artifact.data)
    if artifact.format == "mp3":
        return AudioSegment.from_mp3(buf)
    if artifact.format == "wav":
        return AudioSegment.from_wav(buf)
    raise ValueError(f"Unsupported audio format for stitching: {artifact.format!r}")
```

`pydub` requires `ffmpeg` on the system path for MP3 encoding/decoding. Document in README.

---

## Gemini 2.5 TTS (default)

**File:** `debcast/providers/tts/gemini.py`

Uses the `google-genai` SDK (`pip install google-genai`) — the newer package, distinct from the older `google-generativeai`. Gemini 2.5 Flash TTS supports multi-speaker synthesis natively; the whole script is sent in one request.

**Audio format note**: Gemini TTS returns raw PCM audio (24 kHz, 16-bit, mono) or WAV. It does **not** return MP3. The provider converts to MP3 before returning.

```python
from __future__ import annotations
import io

from google import genai
from google.genai import types
from pydub import AudioSegment

from debcast.types import AudioArtifact, Script
from debcast.utils.audio import pcm_to_mp3, wav_to_mp3


VOICE_A = "Aoede"   # Host A (pro)
VOICE_B = "Puck"    # Host B (con)
# Future: make voice assignment randomizable per episode so hosts don't always sound the same.
MODEL = "gemini-2.5-flash-preview-tts"


class GeminiTTSProvider:
    def __init__(self, api_key: str | None = None) -> None:
        # api_key=None falls back to GOOGLE_API_KEY env var via the SDK
        self._client = genai.Client(api_key=api_key)

    def synthesize(self, script: Script) -> AudioArtifact:
        script_text = "\n\n".join(
            f"[{t.speaker}]: {t.text}" for t in script.turns
        )

        response = self._client.models.generate_content(
            model=MODEL,
            contents=script_text,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    multi_speaker_voice_config=types.MultiSpeakerVoiceConfig(
                        speaker_voice_configs=[
                            types.SpeakerVoiceConfig(
                                speaker="A",
                                voice_config=types.VoiceConfig(
                                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                        voice_name=VOICE_A
                                    )
                                ),
                            ),
                            types.SpeakerVoiceConfig(
                                speaker="B",
                                voice_config=types.VoiceConfig(
                                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                        voice_name=VOICE_B
                                    )
                                ),
                            ),
                        ]
                    )
                ),
            ),
        )

        part = response.candidates[0].content.parts[0]
        raw: bytes = part.inline_data.data          # SDK decodes base64 for us
        mime: str = part.inline_data.mime_type       # e.g. "audio/wav" or "audio/pcm;rate=24000"

        return self._to_mp3(raw, mime)

    def _to_mp3(self, audio_data: bytes, mime_type: str) -> AudioArtifact:
        if audio_data[:4] == b"RIFF" or "wav" in mime_type:
            return wav_to_mp3(audio_data)
        # Raw PCM: Gemini outputs 24 kHz, 16-bit, mono
        return pcm_to_mp3(audio_data, sample_rate=24000, channels=1)
```

**SDK note**: `google-genai` is the replacement for `google-generativeai`. Import path is `from google import genai`. The `genai.Client` constructor accepts `api_key` directly; if `None`, the SDK reads `GOOGLE_API_KEY` from the environment. Verify the exact `types.*` class names against the installed SDK version before implementing — the preview API surface may shift.

---

## Google Cloud TTS

**File:** `debcast/providers/tts/google_cloud.py`

Google Cloud TTS does not support multi-speaker synthesis. Strategy: synthesize each turn separately, then stitch with `stitch_audio_segments`.

```python
from __future__ import annotations
import os
from pathlib import Path

from google.cloud import texttospeech

from debcast.types import AudioArtifact, Script
from debcast.utils.audio import stitch_audio_segments


VOICE_A = texttospeech.VoiceSelectionParams(
    language_code="en-US",
    name="en-US-Wavenet-D",   # Male
)
VOICE_B = texttospeech.VoiceSelectionParams(
    language_code="en-US",
    name="en-US-Wavenet-F",   # Female
)
AUDIO_CONFIG = texttospeech.AudioConfig(
    audio_encoding=texttospeech.AudioEncoding.MP3,
    speaking_rate=1.05,
)


class GoogleCloudTTSProvider:
    def __init__(self, credentials_path: str | None = None) -> None:
        if credentials_path:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(
                Path(credentials_path).expanduser()
            )
        self._client = texttospeech.TextToSpeechClient()

    def synthesize(self, script: Script) -> AudioArtifact:
        segments: list[AudioArtifact] = []
        for turn in script.turns:
            voice = VOICE_A if turn.speaker == "A" else VOICE_B
            response = self._client.synthesize_speech(
                input=texttospeech.SynthesisInput(text=turn.text),
                voice=voice,
                audio_config=AUDIO_CONFIG,
            )
            segments.append(
                AudioArtifact(
                    data=response.audio_content,
                    mime_type="audio/mpeg",
                    format="mp3",
                )
            )
        return stitch_audio_segments(segments)
```

---

## ElevenLabs TTS

**File:** `debcast/providers/tts/elevenlabs.py`

```python
from __future__ import annotations
from elevenlabs import ElevenLabs
from debcast.types import AudioArtifact, Script
from debcast.utils.audio import stitch_audio_segments


VOICE_ID_A = "21m00Tcm4TlvDq8ikWAM"   # Rachel
VOICE_ID_B = "AZnzlk1XvdvUeBnXmlld"   # Domi
MODEL_ID = "eleven_multilingual_v2"


class ElevenLabsTTSProvider:
    def __init__(self, api_key: str) -> None:
        self._client = ElevenLabs(api_key=api_key)

    def synthesize(self, script: Script) -> AudioArtifact:
        segments: list[AudioArtifact] = []
        for turn in script.turns:
            voice_id = VOICE_ID_A if turn.speaker == "A" else VOICE_ID_B
            audio_gen = self._client.text_to_speech.convert(
                voice_id=voice_id,
                text=turn.text,
                model_id=MODEL_ID,
                output_format="mp3_44100_128",
            )
            segments.append(
                AudioArtifact(
                    data=b"".join(audio_gen),
                    mime_type="audio/mpeg",
                    format="mp3",
                )
            )
        return stitch_audio_segments(segments)
```

**Cost note:** ElevenLabs free tier is 10K chars/month. A 15-min script (~15K chars) exceeds that.

---

## Kokoro (local, CPU)

**File:** `debcast/providers/tts/kokoro.py`

```python
from __future__ import annotations
import numpy as np
from debcast.types import AudioArtifact, Script
from debcast.utils.audio import pcm_to_mp3, stitch_audio_segments


VOICE_A = "af_bella"
VOICE_B = "am_adam"


class KokoroTTSProvider:
    def __init__(self) -> None:
        try:
            from kokoro_onnx import Kokoro
        except ImportError:
            raise ImportError(
                "kokoro-onnx is not installed. Install with: pip install debcast[kokoro]"
            )
        self._kokoro = Kokoro("kokoro-v0_19.onnx", "voices.bin")

    def synthesize(self, script: Script) -> AudioArtifact:
        segments: list[AudioArtifact] = []
        for turn in script.turns:
            voice = VOICE_A if turn.speaker == "A" else VOICE_B
            samples, sample_rate = self._kokoro.create(
                text=turn.text, voice=voice, speed=1.0, lang="en-us"
            )
            pcm = (samples * 32767).astype(np.int16).tobytes()
            segments.append(pcm_to_mp3(pcm, sample_rate=sample_rate))
        return stitch_audio_segments(segments)
```

---

## Test plan

```python
# tests/providers/test_tts_gemini.py

from unittest.mock import MagicMock, patch
import pytest
from debcast.providers.tts.gemini import GeminiTTSProvider
from debcast.types import Script, Turn, AudioArtifact


def make_script(n_turns: int = 4) -> Script:
    speakers = ["A", "B"] * (n_turns // 2)
    turns = tuple(Turn(speaker=s, text=f"Turn {i}.") for i, s in enumerate(speakers))
    return Script(topic="test", turns=turns)


def test_synthesize_calls_api_once_and_converts_to_mp3():
    """Gemini sends whole script in one request. Output is converted to MP3."""
    # Simulate WAV response (RIFF header)
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
        # _to_mp3 is tested separately; here we just verify the plumbing
        with patch.object(provider, "_to_mp3", return_value=AudioArtifact(b"mp3", "audio/mpeg", "mp3")) as mock_convert:
            result = provider.synthesize(make_script())

    instance.models.generate_content.assert_called_once()
    mock_convert.assert_called_once_with(fake_wav, "audio/wav")
    assert result.format == "mp3"


@pytest.mark.integration
def test_real_synthesis():
    from debcast.config import get_config
    cfg = get_config()
    provider = GeminiTTSProvider(api_key=cfg.gemini.api_key or None)
    audio = provider.synthesize(make_script(4))
    assert audio.format == "mp3"
    assert audio.mime_type == "audio/mpeg"
    assert len(audio.data) > 1000


# tests/test_audio_utils.py

def test_stitch_raises_on_empty():
    from debcast.utils.audio import stitch_audio_segments
    with pytest.raises(ValueError, match="No audio segments"):
        stitch_audio_segments([])
```
