# Implementation Plan: Types and Interfaces

**File:** `debcast/types.py`

## Purpose

Single source of truth for all data structures and provider protocols. No logic here — pure type definitions. Every other module imports from here; this file imports nothing from the project.

## Complete implementation

```python
from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Source:
    """One web source that backs an argument."""
    url: str
    title: str = ""
    snippet: str = ""   # relevant excerpt from the page


@dataclass(frozen=True)
class Argument:
    """One researched argument (pro or con)."""
    text: str
    sources: tuple[Source, ...] = ()  # empty for LLM-generated counter-arguments


@dataclass(frozen=True)
class ResearchRound:
    """Output of one synced research round."""
    round: int                  # 1-based
    pro: tuple[Argument, ...]
    con: tuple[Argument, ...]


@dataclass(frozen=True)
class ResearchResult:
    """Accumulated output of all research rounds.

    pro and con are derived from rounds — they are properties, not stored fields,
    so they can never drift out of sync.
    """
    topic: str
    rounds: tuple[ResearchRound, ...]

    @property
    def pro(self) -> list[Argument]:
        return [arg for r in self.rounds for arg in r.pro]

    @property
    def con(self) -> list[Argument]:
        return [arg for r in self.rounds for arg in r.con]

    @classmethod
    def from_rounds(cls, topic: str, rounds: list[ResearchRound]) -> "ResearchResult":
        return cls(topic=topic, rounds=tuple(rounds))


@dataclass(frozen=True)
class Turn:
    """One spoken turn in the debate."""
    speaker: Literal["A", "B"]
    text: str


@dataclass(frozen=True)
class Script:
    """Full debate script, ready for TTS."""
    topic: str
    turns: tuple[Turn, ...]

    @property
    def full_text(self) -> str:
        """Concatenated script for display/debugging."""
        return "\n\n".join(f"[{t.speaker}] {t.text}" for t in self.turns)


@dataclass(frozen=True)
class AudioArtifact:
    """Synthesized audio output from a TTS provider."""
    data: bytes
    mime_type: str   # e.g. "audio/mpeg", "audio/wav"
    format: str      # e.g. "mp3", "wav"


@dataclass(frozen=True)
class PublishResult:
    """Result of publishing an episode."""
    feed_url: str            # RSS feed URL or local file path
    episode_url: str         # direct URL or path of the audio file
    local_path: str | None = None  # set only by local provider


@dataclass
class Episode:
    """Finished episode, ready for publishing."""
    title: str
    audio: AudioArtifact
    description: str
    sources: list[str]       # deduplicated source URLs, may be empty
    script: Script | None = None   # kept for --dry-run / debugging


# ---------------------------------------------------------------------------
# Provider protocols
# ---------------------------------------------------------------------------

@runtime_checkable
class ResearchProvider(Protocol):
    def research(
        self,
        topic: str,
        stance: Literal["pro", "con"],
        counter_to: list[Argument] | None = None,
    ) -> list[Argument]: ...


@runtime_checkable
class ScriptProvider(Protocol):
    def generate(self, research: ResearchResult) -> Script: ...


@runtime_checkable
class TTSProvider(Protocol):
    def synthesize(self, script: Script) -> AudioArtifact: ...


@runtime_checkable
class HostingProvider(Protocol):
    def publish(self, episode: Episode) -> PublishResult: ...
```

## Design notes

- `ResearchProvider` and `ScriptProvider` exist for testability only — mock injection in unit tests. Claude is the sole implementation and no other LLM is planned. `TTSProvider` and `HostingProvider` are genuinely configurable.
- `@runtime_checkable` on all protocols allows `isinstance(obj, ResearchProvider)` checks in tests and the pipeline.
- `ResearchResult` is `frozen=True` and `pro`/`con` are `@property` computed from `rounds`. There is no way for them to drift out of sync because they are never stored independently.
- `Argument.sources: tuple[Source, ...]` replaces the old `source_url: str | None`. An argument may have multiple sources, each with a title and snippet, or no sources at all (e.g. LLM-generated counter-arguments). Using a tuple keeps `Argument` hashable/frozen.
- `AudioArtifact` carries `mime_type` and `format` alongside the raw bytes so downstream code (hosting providers, audio utilities) knows how to handle the data without guessing.
- `PublishResult` is richer than a bare `str`: `feed_url` is the RSS feed, `episode_url` is the direct audio link, and `local_path` is set only by the local provider for display/verification purposes.
- `Episode` is not frozen because it may be constructed incrementally (e.g. `script` added later).
- All types that are constructed by external callers and passed through the pipeline (`Argument`, `ResearchRound`, `ResearchResult`, `Turn`, `Script`, `AudioArtifact`, `PublishResult`) are frozen to prevent accidental mutation.

## Testing

No dedicated test file needed. Types are dataclasses — they're trivially correct. Test `ResearchResult.from_rounds` and property behavior inside `test_research_loop.py`.
