# Polymarket Data Collection And Backtest Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a small local research tool that records prediction-market snapshots and backtests fee-aware short-window arbitrage candidates.

**Architecture:** Use a dependency-light Python package with pure core logic and a CLI wrapper. Core modules parse order books, calculate fees, detect opportunities, and replay NDJSON snapshots; network collectors write raw snapshots without being required for tests.

**Tech Stack:** Python 3.9 standard library, `unittest`, NDJSON snapshot files.

---

### Task 1: Core Tests

**Files:**
- Create: `tests/test_fees.py`
- Create: `tests/test_orderbook.py`
- Create: `tests/test_scanner.py`
- Create: `tests/test_backtest.py`

- [ ] Write tests for Polymarket fee calculation, weighted orderbook fills, binary YES/NO structure arbitrage, cross-venue same-binary opportunities, and NDJSON replay.
- [ ] Run `python3 -m unittest discover -s tests -v` and verify imports fail because implementation does not exist.

### Task 2: Pure Core Modules

**Files:**
- Create: `poly_strategy/__init__.py`
- Create: `poly_strategy/fees.py`
- Create: `poly_strategy/orderbook.py`
- Create: `poly_strategy/models.py`
- Create: `poly_strategy/scanner.py`
- Create: `poly_strategy/backtest.py`

- [ ] Implement minimal dataclasses and pure functions to satisfy tests.
- [ ] Run `python3 -m unittest discover -s tests -v` and verify all core tests pass.

### Task 3: CLI And Collector

**Files:**
- Create: `poly_strategy/collectors.py`
- Create: `poly_strategy/cli.py`
- Create: `README.md`

- [ ] Add commands for `collect-polymarket`, `backtest`, and `sample`.
- [ ] Keep network failures explicit and non-fatal to offline tests.
- [ ] Run `python3 -m poly_strategy.cli sample --out data/sample.ndjson` then `python3 -m poly_strategy.cli backtest data/sample.ndjson`.

