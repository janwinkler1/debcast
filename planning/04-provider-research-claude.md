# Implementation Plan: Research Provider — Claude

**File:** `debcast/providers/research/claude.py`

> **Claude only.** Research always uses the Anthropic API. `ResearchProvider` is a protocol for testability (mock injection), not for LLM provider swapping. No other LLM will be added here.

## Purpose

Implement `ResearchProvider` using the Anthropic API with the built-in `web_search` tool. Given a topic and stance, Claude searches the web and returns a list of `Argument` objects, each with structured `Source` citations.

## Complete implementation

```python
from __future__ import annotations
import json
import re
from typing import Literal

import anthropic

from debcast.types import Argument, Source


RESEARCH_MODEL = "claude-haiku-4-5-20251001"

SYSTEM_PROMPT = """You are a professional debate researcher.
Your job is to find strong, factual arguments for a given position on a topic.
Use the web_search tool to find supporting evidence from credible sources.

Return your findings as a JSON array. Each element must follow this schema exactly:
{
  "text": "the argument in 2-4 sentences",
  "sources": [
    {"url": "https://...", "title": "page title", "snippet": "the specific excerpt that supports the argument"}
  ]
}

Rules:
- Include only arguments supported by credible, verifiable sources
- Each source must have a real URL from your search results
- Return only the JSON array — no preamble, no markdown fences, no trailing text"""

PRO_TEMPLATE = """Research the topic: {topic}

Find the {n} strongest arguments IN FAVOR of this topic.
Focus on facts, statistics, expert opinions, and real-world evidence."""

CON_TEMPLATE = """Research the topic: {topic}

Find the {n} strongest arguments AGAINST this topic.
Focus on facts, statistics, expert opinions, and real-world evidence."""

COUNTER_TEMPLATE = """Research the topic: {topic}

The opposing side has made these arguments:
{counter_args}

Find {n} strong counter-arguments that directly rebut one or more of the points above.
Use facts, statistics, and expert opinions. Be specific about which point you are rebutting."""

ARGUMENTS_PER_ROUND = 5


class ClaudeResearchProvider:
    def __init__(self, api_key: str) -> None:
        if not api_key:
            raise ValueError(
                "anthropic.api_key is required for research. "
                "Set it in ~/.debcast/config.toml under [anthropic]."
            )
        self._client = anthropic.Anthropic(api_key=api_key)

    def research(
        self,
        topic: str,
        stance: Literal["pro", "con"],
        counter_to: list[Argument] | None = None,
    ) -> list[Argument]:
        prompt = self._build_prompt(topic, stance, counter_to)
        response = self._client.messages.create(
            model=RESEARCH_MODEL,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": prompt}],
        )
        return self._parse_response(response)

    def _build_prompt(
        self,
        topic: str,
        stance: Literal["pro", "con"],
        counter_to: list[Argument] | None,
    ) -> str:
        n = ARGUMENTS_PER_ROUND
        if counter_to:
            formatted = "\n".join(f"- {a.text}" for a in counter_to)
            return COUNTER_TEMPLATE.format(topic=topic, counter_args=formatted, n=n)
        if stance == "pro":
            return PRO_TEMPLATE.format(topic=topic, n=n)
        return CON_TEMPLATE.format(topic=topic, n=n)

    def _parse_response(self, response: anthropic.types.Message) -> list[Argument]:
        """Extract structured JSON argument list from the final text block."""
        text_block = next(
            (block for block in response.content if block.type == "text"),
            None,
        )
        if not text_block:
            return []

        # Strip markdown fences if Claude included them despite instructions
        raw = re.sub(r"```(?:json)?\n?", "", text_block.text).strip()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            # Fallback: try to extract a JSON array from somewhere in the text
            match = re.search(r"\[.*\]", raw, re.DOTALL)
            if not match:
                return []
            data = json.loads(match.group())

        arguments = []
        for item in data:
            sources = tuple(
                Source(
                    url=s.get("url", ""),
                    title=s.get("title", ""),
                    snippet=s.get("snippet", ""),
                )
                for s in item.get("sources", [])
                if s.get("url")
            )
            arguments.append(Argument(text=item["text"], sources=sources))
        return arguments
