from __future__ import annotations

import io
from typing import TYPE_CHECKING

from debcast.types import AudioArtifact

if TYPE_CHECKING:
    from pydub import AudioSegment

PAUSE_MS = 500


def stitch_audio_segments(segments: list[AudioArtifact]) -> AudioArtifact:
    if not segments:
        raise ValueError("No audio segments to stitch")
    audio_segment = _audio_segment_class()
    combined = audio_segment.empty()
    pause = audio_segment.silent(duration=PAUSE_MS)
    for i, seg in enumerate(segments):
        track = _load_segment(seg)
        combined += track
        if i < len(segments) - 1:
            combined += pause
    buf = io.BytesIO()
    combined.export(buf, format="mp3")
    return AudioArtifact(data=buf.getvalue(), mime_type="audio/mpeg", format="mp3")


def pcm_to_mp3(
    pcm_data: bytes, sample_rate: int = 24000, channels: int = 1
) -> AudioArtifact:
    audio_segment = _audio_segment_class()
    seg = audio_segment(
        data=pcm_data,
        sample_width=2,
        frame_rate=sample_rate,
        channels=channels,
    )
    buf = io.BytesIO()
    seg.export(buf, format="mp3")
    return AudioArtifact(data=buf.getvalue(), mime_type="audio/mpeg", format="mp3")


def wav_to_mp3(wav_data: bytes) -> AudioArtifact:
    audio_segment = _audio_segment_class()
    seg = audio_segment.from_wav(io.BytesIO(wav_data))
    buf = io.BytesIO()
    seg.export(buf, format="mp3")
    return AudioArtifact(data=buf.getvalue(), mime_type="audio/mpeg", format="mp3")


def _load_segment(artifact: AudioArtifact) -> AudioSegment:
    if artifact.format not in {"mp3", "wav"}:
        raise ValueError(f"Unsupported audio format for stitching: {artifact.format!r}")

    audio_segment = _audio_segment_class()
    buf = io.BytesIO(artifact.data)
    if artifact.format == "mp3":
        return audio_segment.from_mp3(buf)
    if artifact.format == "wav":
        return audio_segment.from_wav(buf)
    raise ValueError(f"Unsupported audio format for stitching: {artifact.format!r}")


def _audio_segment_class() -> type[AudioSegment]:
    from pydub import AudioSegment

    return AudioSegment
