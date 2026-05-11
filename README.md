# poly_strategy

Prediction-market research toolkit for collecting market data, replaying snapshots, and validating dry-run opportunities.

The repository is organized for research, paper trading, and guarded execution planning. Live execution stays behind explicit keys and risk checks.

## Layout

- `poly_strategy/`: core package
- `scripts/`: recurring jobs and operational helpers
- `tests/`: unit tests
- `docs/`: architecture, operations, and command reference
- `rules/`: cached semantic rules
- `ops/launchd/`: macOS LaunchAgent templates
- `data/` and `var/`: local runtime state, ignored by git

## Quick start

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install -e ".[dev,live]"
cp .env.example .env.local
pytest
```

## Common entry points

```bash
python -m poly_strategy.cli sample --out data/sample.ndjson
python -m poly_strategy.cli backtest data/sample.ndjson
python -m poly_strategy.cli collect-polymarket --out data/polymarket-gamma.ndjson --limit 20 --timeout 10
```

## Docs

- [Pipeline](docs/pipeline.md)
- [Operations](docs/operations.md)
- [Repository layout](docs/repository-layout.md)
- [Security](docs/security.md)
- [Command reference](docs/command-reference.md)

## Notes

- Keep `.env.local`, generated snapshots, logs, and other runtime artifacts out of git.
- The repo ships with dry-run workflows and optional live integrations, but no secrets.
