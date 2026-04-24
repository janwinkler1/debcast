import pytest

from debcast.types import AudioArtifact
from debcast.utils.audio import stitch_audio_segments


def test_stitch_raises_on_empty():
    with pytest.raises(ValueError, match="No audio segments"):
        stitch_audio_segments([])


def test_load_segment_raises_on_unknown_format():
    from debcast.utils.audio import _load_segment

    artifact = AudioArtifact(data=b"", mime_type="audio/ogg", format="ogg")
    with pytest.raises(ValueError, match="Unsupported audio format"):
        _load_segment(artifact)
