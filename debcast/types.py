from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable


@dataclass(frozen=True)
class Source:
    url: str
    title: str = ""
    snippet: str = ""


@dataclass(frozen=True)
class Argument:
    text: str
    sources: tuple[Source, ...] = ()


@dataclass(frozen=True)
class ResearchRound:
    round: int
    pro: tuple[Argument, ...]
    con: tuple[Argument, ...]


@dataclass(frozen=True)
class ResearchResult:
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
    speaker: Literal["A", "B"]
    text: str


@dataclass(frozen=True)
class Script:
    topic: str
    turns: tuple[Turn, ...]

    @property
    def full_text(self) -> str:
        return "\n\n".join(f"[{t.speaker}] {t.text}" for t in self.turns)


@dataclass(frozen=True)
class AudioArtifact:
    data: bytes
    mime_type: str
    format: str


@dataclass(frozen=True)
class PublishResult:
    feed_url: str
    episode_url: str
    local_path: str | None = None


@dataclass
class Episode:
    title: str
    audio: AudioArtifact
    description: str
    sources: list[str]
    script: Script | None = None


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
