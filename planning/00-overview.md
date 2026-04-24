# Implementation Plan: Overview

## Goal

Build debcast end-to-end: a CLI tool that takes a topic, researches a Pro and Con side using Claude, generates a debate script, synthesizes audio with two distinct voices, and publishes to a podcast feed.

## Implementation phases

### Phase 1 — Working end-to-end with real providers

**Goal:** get from a topic argument to a playable podcast episode as fast as possible. This is the primary milestone — demonstrating real output with real Anthropic accounts. All real providers are wired; local hosting is used to write the episode to disk for quality verification.

**Unit tests** use mocked providers and run offline. **Integration tests** hit real APIs and run in CI via secrets (see [09-testing-strategy.md](09-testing-strategy.md)).

Already exists:
- `pyproject.toml` (minimal — needs dependencies added, see [10-project-setup.md](10-project-setup.md))
- `README.md` (minimal — good enough for now)
- `main.py` (uv scaffold placeholder — replaced by `debcast/cli.py` as the real entry point)

Files to create:
- `config.example.toml`
- `debcast/__init__.py`
- `debcast/types.py`
- `debcast/config.py`
- `debcast/pipeline.py`
- `debcast/research_loop.py`
- `debcast/cli.py`
- `debcast/providers/__init__.py`
- `debcast/providers/research/__init__.py`
- `debcast/providers/research/claude.py`
- `debcast/providers/script/__init__.py`
- `debcast/providers/script/claude.py`
- `debcast/providers/tts/__init__.py`
- `debcast/providers/tts/gemini.py`
- `debcast/providers/hosting/__init__.py`
- `debcast/providers/hosting/local.py`
- `debcast/utils/__init__.py`
- `debcast/utils/audio.py`

### Phase 2 — Tests

Add the full unit test suite covering Phase 1 code (mocked providers), and integration tests for each real provider. CI must pass before Phase 3.

Files produced:
- `tests/__init__.py`
- `tests/conftest.py`
- `tests/providers/__init__.py`
- `tests/test_research_loop.py`
- `tests/test_script_generator.py`
- `tests/test_pipeline.py`
- `tests/test_config.py`
- `tests/test_audio_utils.py`
- `tests/providers/test_research_claude.py`
- `tests/providers/test_tts_gemini.py`
- `tests/providers/test_hosting_local.py`

### Phase 3 — PodClaw hosting _(out of scope for v0.0.1)_

Wire up PodClaw so episodes can be published to a real podcast feed.

Files produced:
- `debcast/providers/hosting/podclaw.py`

### Phase 4 — Remaining TTS providers

ElevenLabs, Google Cloud TTS, Kokoro. Each is independently shippable.

Files produced:
- `debcast/providers/tts/elevenlabs.py`
- `debcast/providers/tts/google_cloud.py`
- `debcast/providers/tts/kokoro.py`

### Phase 5 — Polish

- `debcast --lucky` (topic generation)
- `debcast --list` (episode history)
- Progress display (rich/typer)
- Expand `README.md` with full setup and provider docs

## Dependency graph

```
types.py
    └── config.py
            └── pipeline.py
                    ├── research_loop.py
                    │       └── providers/research/claude.py
                    ├── providers/script/claude.py
                    ├── providers/tts/<any>
                    │       └── utils/audio.py
                    └── providers/hosting/<any>
cli.py → pipeline.py
```

No circular deps. Each layer only imports from the layer below.

## Key decisions

| Decision | Choice | Rationale |
|---|---|---|
| CLI framework | Typer | type-safe, minimal boilerplate |
| Config | Pydantic Settings + TOML | validation for free, familiar |
| LLM provider | Claude only (Anthropic SDK) | research and script generation are always Claude — no other LLM is supported or planned |
| Sync vs async | sync only | pipeline is sequential; async adds complexity for no gain |
| Audio stitching | pydub | simple, well-known |
| Test isolation | unittest.mock / pytest-mock | no extra infra needed |

### Claude-only LLM constraint

Research and script generation use Claude exclusively. There is no provider abstraction for LLMs — `ResearchProvider` and `ScriptProvider` protocols exist only to make the implementations testable with mocks, not to support swapping in other LLMs. The `providers/research/` and `providers/script/` directories will only ever contain `claude.py`.

## External dependencies (approximate)

```toml
[project]
dependencies = [
  "anthropic>=0.40",
  "typer>=0.12",
  "pydantic-settings>=2.0",
  "pydub>=0.25",
  "rich>=13",
  "google-genai>=0.8",    # Gemini TTS (newer google-genai SDK, not google-generativeai)
]

[project.optional-dependencies]
elevenlabs = ["elevenlabs>=1.0"]
google-cloud-tts = ["google-cloud-texttospeech>=2.0"]
kokoro = ["kokoro-onnx>=0.3"]
```
