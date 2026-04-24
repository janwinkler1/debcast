from unittest.mock import MagicMock, call

import pytest

from debcast.research_loop import run_research_loop
from debcast.types import Argument, ResearchResult, ResearchRound


def make_args(n: int, prefix: str) -> list[Argument]:
    return [Argument(text=f"{prefix} arg {i}") for i in range(n)]


def test_single_round_no_counter():
    provider = MagicMock()
    provider.research.side_effect = [
        make_args(2, "pro"),
        make_args(2, "con"),
    ]
    result = run_research_loop("nuclear energy", provider, rounds=1)
    assert len(result.rounds) == 1
    assert result.rounds[0].round == 1
    assert len(result.pro) == 2
    assert len(result.con) == 2
    provider.research.assert_any_call(
        topic="nuclear energy", stance="pro", counter_to=None
    )
    provider.research.assert_any_call(
        topic="nuclear energy", stance="con", counter_to=None
    )


def test_multi_round_counter_arguments():
    pro1 = make_args(3, "pro1")
    con1 = make_args(3, "con1")
    pro2 = make_args(2, "pro2")
    con2 = make_args(2, "con2")
    provider = MagicMock()
    provider.research.side_effect = [pro1, con1, pro2, con2]

    result = run_research_loop("AI regulation", provider, rounds=2)

    assert len(result.rounds) == 2
    assert len(result.pro) == 5
    assert len(result.con) == 5

    calls = provider.research.call_args_list
    assert calls[2] == call(topic="AI regulation", stance="pro", counter_to=con1)
    assert calls[3] == call(topic="AI regulation", stance="con", counter_to=pro1)


def test_invalid_rounds():
    provider = MagicMock()
    with pytest.raises(ValueError, match="rounds must be >= 1"):
        run_research_loop("topic", provider, rounds=0)


def test_from_rounds_flattens_correctly():
    r1 = ResearchRound(round=1, pro=(Argument(text="a"),), con=(Argument(text="b"),))
    r2 = ResearchRound(round=2, pro=(Argument(text="c"),), con=(Argument(text="d"),))
    result = ResearchResult.from_rounds("topic", [r1, r2])
    assert [a.text for a in result.pro] == ["a", "c"]
    assert [a.text for a in result.con] == ["b", "d"]


def test_pro_con_are_computed_properties():
    r = ResearchRound(round=1, pro=(Argument(text="p"),), con=(Argument(text="c"),))
    result = ResearchResult.from_rounds("topic", [r])
    assert result.pro[0].text == "p"
    assert result.con[0].text == "c"
