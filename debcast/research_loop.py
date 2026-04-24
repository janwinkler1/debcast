from __future__ import annotations

from debcast.types import Argument, ResearchProvider, ResearchResult, ResearchRound


def run_research_loop(
    topic: str,
    provider: ResearchProvider,
    rounds: int,
) -> ResearchResult:
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
        completed.append(
            ResearchRound(round=i, pro=tuple(pro_args), con=tuple(con_args))
        )
        prev_pro = pro_args
        prev_con = con_args

    return ResearchResult.from_rounds(topic, completed)
