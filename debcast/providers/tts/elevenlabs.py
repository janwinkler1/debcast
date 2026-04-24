from __future__ import annotations

from elevenlabs import ElevenLabs

from debcast.types import AudioArtifact, Script
from debcast.utils.audio import stitch_audio_segments

VOICE_ID_A = "zGjIP4SZlMnY9m93k97r"  # Hope
VOICE_ID_B = "6fZce9LFNG3iEITDfqZZ"  # Charlotte
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
