# debcast

AI-generated debate podcasts. Two hosts, pro vs con, auto-published to a podcast feed.

```bash
debcast "nuclear energy"
debcast --lucky
```

## Setup

```bash
uv sync
mkdir -p ~/.debcast
cp config.example.toml ~/.debcast/config.toml
# fill in API keys, then:
uv run debcast --lucky
```

## Config

`~/.debcast/config.toml` — set providers and API keys. Defaults: Claude for research + script, Gemini TTS, local hosting.
