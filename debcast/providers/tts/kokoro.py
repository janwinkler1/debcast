from __future__ import annotations

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
        import numpy as np

        segments: list[AudioArtifact] = []
        for turn in script.turns:
            voice = VOICE_A if turn.speaker == "A" else VOICE_B
            samples, sample_rate = self._kokoro.create(
                text=turn.text, voice=voice, speed=1.0, lang="en-us"
            )
            pcm = (samples * 32767).astype(np.int16).tobytes()
            segments.append(pcm_to_mp3(pcm, sample_rate=sample_rate))
        return stitch_audio_segments(segments)
