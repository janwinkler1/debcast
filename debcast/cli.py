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
    lucky: Annotated[
        bool, typer.Option("--lucky", help="Let Claude pick a spicy topic")
    ] = False,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Generate script only, no audio")
    ] = False,
    tts: Annotated[
        Optional[str], typer.Option("--tts", help="TTS provider override")
    ] = None,
    hosting: Annotated[
        Optional[str], typer.Option("--hosting", help="Hosting provider override")
    ] = None,
    research_rounds: Annotated[
        Optional[int],
        typer.Option("--research-rounds", help="Research rounds override"),
    ] = None,
    list_episodes: Annotated[
        bool, typer.Option("--list", help="List recent episodes")
    ] = False,
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
    import anthropic

    client = anthropic.Anthropic(api_key=cfg.anthropic.api_key)
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=100,
        messages=[
            {
                "role": "user",
                "content": (
                    "Suggest one spicy, debate-worthy topic for a podcast. "
                    "Return only the topic phrase, nothing else. "
                    "Examples: 'social media is harmful to democracy', 'universal basic income'"
                ),
            }
        ],
    )
    return response.content[0].text.strip().strip('"')


def _list_episodes(cfg) -> None:
    import xml.etree.ElementTree as ET
    from pathlib import Path

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
