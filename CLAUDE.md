# debcast

AI-generated debate podcasts from any topic. Two hosts, pro vs con, auto-published to a listenable feed. CLI-first.

```bash
debcast "nuclear energy"
debcast --lucky
debcast "remote work" --dry-run
```

---

## What it does

1. **Researches** the topic by crawling the web for arguments on both sides
2. **Generates** a ~15 min two-host debate script (Host A = pro, Host B = con)
3. **Synthesizes** audio with two distinct TTS voices
4. **Publishes** to a podcast feed you can subscribe to on any podcast app

---

## Architecture

The pipeline is intentionally linear and each stage is independently testable:

```
TopicResolver → ResearchLoop → ScriptGenerator → TTSEngine → Publisher
```

Each stage communicates via a typed intermediate — no globals, no shared state.

### Research loop

Research runs as a synced loop of N rounds. Both sides research independently each round, then exchange results so the next round targets counter-arguments:

```
Round 1:  pro.research(topic)               con.research(topic)
               ↓                                     ↓
Round 2:  pro.research(counter_to=con[1])   con.research(counter_to=pro[1])
               ↓                                     ↓
          ...repeat N times...
               ↓
          ResearchResult (all rounds merged)
```

`N` is controlled by `research_rounds` in config (default 3). The accumulated arguments across all rounds feed into script generation, giving the debate genuine depth and back-and-forth.

### Provider abstraction

Every external dependency is behind a `Protocol`. TTS and hosting providers are configurable; research and script generation always use Claude.

```python
class ResearchProvider(Protocol):
    def research(
        self,
        topic: str,
        stance: Literal["pro", "con"],
        counter_to: list[Argument] | None = None,  # opponent's prior-round arguments
    ) -> list[Argument]: ...

class ScriptProvider(Protocol):
    def generate(self, research: ResearchResult) -> Script: ...

class TTSProvider(Protocol):
    def synthesize(self, script: Script) -> bytes: ...

class HostingProvider(Protocol):
    def publish(self, episode: Episode) -> str: ...
```

### Intermediate types

```python
@dataclass
class ResearchRound:
    round: int
    pro: list[Argument]      # each has text + source URL
    con: list[Argument]

@dataclass
class ResearchResult:
    topic: str
    rounds: list[ResearchRound]
    pro: list[Argument]      # flattened across all rounds
    con: list[Argument]

@dataclass
class Script:
    topic: str
    turns: list[Turn]        # {speaker: "A"|"B", text: str}

@dataclass
class Episode:
    title: str
    audio: bytes             # MP3
    description: str
    sources: list[str]
```

---

## Supported providers

| Stage      | Provider         | Free tier         | Notes                        |
|------------|-----------------|-------------------|------------------------------|
| Research   | Claude (Anthropic) | via API key     | web search tool built in     |
| Script     | Claude (Anthropic) | via API key     | only supported provider      |
| TTS        | Gemini 2.5 TTS   | generous free tier | two-speaker mode, default   |
| TTS        | Google Cloud TTS | 1M chars/month    | WaveNet voices               |
| TTS        | ElevenLabs       | 10K chars/month   | best quality, limited free   |
| TTS        | Kokoro           | free, local       | runs on CPU, no API key      |
| Hosting    | PodClaw          | 1 show, unlimited episodes | RSS → Apple/Spotify |
| Hosting    | local            | free              | writes RSS file to disk      |

---

## Project structure

```
debcast/
├── CLAUDE.md
├── README.md
├── pyproject.toml
├── debcast/
│   ├── __init__.py
│   ├── cli.py               # Typer app, entry point
│   ├── config.py            # Pydantic settings, reads ~/.debcast/config.toml
│   ├── pipeline.py          # orchestrates the stages in order
│   ├── research_loop.py     # synced N-round research loop
│   ├── types.py             # ResearchResult, ResearchRound, Script, Episode, Turn, Argument
│   ├── providers/
│   │   ├── __init__.py
│   │   ├── research/
│   │   │   └── claude.py
│   │   ├── script/
│   │   │   └── claude.py
│   │   ├── tts/
│   │   │   ├── gemini.py
│   │   │   ├── google_cloud.py
│   │   │   ├── elevenlabs.py
│   │   │   └── kokoro.py
│   │   └── hosting/
│   │       ├── podclaw.py
│   │       └── local.py
│   └── utils/
│       └── audio.py         # pydub helpers, MP3 stitching
└── tests/
    ├── test_pipeline.py
    ├── test_script_generator.py
    └── providers/
        └── test_tts_gemini.py
```

---

## Config

Place at `~/.debcast/config.toml`:

```toml
[providers]
tts      = "gemini"       # gemini | google_cloud | elevenlabs | kokoro
hosting  = "podclaw"      # podclaw | local

[research]
rounds = 3                # number of pro/con exchange rounds

[anthropic]
api_key = "sk-ant-..."

[elevenlabs]
api_key = "..."           # only needed if tts = "elevenlabs"

[google_cloud]
credentials_path = "~/.config/gcloud/application_default_credentials.json"

[podclaw]
api_key = "..."
show_id = 1

[local]
output_dir = "~/debcast-episodes"
rss_path   = "~/debcast-episodes/feed.xml"
```

---

## CLI

```bash
# generate and publish
debcast "is remote work good for society"

# feeling lucky — LLM picks a spicy topic
debcast --lucky

# print script only, no audio, no publish
debcast "veganism" --dry-run

# override provider or research depth for one run
debcast "AI regulation" --tts elevenlabs --hosting local
debcast "AI regulation" --research-rounds 5

# list recent episodes
debcast --list
```

---

## Development setup

```bash
# install uv if you don't have it
curl -Ls https://astral.sh/uv/install.sh | sh

# clone and install
git clone https://github.com/yourhandle/debcast
cd debcast
uv sync

# copy and fill in config
mkdir -p ~/.debcast
cp config.example.toml ~/.debcast/config.toml
$EDITOR ~/.debcast/config.toml

# run
uv run debcast --lucky
```

---

## Adding a new provider

1. Create the file under the appropriate `providers/` subdirectory
2. Implement the corresponding `Protocol` from `debcast/types.py`
3. Add the provider key to the `config.py` enum
4. Wire it up in `pipeline.py`
5. Add a test under `tests/providers/`

No changes needed anywhere else.

---

## Testing

```bash
uv run pytest                     # all tests
uv run pytest tests/test_pipeline.py  # pipeline only
uv run pytest -k "not integration"    # skip tests that hit real APIs
```

Providers are tested with mocks. Integration tests (hitting real APIs) are marked `@pytest.mark.integration` and skipped by default.

---

## Non-goals

- No web UI — CLI only
- No database — filesystem is enough
- No async — pipeline is sequential, complexity not worth it
- No audio editing beyond stitching — what TTS gives you is what you get

---

## Status

Early. Contributions welcome but expect things to move fast and break.
