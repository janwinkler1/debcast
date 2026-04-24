from __future__ import annotations

import io

import requests

from debcast.types import AudioArtifact, Episode, PublishResult

PODCLAW_BASE_URL = "https://api.podclaw.com"


class PodClawHostingProvider:
    def __init__(self, api_key: str, show_id: int) -> None:
        if not api_key:
            raise ValueError("podclaw.api_key is required when hosting = 'podclaw'")
        if not show_id:
            raise ValueError("podclaw.show_id is required when hosting = 'podclaw'")
        self._api_key = api_key
        self._show_id = show_id
        self._headers = {"Authorization": f"Bearer {self._api_key}"}

    def publish(self, episode: Episode) -> PublishResult:
        audio_url = self._upload_audio(episode.audio)
        return self._create_episode(episode, audio_url)

    def _upload_audio(self, audio: AudioArtifact) -> str:
        resp = requests.post(
            f"{PODCLAW_BASE_URL}/api/v1/shows/{self._show_id}/audio",
            headers=self._headers,
            files={
                "file": (
                    f"episode.{audio.format}",
                    io.BytesIO(audio.data),
                    audio.mime_type,
                )
            },
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json()["audio_url"]

    def _create_episode(self, episode: Episode, audio_url: str) -> PublishResult:
        resp = requests.post(
            f"{PODCLAW_BASE_URL}/api/v1/shows/{self._show_id}/episodes",
            headers={**self._headers, "Content-Type": "application/json"},
            json={
                "title": episode.title,
                "description": episode.description,
                "audio_url": audio_url,
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        return PublishResult(
            feed_url=data["feed_url"],
            episode_url=data.get("episode_url", audio_url),
        )
