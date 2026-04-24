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

## PodClaw

PodClaw publishes episodes to a real RSS feed. Its API expects a public
`audio_url`, so debcast either uploads generated MP3 files to S3-compatible
storage or stages them in a local directory that you sync yourself.

For AWS S3, Cloudflare R2, MinIO, or another S3-compatible store, set
`audio_base_url` to the public URL for that storage location and configure the
`s3_*` fields. For example, if the generated object key is `remote-work.mp3`,
then `<audio_base_url>/remote-work.mp3` must be reachable in a browser.

First, create a PodClaw API key:

```bash
curl -X POST https://podclaw.io/api/keys \
  -H "Content-Type: application/json" \
  -d '{"name":"debcast", "email":"<your-email>"}'
```

Save the returned `api_key.key`; it is only shown once.

Then create a show:

```bash
curl -X POST https://podclaw.io/api/shows \
  -H "Authorization: Bearer pc_live_..." \
  -H "Content-Type: application/json" \
  -d '{"title":"debcast","author":"debcast","category":"Technology"}'
```

Use the returned `show.id` as `podclaw.show_id`:

```toml
[providers]
hosting = "podclaw"

[podclaw]
api_key = "pc_live_..."
show_id = 1
audio_base_url = "https://pub-...r2.dev"
s3_bucket = "debcast-audio"
s3_endpoint_url = "https://<account-id>.r2.cloudflarestorage.com"
s3_region = "auto"
s3_access_key_id = "..."
s3_secret_access_key = "..."

# Optional: also keep a local copy for troubleshooting.
audio_output_dir = "~/debcast-podclaw-audio"
```

Then run:

```bash
uv run debcast "remote work" --hosting podclaw --research-rounds 1
```
