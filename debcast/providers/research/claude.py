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
    {"url": "https://...", "title": "page title", "snippet": "excerpt supporting the arg"}
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
        text_block = next(
            (block for block in response.content if block.type == "text"),
            None,
        )
        if not text_block:
            return []

        raw = re.sub(r"```(?:json)?\n?", "", text_block.text).strip()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
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
