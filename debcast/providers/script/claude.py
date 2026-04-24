from __future__ import annotations

import json
import re

import anthropic

from debcast.types import Argument, ResearchResult, Script, Turn

SCRIPT_MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = """You are a podcast script writer specializing in debate formats.
You write scripts for two hosts: Host A (pro position) and Host B (con position).
The debate should feel natural and conversational, not like a formal debate.
Hosts can interrupt, ask clarifying questions, and acknowledge good points from the other side.
Target length: approximately 15 minutes when spoken aloud (about 2000–2500 words total).
Format each turn as JSON: {"speaker": "A" or "B", "text": "..."}
Output a JSON array of these turn objects. No preamble, no markdown, just the JSON array."""

SCRIPT_TEMPLATE = """Write a debate podcast script on the topic: {topic}

HOST A (PRO position) has researched these arguments:
{pro_args}

HOST B (CON position) has researched these arguments:
{con_args}

Guidelines:
- Start with a brief intro from Host A introducing the topic and both positions
- Alternate turns, but allow natural back-and-forth — not strictly A/B/A/B
- Each turn should be 2–5 sentences (not too long, conversational)
- Include at least one moment where a host concedes a minor point
- End with brief closing statements from each host
- Do NOT include music cues, stage directions, or anything that can't be spoken
- Total turns: 20–30

Output format: JSON array of {{"speaker": "A"|"B", "text": "..."}} objects."""


def _format_args(args: list[Argument], max_args: int = 15) -> str:
    selected = args[:max_args]
    lines = []
    for i, arg in enumerate(selected, 1):
        source = f" (source: {arg.sources[0].url})" if arg.sources else ""
        lines.append(f"{i}. {arg.text}{source}")
    return "\n".join(lines)


class ClaudeScriptProvider:
    def __init__(self, api_key: str) -> None:
        if not api_key:
            raise ValueError(
                "anthropic.api_key is required for script generation. "
                "Set it in ~/.debcast/config.toml under [anthropic]."
            )
        self._client = anthropic.Anthropic(api_key=api_key)

    def generate(self, research: ResearchResult) -> Script:
        prompt = SCRIPT_TEMPLATE.format(
            topic=research.topic,
            pro_args=_format_args(research.pro),
            con_args=_format_args(research.con),
        )
        response = self._client.messages.create(
            model=SCRIPT_MODEL,
            max_tokens=8192,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text
        return self._parse_script(research.topic, raw)

    def _parse_script(self, topic: str, raw: str) -> Script:
        text = re.sub(r"```(?:json)?\n?", "", raw).strip()
        data = json.loads(text)
        turns = tuple(
            Turn(speaker=item["speaker"], text=item["text"])
            for item in data
            if item.get("speaker") in ("A", "B") and item.get("text")
        )
        if not turns:
            raise ValueError(
                f"Script parser got 0 valid turns from response:\n{raw[:500]}"
            )
        return Script(topic=topic, turns=turns)
