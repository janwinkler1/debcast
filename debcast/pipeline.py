from __future__ import annotations

from dataclasses import dataclass

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from debcast.config import Config
from debcast.research_loop import run_research_loop
from debcast.types import AudioArtifact, Episode, ResearchResult, Script

console = Console()


@dataclass
class RunOptions:
    topic: str
    tts_override: str | None = None
    hosting_override: str | None = None
    research_rounds_override: int | None = None
    dry_run: bool = False


def run(options: RunOptions, cfg: Config) -> str:
    """Execute the full pipeline. Returns the published feed URL or a dry-run notice."""
    tts_name = options.tts_override or cfg.providers.tts
    hosting_name = options.hosting_override or cfg.providers.hosting
    rounds = options.research_rounds_override or cfg.research.rounds

    research_provider = _build_research_provider(cfg)
    script_provider = _build_script_provider(cfg)

    research = run_research_loop(
        topic=options.topic,
        provider=research_provider,
        rounds=rounds,
        on_progress=lambda msg: console.print(f"[dim]  {msg}[/dim]"),
    )
    console.print(
        f"[green]✓[/green] Research complete — {len(research.pro)} pro args, "
        f"{len(research.con)} con args"
    )

    with _spinner("Generating debate script…"):
        script = script_provider.generate(research)
    console.print(f"[green]✓[/green] Script ready — {len(script.turns)} turns")

    if options.dry_run:
        console.print("\n[bold]--- SCRIPT (dry run) ---[/bold]")
        console.print(script.full_text)
        return "(dry run — no audio produced)"

    tts_provider = _build_tts_provider(tts_name, cfg)
    with _spinner(f"Synthesizing audio via {tts_name}…"):
        audio = tts_provider.synthesize(script)
    console.print(f"[green]✓[/green] Audio ready — {len(audio.data) // 1024} KB")

    episode = _build_episode(options.topic, script, audio, research)
    hosting_provider = _build_hosting_provider(hosting_name, cfg)
    with _spinner(f"Publishing via {hosting_name}…"):
        result = hosting_provider.publish(episode)
    console.print(f"[green]✓[/green] Published: {result.feed_url}")

    return result.feed_url


def _spinner(msg: str):
    return Progress(SpinnerColumn(), TextColumn(msg), transient=True)


def _build_episode(
    topic: str, script: Script, audio: AudioArtifact, research: ResearchResult
) -> Episode:
    sources = sorted(
        {s.url for a in research.pro + research.con for s in a.sources if s.url}
    )
    return Episode(
        title=f"{topic.title()}: A Debate",
        audio=audio,
        description=_build_description(topic, research, sources),
        sources=sources,
        script=script,
    )


def _build_description(topic: str, research: ResearchResult, sources: list[str]) -> str:
    lines = [
        f"An AI-generated debate on: {topic}",
        "",
        f"Pro arguments researched: {len(research.pro)}",
        f"Con arguments researched: {len(research.con)}",
    ]
    if sources:
        lines += ["", "Sources:"] + [f"- {s}" for s in sources[:10]]
    return "\n".join(lines)


def _build_research_provider(cfg: Config):
    from debcast.providers.research.claude import ClaudeResearchProvider

    return ClaudeResearchProvider(api_key=cfg.anthropic.api_key)


def _build_script_provider(cfg: Config):
    from debcast.providers.script.claude import ClaudeScriptProvider

    return ClaudeScriptProvider(api_key=cfg.anthropic.api_key)


def _build_tts_provider(name: str, cfg: Config):
    if name == "gemini":
        from debcast.providers.tts.gemini import GeminiTTSProvider

        return GeminiTTSProvider(api_key=cfg.gemini.api_key or None)
    if name == "google_cloud":
        from debcast.providers.tts.google_cloud import GoogleCloudTTSProvider

        return GoogleCloudTTSProvider(
            credentials_path=cfg.google_cloud.credentials_path
        )
    if name == "elevenlabs":
        from debcast.providers.tts.elevenlabs import ElevenLabsTTSProvider

        return ElevenLabsTTSProvider(api_key=cfg.elevenlabs.api_key)
    if name == "kokoro":
        from debcast.providers.tts.kokoro import KokoroTTSProvider

        return KokoroTTSProvider()
    raise ValueError(f"Unknown TTS provider: {name!r}")


def _build_hosting_provider(name: str, cfg: Config):
    if name == "local":
        from debcast.providers.hosting.local import LocalHostingProvider

        return LocalHostingProvider(
            output_dir=cfg.local.output_dir,
            rss_path=cfg.local.rss_path,
        )
    if name == "podclaw":
        from debcast.providers.hosting.podclaw import PodClawHostingProvider

        return PodClawHostingProvider(
            api_key=cfg.podclaw.api_key,
            show_id=cfg.podclaw.show_id,
            audio_output_dir=cfg.podclaw.audio_output_dir,
            audio_base_url=cfg.podclaw.audio_base_url,
            s3_bucket=cfg.podclaw.s3_bucket,
            s3_prefix=cfg.podclaw.s3_prefix,
            s3_endpoint_url=cfg.podclaw.s3_endpoint_url,
            s3_region=cfg.podclaw.s3_region,
            s3_access_key_id=cfg.podclaw.s3_access_key_id,
            s3_secret_access_key=cfg.podclaw.s3_secret_access_key,
        )
    raise ValueError(f"Unknown hosting provider: {name!r}")
