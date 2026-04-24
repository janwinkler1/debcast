from __future__ import annotations

import os
from pathlib import Path

from google.cloud import texttospeech

from debcast.types import AudioArtifact, Script
from debcast.utils.audio import stitch_audio_segments

VOICE_A = texttospeech.VoiceSelectionParams(
    language_code="en-US",
    name="en-US-Wavenet-D",
)
VOICE_B = texttospeech.VoiceSelectionParams(
    language_code="en-US",
    name="en-US-Wavenet-F",
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
