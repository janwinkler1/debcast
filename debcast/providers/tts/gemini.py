from __future__ import annotations

from google import genai
from google.genai import types

from debcast.types import AudioArtifact, Script
from debcast.utils.audio import pcm_to_mp3, wav_to_mp3

VOICE_A = "Aoede"
VOICE_B = "Puck"
MODEL = "gemini-2.5-flash-preview-tts"


class GeminiTTSProvider:
    def __init__(self, api_key: str | None = None) -> None:
        self._client = genai.Client(api_key=api_key)

    def synthesize(self, script: Script) -> AudioArtifact:
        script_text = "\n\n".join(f"[{t.speaker}]: {t.text}" for t in script.turns)

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
        raw: bytes = part.inline_data.data
        mime: str = part.inline_data.mime_type

        return self._to_mp3(raw, mime)

    def _to_mp3(self, audio_data: bytes, mime_type: str) -> AudioArtifact:
        if audio_data[:4] == b"RIFF" or "wav" in mime_type:
            return wav_to_mp3(audio_data)
        return pcm_to_mp3(audio_data, sample_rate=24000, channels=1)
