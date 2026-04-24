# debcast

AI-generated debate podcasts from any topic. Two hosts, pro vs con, auto-published to a listenable feed. CLI-first.

______________________________________________________________________

## Development setup

```bash
uv sync
```

______________________________________________________________________

## Code quality

```bash
uv run ruff format .                                  # format
uv run ruff check . --fix                             # lint + autofix
uv run ruff format --check . && uv run ruff check .   # what CI runs
uv run mdformat README.md CLAUDE.md                   # format markdown
uv run mdformat --check README.md CLAUDE.md           # what CI runs
```

______________________________________________________________________

## Testing

```bash
uv run pytest tests/
```

______________________________________________________________________

## GitHub workflow

We do trunk-based development with short-lived feature branches. **One branch per atomic unit of work** (one issue, one PR). Never bundle unrelated changes.

1. Create an issue for the work
1. Create a feature branch from `main`
1. Open a PR that closes the issue — wait for review before merging

```bash
gh issue create --title "short title" --body "description"

git checkout -b your-name/short-description

gh pr create --title "short title" --body "$(cat <<'EOF'
## Summary
- what changed and why

Closes #<issue-number>
EOF
)"
```
