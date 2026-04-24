from debcast.providers.hosting.local import LocalHostingProvider, _slugify
from debcast.types import AudioArtifact, Episode


def make_episode(title: str = "Nuclear Energy") -> Episode:
    return Episode(
        title=title,
        audio=AudioArtifact(
            data=b"\xff\xfb" + b"\x00" * 100,
            mime_type="audio/mpeg",
            format="mp3",
        ),
        description="A debate about nuclear energy.",
        sources=["https://example.com"],
    )


def test_publish_writes_audio_file(tmp_path):
    provider = LocalHostingProvider(
        output_dir=str(tmp_path / "episodes"),
        rss_path=str(tmp_path / "feed.xml"),
    )
    result = provider.publish(make_episode())
    mp3_files = list((tmp_path / "episodes").glob("*.mp3"))
    assert len(mp3_files) == 1
    assert mp3_files[0].read_bytes() == make_episode().audio.data
    assert result.local_path is not None
    assert result.feed_url.endswith("feed.xml")


def test_publish_creates_rss(tmp_path):
    provider = LocalHostingProvider(
        output_dir=str(tmp_path / "episodes"),
        rss_path=str(tmp_path / "feed.xml"),
    )
    provider.publish(make_episode("Nuclear Energy"))
    rss = (tmp_path / "feed.xml").read_text()
    assert "Nuclear Energy" in rss
    assert "<enclosure" in rss
    assert "audio/mpeg" in rss


def test_publish_prepends_new_episodes(tmp_path):
    provider = LocalHostingProvider(
        output_dir=str(tmp_path / "episodes"),
        rss_path=str(tmp_path / "feed.xml"),
    )
    provider.publish(make_episode("Episode One"))
    provider.publish(make_episode("Episode Two"))
    rss = (tmp_path / "feed.xml").read_text()
    assert rss.index("Episode Two") < rss.index("Episode One")


def test_episode_url_is_file_uri(tmp_path):
    provider = LocalHostingProvider(
        output_dir=str(tmp_path / "episodes"),
        rss_path=str(tmp_path / "feed.xml"),
    )
    result = provider.publish(make_episode())
    assert result.episode_url.startswith("file://")


def test_publish_handles_existing_rss_without_channel(tmp_path):
    rss_path = tmp_path / "feed.xml"
    rss_path.write_text('<?xml version="1.0"?><rss version="2.0"></rss>')
    provider = LocalHostingProvider(
        output_dir=str(tmp_path / "episodes"),
        rss_path=str(rss_path),
    )
    provider.publish(make_episode())
    rss = rss_path.read_text()
    assert "<channel>" in rss
    assert "Nuclear Energy" in rss


def test_slugify():
    assert _slugify("Nuclear Energy: Pro vs Con!") == "nuclear-energy-pro-vs-con"
    assert _slugify("  spaces  ") == "spaces"
    assert len(_slugify("a" * 100)) <= 60
    assert _slugify("!!!") == "episode"
