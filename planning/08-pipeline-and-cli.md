# Implementation Plan: Pipeline and CLI

**Files:**

- `debcast/pipeline.py`
- `debcast/cli.py`

______________________________________________________________________

## Pipeline

**File:** `debcast/pipeline.py`

The pipeline is the single place where providers are instantiated, the stages are called in order, and progress is displayed. It knows about config but doesn't import from CLI.

### Complete implementation

```python
from __future__ import annotations
from dataclasses import dataclass

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from debcast.config import Config
from debcast.research_loop import run_research_loop
from debcast.types import Episode, ResearchResult, Script

console = Console()


@dataclass
class RunOptions:
    """CLI-level overrides applied on top of config."""
    topic: str
    tts_override: str | None = None
    hosting_override: str | None = None
    research_rounds_override: int | None = None
    dry_run: bool = False


def run(options: RunOptions, cfg: Config) -> str:
    """Execute the full pipeline. Returns the published feed URL or RSS path."""
    tts_name = options.tts_override or cfg.providers.tts
    hosting_name = options.hosting_override or cfg.providers.hosting
    rounds = options.research_rounds_override or cfg.research.rounds

    research_provider = _build_research_provider(cfg)
    script_provider = _build_script_provider(cfg)

    # --- Stage 1: Research ---
    with _spinner(f"Researching '{options.topic}' ({rounds} rounds)…"):
        research = run_research_loop(
            topic=options.topic,
            provider=research_provider,
            rounds=rounds,
        )
    console.print(f"[green]✓[/green] Research complete — {len(research.pro)} pro args, {len(research.con)} con args")

    # --- Stage 2: Script ---
    with _spinner("Generating debate script…"):
        script = script_provider.generate(research)
    console.print(f"[green]✓[/green] Script ready — {len(script.turns)} turns")

    if options.dry_run:
        console.print("\n[bold]--- SCRIPT (dry run) ---[/bold]")
        console.print(script.full_text)
        return "(dry run — no audio produced)"

    # --- Stage 3: TTS ---
    tts_provider = _build_tts_provider(tts_name, cfg)
    with _spinner(f"Synthesizing audio via {tts_name}…"):
        audio = tts_provider.synthesize(script)
    console.print(f"[green]✓[/green] Audio ready — {len(audio) // 1024} KB")

    # --- Stage 4: Publish ---
    episode = _build_episode(options.topic, script, audio, research)
    hosting_provider = _build_hosting_provider(hosting_name, cfg)
    with _spinner(f"Publishing via {hosting_name}…"):
        feed_url = hosting_provider.publish(episode)
    console.print(f"[green]✓[/green] Published: {feed_url}")

    return feed_url


def _spinner(msg: str):
    return Progress(SpinnerColumn(), TextColumn(msg), transient=True)


def _build_episode(topic: str, script: Script, audio: bytes, research: ResearchResult) -> Episode:
    sources = sorted({a.source_url for a in research.pro + research.con if a.source_url})
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
        return GoogleCloudTTSProvider(credentials_path=cfg.google_cloud.credentials_path)
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
        )
    raise ValueError(f"Unknown hosting provider: {name!r}")
```

### Design notes

- Lazy imports inside `_build_*` functions mean optional dependencies (elevenlabs, kokoro, google-cloud) are only imported if that provider is actually selected. A user with only `gemini` installed won't see an ImportError for `elevenlabs`.
- `RunOptions` decouples the CLI from the pipeline — the pipeline doesn't know it came from a CLI. Easier to test and reuse.
- `_spinner` is a thin wrapper around `rich.Progress`. All progress display is in the pipeline; providers are silent.
- `dry_run` short-circuits after script generation — no TTS, no publishing, no API calls to audio or hosting providers.

______________________________________________________________________

## CLI

**File:** `debcast/cli.py`

Thin Typer app. Parses arguments, builds `RunOptions`, calls `pipeline.run`. All logic lives in the pipeline.

### Complete implementation

