# Implementation Plan: Script Provider — Claude

**File:** `debcast/providers/script/claude.py`

> **Claude only.** Script generation always uses the Anthropic API. `ScriptProvider` is a protocol for testability (mock injection), not for LLM provider swapping. No other LLM will be added here.

## Purpose

Take a `ResearchResult` (all accumulated pro/con arguments) and generate a realistic, engaging debate script as a `Script` object. Uses Claude with a structured output prompt. No web search needed here — all research is already done.

## Complete implementation

```python
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
    """Format arguments for the prompt, capping at max_args to stay within context."""
    selected = args[:max_args]
    lines = []
    for i, arg in enumerate(selected, 1):
        # Include first source URL if available — helps Claude cite facts accurately
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
        """Parse JSON turn array from Claude's response."""
        # Strip markdown code fences if Claude included them despite instructions
        text = re.sub(r"```(?:json)?\n?", "", raw).strip()
        data = json.loads(text)
        turns = tuple(
            Turn(speaker=item["speaker"], text=item["text"])
            for item in data
            if item.get("speaker") in ("A", "B") and item.get("text")
        )
        if not turns:
            raise ValueError(f"Script parser got 0 valid turns from response:\n{raw[:500]}")
        return Script(topic=topic, turns=turns)
```

## Design notes

- `SCRIPT_MODEL = "claude-sonnet-4-6"` — a step up from the cheaper research model. Script quality is the most user-visible output; better reasoning here pays off more than in research.
- JSON output format was chosen over free-text parsing because it's unambiguous and Claude is reliable at it. The regex stripping handles the one common failure mode (markdown fences).
- `_format_args` caps at 15 arguments per side. With 3 rounds × 5 args = 15 args per side, this means all arguments fit in one request. If `research_rounds` is bumped high, earlier rounds may be truncated, which is acceptable — the debate script doesn't need to cover every argument.
- Including source URLs in the prompt is optional but helps Claude cite facts accurately rather than paraphrasing.
- No streaming — we need the full response to parse JSON.
- `_parse_script` raises `ValueError` on empty output so the pipeline can surface a clear error rather than publishing a silent empty episode.

## Prompt strategy

The system prompt asks for JSON array output explicitly. This produces reliable structured output without needing Anthropic's structured output / tool-use JSON mode, which would add complexity. The user prompt includes:
1. Topic
2. Formatted arguments for each side (with source URLs)
3. Specific format and length guidelines
4. Turn count target (20–30 turns ≈ 15 min at ~40 words/turn × 2s/word)

## Test plan

```python
# tests/test_script_generator.py

import json
from unittest.mock import MagicMock
import pytest
from debcast.providers.script.claude import ClaudeScriptProvider, _format_args
from debcast.types import Argument, ResearchResult, ResearchRound, Script, Turn


def make_research(topic: str = "remote work", n_args: int = 3) -> ResearchResult:
    args = tuple(Argument(text=f"arg {i}") for i in range(n_args))
    round_ = ResearchRound(round=1, pro=args, con=args)
    return ResearchResult.from_rounds(topic, [round_])


def make_mock_client(turns: list[dict]) -> MagicMock:
    block = MagicMock()
    block.text = json.dumps(turns)
    msg = MagicMock()
    msg.content = [block]
    client = MagicMock()
    client.messages.create.return_value = msg
    return client


def test_parse_valid_json():
    turns = [{"speaker": "A", "text": "Hello"}, {"speaker": "B", "text": "Hi there"}]
    provider = ClaudeScriptProvider.__new__(ClaudeScriptProvider)
    provider._client = make_mock_client(turns)
    research = make_research()
    script = provider.generate(research)
    assert len(script.turns) == 2
    assert script.turns[0].speaker == "A"
    assert script.turns[1].text == "Hi there"
    assert isinstance(script.turns, tuple)  # frozen Script uses tuple


def test_parse_strips_markdown_fences():
    turns = [{"speaker": "A", "text": "intro"}]
    raw = "```json\n" + json.dumps(turns) + "\n```"
    provider = ClaudeScriptProvider.__new__(ClaudeScriptProvider)
    script = provider._parse_script("topic", raw)
    assert len(script.turns) == 1


def test_parse_filters_invalid_speakers():
    turns = [
        {"speaker": "A", "text": "valid"},
        {"speaker": "C", "text": "invalid speaker — dropped"},
        {"speaker": "B", "text": "also valid"},
    ]
    provider = ClaudeScriptProvider.__new__(ClaudeScriptProvider)
    script = provider._parse_script("topic", json.dumps(turns))
    assert len(script.turns) == 2


def test_parse_raises_on_empty():
    provider = ClaudeScriptProvider.__new__(ClaudeScriptProvider)
    with pytest.raises(ValueError, match="0 valid turns"):
        provider._parse_script("topic", json.dumps([]))


def test_format_args_caps_at_limit():
    args = [Argument(text=f"arg {i}") for i in range(20)]
    result = _format_args(args, max_args=5)
    assert result.count("\n") == 4  # 5 lines = 4 newlines


def test_full_text_property():
    script = Script(
        topic="t",
        turns=(Turn("A", "hello"), Turn("B", "world")),
    )
    assert "[A] hello" in script.full_text
    assert "[B] world" in script.full_text


@pytest.mark.integration
def test_real_generation():
    from debcast.config import get_config
    cfg = get_config()
    provider = ClaudeScriptProvider(api_key=cfg.anthropic.api_key)
    research = make_research("nuclear energy", n_args=5)
    script = provider.generate(research)
    assert len(script.turns) >= 10
    assert script.topic == "nuclear energy"
```
