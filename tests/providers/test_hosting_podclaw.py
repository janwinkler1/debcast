from unittest.mock import MagicMock

import pytest

from debcast.providers.hosting.podclaw import PodClawHostingProvider
from debcast.types import AudioArtifact, Episode


def make_episode(audio_url: str | None = None) -> Episode:
    return Episode(
        title="Nuclear Energy: A Debate",
        audio=AudioArtifact(
            data=b"\xff\xfb" + b"\x00" * 100,
            mime_type="audio/mpeg",
            format="mp3",
        ),
        description="A debate about nuclear energy.",
        sources=["https://example.com"],
        audio_url=audio_url,
    )


def make_session(feed_url: str = "https://podclaw.io/api/shows/7/feed") -> MagicMock:
    response = MagicMock()
    response.json.return_value = {
        "episode": {"id": 42, "status": "published"},
        "feed_url": feed_url,
    }
    session = MagicMock()
    session.post.return_value = response
    return session


def test_requires_credentials():
    with pytest.raises(ValueError, match="api_key"):
        PodClawHostingProvider(api_key="", show_id=7)
    with pytest.raises(ValueError, match="show_id"):
        PodClawHostingProvider(api_key="pc_live_test", show_id=0)


def test_publish_uses_existing_audio_url_without_staging():
    session = make_session()
    audio_url = "https://cdn.example.com/debcast/episode.mp3"
    provider = PodClawHostingProvider(
        api_key="pc_live_test",
        show_id=7,
        session=session,
    )

    result = provider.publish(make_episode(audio_url=audio_url))

    session.post.assert_called_once_with(
        "https://podclaw.io/api/episodes/publish",
        headers={
            "Authorization": "Bearer pc_live_test",
            "Content-Type": "application/json",
        },
        json={
            "show_id": 7,
            "audio_url": audio_url,
            "title": "Nuclear Energy: A Debate",
            "description": "A debate about nuclear energy.",
        },
        timeout=30,
    )
    session.post.return_value.raise_for_status.assert_called_once_with()
    assert result.feed_url == "https://podclaw.io/api/shows/7/feed"
    assert result.episode_url == audio_url
    assert result.local_path is None


def test_publish_stages_audio_and_posts_public_url(tmp_path):
    session = make_session()
    audio_output_dir = tmp_path / "audio"
    provider = PodClawHostingProvider(
        api_key="pc_live_test",
        show_id=7,
        audio_output_dir=str(audio_output_dir),
        audio_base_url="https://cdn.example.com/debcast/",
        session=session,
    )

    result = provider.publish(make_episode())

    staged_files = list(audio_output_dir.glob("*.mp3"))
    assert len(staged_files) == 1
    assert staged_files[0].read_bytes() == make_episode().audio.data
    payload = session.post.call_args.kwargs["json"]
    assert payload["audio_url"].startswith("https://cdn.example.com/debcast/")
    assert payload["audio_url"].endswith(staged_files[0].name)
    assert result.local_path == str(staged_files[0])


def test_publish_uploads_staged_audio_to_s3(tmp_path):
    session = make_session()
    s3_client = MagicMock()
    audio_output_dir = tmp_path / "audio"
    provider = PodClawHostingProvider(
        api_key="pc_live_test",
        show_id=7,
        audio_output_dir=str(audio_output_dir),
        audio_base_url="https://pub.example.com",
        s3_bucket="debcast-audio",
        s3_prefix="episodes",
        s3_client=s3_client,
        session=session,
    )

    result = provider.publish(make_episode())

    staged_files = list(audio_output_dir.glob("episodes/*.mp3"))
    assert len(staged_files) == 1
    object_key = f"episodes/{staged_files[0].name}"
    s3_client.put_object.assert_called_once_with(
        Bucket="debcast-audio",
        Key=object_key,
        Body=make_episode().audio.data,
        ContentType="audio/mpeg",
    )
    payload = session.post.call_args.kwargs["json"]
    assert payload["audio_url"] == f"https://pub.example.com/{object_key}"
    assert result.local_path == str(staged_files[0])


def test_publish_uploads_to_s3_without_local_staging():
    session = make_session()
    s3_client = MagicMock()
    provider = PodClawHostingProvider(
        api_key="pc_live_test",
        show_id=7,
        audio_base_url="https://pub.example.com",
        s3_bucket="debcast-audio",
        s3_client=s3_client,
        session=session,
    )

    result = provider.publish(make_episode())

    s3_client.put_object.assert_called_once()
    payload = session.post.call_args.kwargs["json"]
    assert payload["audio_url"].startswith("https://pub.example.com/")
    assert payload["audio_url"].endswith(".mp3")
    assert result.local_path is None


def test_publish_requires_staging_or_s3_bucket():
    for kwargs in [
        {},
        {"audio_base_url": "https://pub.example.com"},
    ]:
        provider = PodClawHostingProvider(
            api_key="pc_live_test",
            show_id=7,
            session=make_session(),
            **kwargs,
        )
        with pytest.raises(ValueError, match="staged or uploaded"):
            provider.publish(make_episode())


def test_publish_requires_audio_base_url_when_no_s3_bucket(tmp_path):
    provider = PodClawHostingProvider(
        api_key="pc_live_test",
        show_id=7,
        audio_output_dir=str(tmp_path / "audio"),
        session=make_session(),
    )

    with pytest.raises(ValueError, match="audio_base_url"):
        provider.publish(make_episode())


def test_publish_uploads_to_s3_derives_url_from_bucket_and_region():
    session = make_session()
    s3_client = MagicMock()
    provider = PodClawHostingProvider(
        api_key="pc_live_test",
        show_id=7,
        s3_bucket="debcast-audio",
        s3_region="eu-central-1",
        s3_client=s3_client,
        session=session,
    )

    result = provider.publish(make_episode())

    s3_client.put_object.assert_called_once()
    payload = session.post.call_args.kwargs["json"]
    assert payload["audio_url"].startswith(
        "https://debcast-audio.s3.eu-central-1.amazonaws.com/"
    )
    assert payload["audio_url"].endswith(".mp3")
    assert result.local_path is None


def test_publish_requires_audio_base_url_for_custom_s3_endpoint():
    provider = PodClawHostingProvider(
        api_key="pc_live_test",
        show_id=7,
        s3_bucket="debcast-audio",
        s3_endpoint_url="https://abc123.r2.cloudflarestorage.com",
        s3_client=MagicMock(),
        session=make_session(),
    )

    with pytest.raises(ValueError, match="audio_base_url"):
        provider.publish(make_episode())


def test_s3_credentials_must_be_set_together():
    with pytest.raises(ValueError, match="must be set together"):
        PodClawHostingProvider(
            api_key="pc_live_test",
            show_id=7,
            s3_access_key_id="key",
        )


def test_missing_feed_url_raises():
    response = MagicMock()
    response.json.return_value = {"episode": {"id": 42, "status": "published"}}
    session = MagicMock()
    session.post.return_value = response
    provider = PodClawHostingProvider(
        api_key="pc_live_test",
        show_id=7,
        session=session,
    )

    with pytest.raises(ValueError, match="feed_url"):
        provider.publish(make_episode(audio_url="https://cdn.example.com/episode.mp3"))
