import json
from unittest.mock import MagicMock

import pytest

from debcast.providers.script.claude import ClaudeScriptProvider, _format_args
from debcast.types import Argument, ResearchResult, ResearchRound, Script, Source, Turn


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
    assert isinstance(script.turns, tuple)


def test_parse_strips_markdown_fences():
    turns = [{"speaker": "A", "text": "intro"}]
    raw = "```json\n" + json.dumps(turns) + "\n```"
    provider = ClaudeScriptProvider.__new__(ClaudeScriptProvider)
    script = provider._parse_script("topic", raw)
    assert len(script.turns) == 1


def test_parse_extracts_json_array_from_wrapped_text():
    turns = [{"speaker": "A", "text": "intro"}]
    raw = f"Here is your script:\n{json.dumps(turns)}\nThanks!"
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
    assert result.count("\n") == 4


def test_format_args_includes_source_url():
    args = [Argument(text="arg", sources=(Source(url="https://example.com"),))]
    result = _format_args(args)
    assert "https://example.com" in result


def test_full_text_property():
    script = Script(
        topic="t",
        turns=(Turn("A", "hello"), Turn("B", "world")),
    )
    assert "[A] hello" in script.full_text
    assert "[B] world" in script.full_text


def test_constructor_rejects_empty_key():
    with pytest.raises(ValueError, match="api_key is required"):
        ClaudeScriptProvider(api_key="")


@pytest.mark.integration
def test_real_generation(anthropic_api_key):
    provider = ClaudeScriptProvider(api_key=anthropic_api_key)
    research = make_research("nuclear energy", n_args=5)
    script = provider.generate(research)
    assert len(script.turns) >= 10
    assert script.topic == "nuclear energy"