```

## Design notes

- **Versioned tool type**: `"type": "web_search_20250305"` — Anthropic versions their built-in tools. Using the unversioned `"web_search"` type string risks breakage if the API changes. Always pin to the versioned form.
- **Structured JSON output**: The system prompt asks for a JSON array with an explicit schema. This replaces the previous approach of splitting text at blank lines and correlating URLs by position — that approach was brittle because paragraph order doesn't reliably map to search-result order.
- **API key validation in constructor**: Raised here (not at config load time) so offline tests and `--list` work without credentials.
- **Lenient JSON parsing**: If Claude wraps output in markdown fences despite being told not to, the regex strip handles it. The regex fallback for embedded arrays handles rare cases where Claude adds a brief intro sentence before the array.
- `_parse_response` is a separate method to keep it independently testable without making real API calls.
- No retry logic — exceptions propagate to `pipeline.py` for user-facing error display.

## Prompt strategy

- Separate templates for initial research vs. counter-arguments. Counter-argument prompt names the opposing arguments explicitly.
- The system prompt establishes the output schema inline. Repeating it in each user message is not needed — the system prompt is sufficient.
- `ARGUMENTS_PER_ROUND = 5` is a module-level constant. `research_rounds` config controls depth; this constant controls breadth per round.

## Integration with research_loop.py

`ClaudeResearchProvider` is instantiated once in `pipeline.py` and passed to `run_research_loop`. The loop calls `.research()` twice per round.

## Test plan

```python
# tests/providers/test_research_claude.py

import json
from unittest.mock import MagicMock
import pytest
from debcast.providers.research.claude import ClaudeResearchProvider
from debcast.types import Argument, Source


def make_mock_response(json_data: list) -> MagicMock:
    block = MagicMock()
    block.type = "text"
    block.text = json.dumps(json_data)
    msg = MagicMock()
    msg.content = [block]
    return msg


def test_pro_prompt_no_counter():
    provider = ClaudeResearchProvider(api_key="test")
    prompt = provider._build_prompt("nuclear energy", "pro", counter_to=None)
    assert "IN FAVOR" in prompt
    assert "nuclear energy" in prompt
    assert "counter" not in prompt.lower()


def test_con_prompt_no_counter():
    provider = ClaudeResearchProvider(api_key="test")
    prompt = provider._build_prompt("nuclear energy", "con", counter_to=None)
    assert "AGAINST" in prompt


def test_counter_prompt_includes_opposing_args():
    opposing = [
        Argument("Nuclear power is dangerous"),
        Argument("Waste is unsolvable"),
    ]
    provider = ClaudeResearchProvider(api_key="test")
    prompt = provider._build_prompt("nuclear energy", "pro", counter_to=opposing)
    assert "Nuclear power is dangerous" in prompt
    assert "counter" in prompt.lower()


def test_parse_structured_json():
    data = [
        {
            "text": "Nuclear power has a low carbon footprint.",
            "sources": [{"url": "https://iea.org/nuclear", "title": "IEA", "snippet": "..."}],
        },
        {
            "text": "Modern reactors have strong safety records.",
            "sources": [],
        },
    ]
    provider = ClaudeResearchProvider(api_key="test")
    args = provider._parse_response(make_mock_response(data))
    assert len(args) == 2
    assert args[0].text == "Nuclear power has a low carbon footprint."
    assert len(args[0].sources) == 1
    assert args[0].sources[0].url == "https://iea.org/nuclear"
    assert args[0].sources[0].title == "IEA"
    assert args[1].sources == ()   # empty tuple, not None


def test_parse_strips_markdown_fences():
    data = [{"text": "An argument.", "sources": []}]
    block = MagicMock()
    block.type = "text"
    block.text = "```json\n" + json.dumps(data) + "\n```"
    msg = MagicMock()
    msg.content = [block]
    provider = ClaudeResearchProvider(api_key="test")
    args = provider._parse_response(msg)
    assert len(args) == 1


def test_parse_empty_response_returns_empty_list():
    msg = MagicMock()
    msg.content = []
    provider = ClaudeResearchProvider(api_key="test")
    assert provider._parse_response(msg) == []


def test_constructor_rejects_empty_key():
    with pytest.raises(ValueError, match="api_key is required"):
        ClaudeResearchProvider(api_key="")


@pytest.mark.integration
def test_real_research_call():
    """Hits the real Anthropic API."""
    from debcast.config import get_config
    cfg = get_config()
    provider = ClaudeResearchProvider(api_key=cfg.anthropic.api_key)
    args = provider.research("remote work", "pro")
    assert len(args) >= 1
    assert all(isinstance(a, Argument) for a in args)
    assert all(isinstance(s, Source) for a in args for s in a.sources)
```
