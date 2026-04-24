# Implementation Plan: Testing Strategy

## Philosophy

- Unit tests cover logic branches and require no credentials. They must always pass.
- Integration tests hit real APIs and require credentials in the environment. They must also pass — they run in CI on every PR, gated behind CI secrets. **There is no skip-by-default behavior.**
- No end-to-end tests that run the full pipeline — integration tests at the provider level give sufficient coverage.
- Provider implementations are tested by injecting mock SDK clients; the SDK itself is trusted.

## pytest configuration

```toml
# pyproject.toml
[tool.pytest.ini_options]
testpaths = ["tests"]
markers = [
    "integration: marks tests that require real API credentials",
]
# No addopts skipping integration tests — they run by default.
# In CI, inject API keys via secrets (DEBCAST_ANTHROPIC__API_KEY, etc.)
```

To run only unit tests locally (when you don't have credentials available):
```bash
uv run pytest -m "not integration"
```

To run everything (as CI does):
```bash
uv run pytest
```

## Test file map

| Test file | What it tests | Real API? |
|---|---|---|
| `tests/test_research_loop.py` | `run_research_loop` logic, round indexing, counter_to wiring | No |
| `tests/test_script_generator.py` | JSON parsing, speaker filtering, format edge cases | No |
| `tests/test_pipeline.py` | Stage sequencing, dry_run short-circuit, episode construction | No |
| `tests/test_config.py` | Config loading, defaults, env override, missing file | No |
| `tests/test_audio_utils.py` | `stitch_audio_segments`, `pcm_to_mp3`, `wav_to_mp3` | No |
| `tests/providers/test_research_claude.py` | Prompt building, structured JSON parsing | No + 1 integration |
| `tests/providers/test_tts_gemini.py` | API call structure, PCM→MP3 conversion | No + 1 integration |
| `tests/providers/test_hosting_local.py` | RSS creation, file writes, prepend order, slugify | No |

## Mocking approach

### Anthropic SDK

```python
from unittest.mock import MagicMock
import json

def make_mock_anthropic_client(json_data: list) -> MagicMock:
    block = MagicMock()
    block.type = "text"
    block.text = json.dumps(json_data)
    msg = MagicMock()
    msg.content = [block]
    client = MagicMock()
    client.messages.create.return_value = msg
    return client
```

### Google GenAI (Gemini TTS)

```python
with patch("google.genai.Client") as MockClient:
    instance = MockClient.return_value
    instance.models.generate_content.return_value = mock_response
    ...
```

### Research provider (for pipeline/loop tests)

```python
provider = MagicMock()
provider.research.side_effect = [pro_args_round1, con_args_round1, pro_args_round2, ...]
```

## Fixtures

```python
# tests/conftest.py

import pytest
from debcast.types import Argument, ResearchResult, ResearchRound, Script, Source, Turn


@pytest.fixture
def sample_sources():
    return (Source(url=f"https://source{i}.com", title=f"Source {i}") for i in range(3))


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
```

## CI configuration (GitHub Actions)

```yaml
# .github/workflows/test.yml
name: test
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 # v4.2.2
      - uses: astral-sh/setup-uv@f0b9a6de3f46e0f44b9cfb33d9f63c73b85ab6de # v5.4.2
      - run: uv sync
      - run: uv run pytest
    env:
      DEBCAST_ANTHROPIC__API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
      GOOGLE_API_KEY: ${{ secrets.GOOGLE_API_KEY }}
```

All secrets must be configured in the GitHub repository settings before CI can pass. Integration tests will fail — and block merge — if credentials are missing or expired.

## Coverage targets

Focus coverage effort on:
- `research_loop.py`: 100% — pure logic, no excuse
- `providers/hosting/local.py`: 100% — no API calls, just file I/O
- `providers/research/claude.py` parsing: 100% — the JSON parsing is the tricky part
- `providers/script/claude.py` parsing: 100%
- `pipeline.py`: ~80% — dry_run and main paths covered; TTS/hosting integration covered by provider-level tests
