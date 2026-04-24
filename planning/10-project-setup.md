# Implementation Plan: Project Setup

**Files:**

- `pyproject.toml`
- `debcast/__init__.py`
- `debcast/providers/__init__.py` (and sub-package inits)

______________________________________________________________________

## pyproject.toml

`pyproject.toml` already exists with a minimal scaffold. It needs dependencies, optional extras, the entry point, and tool config added. Current state:

```toml
[project]
name = "debcast"
version = "0.1.0"
description = "AI-generated debate podcasts from any topic"
readme = "README.md"
requires-python = ">=3.14"
dependencies = []
```

Target state (add everything below the existing `[project]` block):

```toml
[project]
name = "debcast"
version = "0.1.0"
description = "AI-generated debate podcasts from any topic"
readme = "README.md"
requires-python = ">=3.14"
dependencies = [
    "anthropic>=0.40",
    "typer>=0.12",
    "pydantic>=2.0",
    "pydantic-settings>=2.0",
    "pydub>=0.25",
    "rich>=13",
    "google-genai>=0.8",    # Gemini TTS — use google-genai, NOT google-generativeai
]

[project.optional-dependencies]
elevenlabs = ["elevenlabs>=1.0"]
google-cloud-tts = ["google-cloud-texttospeech>=2.0"]
kokoro = ["kokoro-onnx>=0.3", "numpy>=1.24"]
dev = [
    "pytest>=8",
    "pytest-mock>=3",
]

[project.scripts]
debcast = "debcast.cli:app"

[tool.pytest.ini_options]
testpaths = ["tests"]
markers = [
    "integration: marks tests that require real API credentials",
]
# No addopts skipping integration tests — they run by default.
# CI injects credentials via secrets. See 09-testing-strategy.md.

[tool.ruff]
line-length = 100
target-version = "py314"

[tool.ruff.lint]
select = ["E", "F", "I"]
```

______________________________________________________________________

## main.py

`main.py` exists at the repo root as a uv scaffold placeholder. It is not the real entry point — that will be `debcast/cli.py` registered via `[project.scripts]`. `main.py` can be deleted once the package is installed and `uv run debcast` works via the script entry point.

## README.md

`README.md` already exists with a minimal setup section. It is sufficient for Phase 1. Full expansion (provider docs, config reference, ffmpeg/Kokoro setup notes) is a Phase 7 task.

## debcast/__init__.py

```python
"""debcast — AI-generated debate podcasts."""
__version__ = "0.1.0"
```

______________________________________________________________________

## Provider __init__ files

All empty. They exist only to make Python treat the directories as packages.

```
debcast/providers/__init__.py        # empty
debcast/providers/research/__init__.py  # empty
debcast/providers/script/__init__.py    # empty
debcast/providers/tts/__init__.py       # empty
debcast/providers/hosting/__init__.py   # empty
debcast/utils/__init__.py               # empty
tests/__init__.py                       # empty
tests/providers/__init__.py             # empty
```

______________________________________________________________________

## System dependencies

`pydub` requires `ffmpeg` to be installed on the system path for MP3 encoding/decoding.

Installation:

```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt-get install ffmpeg

# Windows
# Download from ffmpeg.org or: winget install ffmpeg
```

**Kokoro** additionally requires model files:

```bash
# Download model files to project root or a known path
wget https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files/kokoro-v0_19.onnx
wget https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files/voices.bin
```

______________________________________________________________________

## Development setup

```bash
# 1. Install uv
curl -Ls https://astral.sh/uv/install.sh | sh

# 2. Clone and install
git clone https://github.com/yourhandle/debcast
cd debcast
uv sync

# 3. Install optional deps if needed
uv sync --extra elevenlabs
uv sync --extra google-cloud-tts
uv sync --extra kokoro

# 4. Configure
mkdir -p ~/.debcast
cp config.example.toml ~/.debcast/config.toml
$EDITOR ~/.debcast/config.toml   # fill in anthropic.api_key at minimum

# 5. Run unit tests only (no credentials needed)
uv run pytest -m "not integration"

# 6. Run everything including integration tests (needs API keys in env or config)
uv run pytest

# 7. First run
uv run debcast "nuclear energy"
```

______________________________________________________________________

## Python version requirement

`>=3.14` as set in the existing `pyproject.toml`. All modern Python features are available:

- `tomllib` in stdlib (since 3.11)
- `str | None` union syntax (since 3.10)
- `from __future__ import annotations` is no longer needed but harmless to include

______________________________________________________________________

## .gitignore additions

```gitignore
# debcast
~/.debcast/
*.onnx
voices.bin
debcast-episodes/
```
