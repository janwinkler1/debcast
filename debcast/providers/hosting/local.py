from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

from debcast.types import Episode, PublishResult


class LocalHostingProvider:
    def __init__(self, output_dir: str, rss_path: str) -> None:
        self._output_dir = Path(output_dir).expanduser()
        self._rss_path = Path(rss_path).expanduser()

    def publish(self, episode: Episode) -> PublishResult:
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._rss_path.parent.mkdir(parents=True, exist_ok=True)

        slug = _slugify(episode.title)
        date_str = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        ext = episode.audio.format
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
