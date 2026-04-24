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
            "sources": [
                {"url": "https://iea.org/nuclear", "title": "IEA", "snippet": "..."}
            ],
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
    assert args[1].sources == ()


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
def test_real_research_call(anthropic_api_key):
    provider = ClaudeResearchProvider(api_key=anthropic_api_key)
    args = provider.research("remote work", "pro")
    assert len(args) >= 1
    assert all(isinstance(a, Argument) for a in args)
    assert all(isinstance(s, Source) for a in args for s in a.sources)
