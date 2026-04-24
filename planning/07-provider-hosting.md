# Implementation Plan: Hosting Providers

**Files:**

- `debcast/providers/hosting/local.py`
- `debcast/providers/hosting/podclaw.py`

Both implement `HostingProvider.publish(episode: Episode) -> PublishResult`.

______________________________________________________________________

## Local hosting

**File:** `debcast/providers/hosting/local.py`

Writes the audio file to a local directory and maintains an RSS 2.0 feed XML file on disk. No external calls. Works fully offline.

### Honest scope

Local hosting is primarily a **dev and quality verification tool**. The output — an RSS file with `file://` enclosure URLs — can be opened directly in players like VLC, but **will not work with standard podcast apps** (Apple Podcasts, Spotify, Overcast, etc.) because:

- `file://` URLs are not network-accessible
- Podcast apps require HTTP(S) feeds

For a quick podcast-app test, serve the output directory over HTTP:

```bash
cd ~/debcast-episodes && python -m http.server 8080
# Then subscribe to: http://localhost:8080/feed.xml
```

This is intentional: local hosting is phase 1 of the workflow. Verify the episode sounds good locally, then publish to PodClaw for real distribution.

### RSS feed structure

```xml
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
  <channel>
    <title>debcast</title>
    <description>AI-generated debate podcasts</description>
    <link>http://localhost</link>
    <language>en-us</language>
    <item>
      <title>Nuclear Energy: A Debate</title>
      <description>...</description>
      <enclosure url="file:///home/user/debcast-episodes/nuclear-energy-20260424120000.mp3"
                 length="12345678" type="audio/mpeg"/>
      <pubDate>Thu, 24 Apr 2026 12:00:00 +0000</pubDate>
      <guid>nuclear-energy-20260424120000</guid>
    </item>
  </channel>
</rss>
```

### Implementation

```python
from __future__ import annotations
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

from debcast.types import AudioArtifact, Episode, PublishResult


class LocalHostingProvider:
    def __init__(self, output_dir: str, rss_path: str) -> None:
        self._output_dir = Path(output_dir).expanduser()
        self._rss_path = Path(rss_path).expanduser()

    def publish(self, episode: Episode) -> PublishResult:
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._rss_path.parent.mkdir(parents=True, exist_ok=True)

        slug = _slugify(episode.title)
        date_str = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        ext = episode.audio.format   # "mp3", "wav", etc.
        filename = f"{slug}-{date_str}.{ext}"
        audio_path = self._output_dir / filename
        audio_path.write_bytes(episode.audio.data)

        self._upsert_rss(episode, audio_path)
        return PublishResult(
            feed_url=str(self._rss_path),
            episode_url=audio_path.as_uri(),
            local_path=str(audio_path),
        )

    def _upsert_rss(self, episode: Episode, audio_path: Path) -> None:
        if self._rss_path.exists():
            tree = ET.parse(self._rss_path)
            root = tree.getroot()
            channel = root.find("channel")
        else:
            root = ET.Element("rss", version="2.0")
            root.set("xmlns:itunes", "http://www.itunes.com/dtds/podcast-1.0.dtd")
            channel = ET.SubElement(root, "channel")
            ET.SubElement(channel, "title").text = "debcast"
            ET.SubElement(channel, "description").text = "AI-generated debate podcasts"
            ET.SubElement(channel, "link").text = "http://localhost"
            ET.SubElement(channel, "language").text = "en-us"
            tree = ET.ElementTree(root)

        item = ET.Element("item")
        ET.SubElement(item, "title").text = episode.title
        ET.SubElement(item, "description").text = episode.description
        enclosure = ET.SubElement(item, "enclosure")
        enclosure.set("url", audio_path.as_uri())
        enclosure.set("length", str(len(episode.audio.data)))
        enclosure.set("type", episode.audio.mime_type)
        pub_date = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S %z")
        ET.SubElement(item, "pubDate").text = pub_date
        ET.SubElement(item, "guid").text = audio_path.stem

        # Prepend new item (most recent first)
        first_item = channel.find("item")
        if first_item is not None:
            channel.insert(list(channel).index(first_item), item)
        else:
            channel.append(item)

        ET.indent(tree, space="  ")
        tree.write(self._rss_path, encoding="unicode", xml_declaration=True)


def _slugify(title: str) -> str:
    title = title.lower()
    title = re.sub(r"[^\w\s-]", "", title)
    title = re.sub(r"[\s_-]+", "-", title)
    return title.strip("-")[:60]
```

______________________________________________________________________

## PodClaw hosting

**File:** `debcast/providers/hosting/podclaw.py`

PodClaw's current API accepts episode metadata as JSON with a pre-existing
public `audio_url`. It does **not** accept raw audio bytes in the publish
request. Debcast therefore supports three inputs:

1. `Episode.audio_url` is already set by an upstream step.
1. `podclaw.audio_output_dir` and `podclaw.audio_base_url` are configured, so
   debcast writes the generated audio file locally and derives
   `audio_base_url/<filename>`.
1. `podclaw.s3_bucket` and `podclaw.audio_base_url` are configured, so debcast
   uploads the generated audio to S3-compatible storage and derives
   `audio_base_url/<object-key>`.

If only `audio_output_dir` is configured, the user is responsible for serving or
syncing it at `audio_base_url` before podcast apps fetch the RSS enclosure.

```
POST https://podclaw.io/api/episodes/publish
  Authorization: Bearer {api_key}
  Content-Type: application/json
  Body: {
    "show_id": 1,
    "title": "...",
    "description": "...",
    "audio_url": "https://cdn.example.com/episode.mp3"
  }
  → Response: {
    "episode": {"id": 42, "status": "published"},
    "feed_url": "https://podclaw.io/api/shows/1/feed"
  }
```

Verified against PodClaw's public docs on 2026-04-24:

- Publish endpoint: `POST /api/episodes/publish`
- Request fields: `show_id`, `audio_url`, `title`, optional `description`
- Response includes `feed_url`

Implementation notes:

- `PodClawHostingProvider.publish()` resolves a public audio URL, posts to
  `/api/episodes/publish`, and returns `PublishResult(feed_url, episode_url)`.
- If audio is staged locally for a public CDN/static host, `local_path` is set
  to the staged file path for troubleshooting.
- Unit tests mock HTTP calls; real PodClaw calls belong in integration tests
  guarded by API-key secrets.

______________________________________________________________________

## Test plan

```python
# tests/providers/test_hosting_local.py

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


def test_slugify():
    assert _slugify("Nuclear Energy: Pro vs Con!") == "nuclear-energy-pro-vs-con"
    assert _slugify("  spaces  ") == "spaces"
    assert len(_slugify("a" * 100)) <= 60
```