```python
from __future__ import annotations
from typing import Annotated, Optional

import typer
from rich.console import Console

from debcast.config import get_config
from debcast.pipeline import RunOptions, run

app = typer.Typer(no_args_is_help=True, add_completion=False)
console = Console()


@app.command()
def main(
    topic: Annotated[Optional[str], typer.Argument(help="Debate topic")] = None,
    lucky: Annotated[bool, typer.Option("--lucky", help="Let Claude pick a spicy topic")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Generate script only, no audio")] = False,
    tts: Annotated[Optional[str], typer.Option("--tts", help="TTS provider override")] = None,
    hosting: Annotated[Optional[str], typer.Option("--hosting", help="Hosting provider override")] = None,
    research_rounds: Annotated[Optional[int], typer.Option("--research-rounds", help="Research rounds override")] = None,
    list_episodes: Annotated[bool, typer.Option("--list", help="List recent episodes")] = False,
) -> None:
    cfg = get_config()

    if list_episodes:
        _list_episodes(cfg)
        return

    if lucky:
        topic = _pick_lucky_topic(cfg)
        console.print(f"[bold]Lucky topic:[/bold] {topic}")

    if not topic:
        console.print("[red]Error:[/red] provide a topic or use --lucky")
        raise typer.Exit(1)

    options = RunOptions(
        topic=topic,
        tts_override=tts,
        hosting_override=hosting,
        research_rounds_override=research_rounds,
        dry_run=dry_run,
    )

    try:
        run(options, cfg)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


def _pick_lucky_topic(cfg) -> str:
    """Ask Claude to suggest a debate-worthy topic."""
    import anthropic
    client = anthropic.Anthropic(api_key=cfg.anthropic.api_key)
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",   # fast and cheap for a one-liner
        max_tokens=100,
        messages=[{
            "role": "user",
            "content": (
                "Suggest one spicy, debate-worthy topic for a podcast. "
                "Return only the topic phrase, nothing else. "
                "Examples: 'social media is harmful to democracy', 'universal basic income'"
            ),
        }],
    )
    return response.content[0].text.strip().strip('"')


def _list_episodes(cfg) -> None:
    """Print recently published episodes from the local RSS feed."""
    from pathlib import Path
    import xml.etree.ElementTree as ET

    rss_path = Path(cfg.local.rss_path).expanduser()
    if not rss_path.exists():
        console.print("No episodes found. Run debcast to create your first episode.")
        return

    tree = ET.parse(rss_path)
    items = tree.findall(".//item")
    if not items:
        console.print("No episodes in feed.")
        return

    console.print(f"\n[bold]Recent episodes ({len(items)} total):[/bold]")
    for item in items[:10]:
        title = item.findtext("title", "(untitled)")
        pub_date = item.findtext("pubDate", "")
        console.print(f"  • {title}  [dim]{pub_date}[/dim]")
```

### pyproject.toml entry point

```toml
[project.scripts]
debcast = "debcast.cli:app"
```

### --list limitation

`--list` reads from the local RSS feed only. If `hosting = "podclaw"`, it won't list PodClaw episodes. This is acceptable for now — a future version could query the PodClaw API.

______________________________________________________________________

## Pipeline test plan

```python
# tests/test_pipeline.py

from unittest.mock import MagicMock, patch
import pytest
from debcast.pipeline import RunOptions, run, _build_episode
from debcast.types import Argument, ResearchResult, ResearchRound, Script, Turn


def make_research() -> ResearchResult:
    r = ResearchRound(1, [Argument("pro")], [Argument("con", "http://example.com")])
    return ResearchResult.from_rounds("AI regulation", [r])


def make_script() -> Script:
    return Script("AI regulation", [Turn("A", "Hello"), Turn("B", "Hi")])


def test_dry_run_skips_tts_and_hosting(tmp_path, capsys):
    cfg = MagicMock()
    cfg.providers.tts = "gemini"
    cfg.providers.hosting = "local"
    cfg.research.rounds = 1
    cfg.anthropic.api_key = "fake"

    with (
        patch("debcast.pipeline.run_research_loop", return_value=make_research()),
        patch("debcast.pipeline._build_script_provider") as mock_script_prov,
        patch("debcast.pipeline._build_tts_provider") as mock_tts,
        patch("debcast.pipeline._build_hosting_provider") as mock_hosting,
    ):
        mock_script_prov.return_value.generate.return_value = make_script()
        options = RunOptions(topic="AI regulation", dry_run=True)
        result = run(options, cfg)

    assert result == "(dry run — no audio produced)"
    mock_tts.assert_not_called()
    mock_hosting.assert_not_called()


def test_build_episode_collects_sources():
    research = make_research()  # con arg has source_url
    script = make_script()
    audio = b"\xff\xfb" + b"\x00" * 100
    episode = _build_episode("AI regulation", script, audio, research)
    assert "http://example.com" in episode.sources
    assert episode.title == "Ai Regulation: A Debate"
    assert len(episode.audio) == len(audio)


def test_unknown_tts_provider_raises():
    from debcast.pipeline import _build_tts_provider
    with pytest.raises(ValueError, match="Unknown TTS provider"):
        _build_tts_provider("nonexistent", MagicMock())
```
