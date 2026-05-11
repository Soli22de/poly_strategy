# Contributing

## Setup

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install -e ".[dev,live]"
pytest
```

## Before opening a PR

- Keep secrets out of git.
- Update docs when behavior changes.
- Run the full test suite.
- Prefer small, focused commits.

## Code review

This repo favors conservative changes. If a change affects live execution, data retention, or external API calls, include a test that covers the new behavior.

