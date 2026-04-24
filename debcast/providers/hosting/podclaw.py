from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests

from debcast.types import Episode, PublishResult

PODCLAW_BASE_URL = "https://podclaw.io"


class PodClawHostingProvider:
    def __init__(
        self,
        api_key: str,
        show_id: int,
        audio_output_dir: str = "",
        audio_base_url: str = "",
        s3_bucket: str = "",
        s3_prefix: str = "",
        s3_endpoint_url: str = "",
        s3_region: str = "",
        s3_access_key_id: str = "",
        s3_secret_access_key: str = "",
        base_url: str = PODCLAW_BASE_URL,
        session: requests.Session | None = None,
        s3_client: Any | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("podclaw.api_key is required when hosting = 'podclaw'")
        if show_id <= 0:
            raise ValueError("podclaw.show_id is required when hosting = 'podclaw'")
        if bool(s3_access_key_id) != bool(s3_secret_access_key):
            raise ValueError(
                "podclaw.s3_access_key_id and podclaw.s3_secret_access_key "
                "must be set together"
            )

        self._show_id = show_id
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        self._base_url = base_url.rstrip("/")
        self._session = session or requests.Session()
        self._audio_output_dir = (
            Path(audio_output_dir).expanduser() if audio_output_dir else None
        )
        self._audio_base_url = audio_base_url.rstrip("/") if audio_base_url else ""
        self._s3_bucket = s3_bucket
        self._s3_prefix = s3_prefix.strip("/")
        self._s3_endpoint_url = s3_endpoint_url or None
        self._s3_region = s3_region or None
        self._s3_access_key_id = s3_access_key_id or None
        self._s3_secret_access_key = s3_secret_access_key or None
        self._s3_client = s3_client

    def publish(self, episode: Episode) -> PublishResult:
        audio_url, local_path = self._resolve_audio_url(episode)
        return self._publish_episode(
            episode=episode,
            audio_url=audio_url,
            local_path=local_path,
        )

    def _resolve_audio_url(self, episode: Episode) -> tuple[str, str | None]:
        if episode.audio_url:
            return episode.audio_url, None

        if not self._audio_output_dir and not self._s3_bucket:
            raise ValueError(
                "PodClaw requires audio to be staged or uploaded. "
                "Set podclaw.s3_bucket or podclaw.audio_output_dir."
            )

        filename = _audio_filename(episode)
        object_key = _object_key(self._s3_prefix, filename)
        local_path = self._stage_audio(episode, object_key)

        if self._s3_bucket:
            self._upload_audio_object(episode, object_key)
            audio_base_url = self._audio_base_url or self._derive_s3_base_url()
        elif self._audio_base_url:
            audio_base_url = self._audio_base_url
        else:
            raise ValueError(
                "podclaw.audio_base_url is required when serving audio "
                "from audio_output_dir without s3_bucket."
            )

        audio_url = _public_audio_url(audio_base_url, object_key)
        return audio_url, local_path

    def _derive_s3_base_url(self) -> str:
        if self._s3_endpoint_url:
            raise ValueError(
                "podclaw.audio_base_url is required when using a custom "
                "s3_endpoint_url (e.g. Cloudflare R2)."
            )
        if self._s3_region:
            return f"https://{self._s3_bucket}.s3.{self._s3_region}.amazonaws.com"
        return f"https://{self._s3_bucket}.s3.amazonaws.com"

    def _stage_audio(self, episode: Episode, object_key: str) -> str | None:
        if not self._audio_output_dir:
            return None

        audio_path = self._audio_output_dir / object_key
        audio_path.parent.mkdir(parents=True, exist_ok=True)
        audio_path.write_bytes(episode.audio.data)
        return str(audio_path)

    def _upload_audio_object(self, episode: Episode, object_key: str) -> None:
        client = self._get_s3_client()
        client.put_object(
            Bucket=self._s3_bucket,
            Key=object_key,
            Body=episode.audio.data,
            ContentType=episode.audio.mime_type,
        )

    def _get_s3_client(self):
        if self._s3_client is not None:
            return self._s3_client

        try:
            import boto3
        except ImportError as e:
            raise RuntimeError(
                "boto3 is required for podclaw.s3_bucket uploads. "
                "Install project dependencies with `uv sync`."
            ) from e

        kwargs: dict[str, str] = {}
        if self._s3_endpoint_url:
            kwargs["endpoint_url"] = self._s3_endpoint_url
        if self._s3_region:
            kwargs["region_name"] = self._s3_region
        if self._s3_access_key_id:
            kwargs["aws_access_key_id"] = self._s3_access_key_id
            kwargs["aws_secret_access_key"] = self._s3_secret_access_key or ""

        self._s3_client = boto3.client("s3", **kwargs)
        return self._s3_client

    def _publish_episode(
        self,
        episode: Episode,
        audio_url: str,
        local_path: str | None,
    ) -> PublishResult:
        resp = self._session.post(
            f"{self._base_url}/api/episodes/publish",
            headers=self._headers,
            json={
                "show_id": self._show_id,
                "audio_url": audio_url,
                "title": episode.title,
                "description": episode.description,
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        feed_url = data.get("feed_url")
        if not feed_url:
            raise ValueError("PodClaw publish response did not include feed_url")

        published_episode = data.get("episode") or {}
        episode_url = (
            data.get("episode_url")
            or published_episode.get("episode_url")
            or published_episode.get("url")
            or audio_url
        )
        return PublishResult(
            feed_url=feed_url,
            episode_url=episode_url,
            local_path=local_path,
        )


def _audio_filename(episode: Episode) -> str:
    slug = _slugify(episode.title)
    date_str = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
    ext = re.sub(r"[^a-zA-Z0-9]", "", episode.audio.format.lower()) or "mp3"
    return f"{slug}-{date_str}.{ext}"


def _object_key(prefix: str, filename: str) -> str:
    return f"{prefix}/{filename}" if prefix else filename


def _public_audio_url(base_url: str, object_key: str) -> str:
    return f"{base_url.rstrip('/')}/{quote(object_key, safe='/')}"


def _slugify(title: str) -> str:
    title = title.lower()
    title = re.sub(r"[^\w\s-]", "", title)
    title = re.sub(r"[\s_-]+", "-", title)
    slug = title.strip("-")[:60]
    return slug or "episode"
