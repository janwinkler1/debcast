# debcast

AI-generated debate podcasts. Two hosts, pro vs con, auto-published to a podcast feed.

```bash
uv run debcast "nuclear energy"
uv run debcast --lucky
```

## Setup

```bash
uv sync
mkdir -p ~/.debcast
cp config.example.toml ~/.debcast/config.toml
```

Install `ffmpeg` for audio conversion:

```bash
# Ubuntu/Debian
sudo apt-get install ffmpeg

# macOS
brew install ffmpeg
```

Edit `~/.debcast/config.toml`. Anthropic is required for every real run because
Claude handles research and script generation:

```toml
[anthropic]
api_key = "sk-ant-..."
```

That is enough for a script-only smoke test:

```bash
uv run debcast "remote work" --dry-run --research-rounds 1
```

## TTS

### Gemini

Gemini is the default TTS provider. For audio generation, add a Gemini API key
to `~/.debcast/config.toml`:

```toml
[providers]
tts = "gemini"

[gemini]
api_key = "..."
```

Then run:

```bash
uv run debcast "remote work" --research-rounds 1 --hosting local
```

You can also override the configured provider from the CLI:

```bash
uv run debcast "remote work" --tts gemini --hosting local --research-rounds 1
```

### Kokoro

Kokoro runs TTS locally. It does not need a Gemini API key, but it does need the
optional Kokoro dependencies and model files:

```bash
uv sync --extra kokoro

curl -L -o kokoro-v0_19.onnx \
  https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files/kokoro-v0_19.onnx

curl -L -o voices.bin \
  https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files/voices.bin
```

Then run:

```bash
uv run --extra kokoro debcast "remote work" --tts kokoro --hosting local --research-rounds 1
```

Both Gemini and Kokoro still require Anthropic for research and script
generation. Both also require `ffmpeg` for MP3 conversion.
