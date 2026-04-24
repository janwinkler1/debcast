# Implementation Plan: Research Loop

**File:** `debcast/research_loop.py`

## Purpose

Orchestrate N rounds of synced pro/con research. Each round: both sides research independently, then the next round passes each side the opponent's prior-round arguments as `counter_to`. Returns a `ResearchResult` with all rounds and flattened argument lists.

## Algorithm

```
Round 1:
  pro_args_1 = provider.research(topic, "pro", counter_to=None)
  con_args_1 = provider.research(topic, "con", counter_to=None)

Round 2:
  pro_args_2 = provider.research(topic, "pro", counter_to=con_args_1)
  con_args_2 = provider.research(topic, "con", counter_to=pro_args_1)

Round 3:
  pro_args_3 = provider.research(topic, "pro", counter_to=con_args_2)
  con_args_3 = provider.research(topic, "con", counter_to=pro_args_2)

result = ResearchResult.from_rounds(topic, [round1, round2, round3])
```

"Synced" means each round's counter arguments are from the immediately prior round only, not accumulated — this mirrors how a real debate exchange works.

## Complete implementation

```python
from __future__ import annotations

from debcast.types import Argument, ResearchProvider, ResearchResult, ResearchRound


def run_research_loop(
    topic: str,
    provider: ResearchProvider,
    rounds: int,
) -> ResearchResult:
    """Run N synced rounds of pro/con research and return accumulated result."""
    if rounds < 1:
        raise ValueError(f"rounds must be >= 1, got {rounds}")

    completed: list[ResearchRound] = []
    prev_pro: list[Argument] = []
    prev_con: list[Argument] = []

    for i in range(1, rounds + 1):
        pro_args = provider.research(
            topic=topic,
            stance="pro",
            counter_to=prev_con if prev_con else None,
        )
        con_args = provider.research(
            topic=topic,
            stance="con",
            counter_to=prev_pro if prev_pro else None,
        )
        completed.append(ResearchRound(round=i, pro=tuple(pro_args), con=tuple(con_args)))
        prev_pro = pro_args
        prev_con = con_args

    return ResearchResult.from_rounds(topic, completed)
```

## Design notes

- The loop is intentionally sequential (not parallel threads/processes) — the project explicitly rules out async, and the `counter_to` dependency between rounds makes true parallelism moot. Within a single round, pro and con are independent, but the API call time is dominated by the research content, not the round-trip, so parallelism would gain little.
- `prev_con if prev_con else None` converts an empty list to `None` for the first round, keeping the provider API clean (`counter_to=None` means "no counter-arguments yet", not "empty list of counter-arguments").
- The function is pure (no side effects, no I/O beyond delegating to `provider`). Easy to test by injecting a mock provider.
- No progress printing here — that belongs in `pipeline.py` where we have access to the rich console.

## Test plan

**File:** `tests/test_research_loop.py`

```python
from unittest.mock import MagicMock, call
import pytest
from debcast.research_loop import run_research_loop
from debcast.types import Argument, ResearchRound, ResearchResult


def make_args(n: int, prefix: str) -> list[Argument]:
    return [Argument(text=f"{prefix} arg {i}") for i in range(n)]


def test_single_round_no_counter():
    provider = MagicMock()
    provider.research.side_effect = [
        make_args(2, "pro"),   # round 1 pro
        make_args(2, "con"),   # round 1 con
    ]
    result = run_research_loop("nuclear energy", provider, rounds=1)
    assert len(result.rounds) == 1
    assert result.rounds[0].round == 1
    assert len(result.pro) == 2
    assert len(result.con) == 2
    # first round: counter_to must be None for both sides
    provider.research.assert_any_call(topic="nuclear energy", stance="pro", counter_to=None)
    provider.research.assert_any_call(topic="nuclear energy", stance="con", counter_to=None)


def test_multi_round_counter_arguments():
    pro1 = make_args(3, "pro1")
    con1 = make_args(3, "con1")
    pro2 = make_args(2, "pro2")
    con2 = make_args(2, "con2")
    provider = MagicMock()
    provider.research.side_effect = [pro1, con1, pro2, con2]

    result = run_research_loop("AI regulation", provider, rounds=2)

    assert len(result.rounds) == 2
    assert len(result.pro) == 5   # 3 + 2
    assert len(result.con) == 5

    calls = provider.research.call_args_list
    # round 2 pro should get round 1 con as counter_to
    assert calls[2] == call(topic="AI regulation", stance="pro", counter_to=con1)
    # round 2 con should get round 1 pro as counter_to
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
    """pro and con cannot drift from rounds — they are derived, not stored."""
    r = ResearchRound(round=1, pro=(Argument(text="p"),), con=(Argument(text="c"),))
    result = ResearchResult.from_rounds("topic", [r])
    assert result.pro[0].text == "p"
    assert result.con[0].text == "c"
```

All tests are pure unit tests — no I/O, no integration mark needed.
