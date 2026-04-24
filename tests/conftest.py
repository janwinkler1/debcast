import pytest

from debcast.config import get_config
from debcast.types import Argument, ResearchResult, ResearchRound, Script, Source, Turn


@pytest.fixture
def sample_arguments():
    return [
        Argument(
            text=f"argument {i}",
            sources=(Source(url=f"https://source{i}.com"),),
        )
        for i in range(5)
    ]


@pytest.fixture
def sample_research(sample_arguments):
    r = ResearchRound(1, pro=tuple(sample_arguments), con=tuple(sample_arguments))
    return ResearchResult.from_rounds("remote work", [r])


@pytest.fixture
def sample_script():
    turns = (
        Turn("A", "Remote work improves work-life balance."),
        Turn("B", "Remote work can lead to isolation."),
        Turn("A", "Studies show productivity increases."),
        Turn("B", "But collaboration suffers."),
    )
    return Script(topic="remote work", turns=turns)


@pytest.fixture
def anthropic_api_key():
    key = get_config().anthropic.api_key
    if not key:
        pytest.skip("anthropic.api_key is required for this integration test")
    return key


@pytest.fixture
def gemini_api_key():
    key = get_config().gemini.api_key
    if not key:
        pytest.skip("gemini.api_key is required for this integration test")
    return key
