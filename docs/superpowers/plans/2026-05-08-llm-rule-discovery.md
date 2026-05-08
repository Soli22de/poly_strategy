# LLM Rule Discovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an offline OpenAI-powered rule discovery stage that converts Polymarket market metadata into conservative implication rules, then feeds those rules into the existing deterministic backtester.

**Architecture:** Keep the current dependency-light Python package. Add pure parsing/filtering code, a small OpenAI Responses API client behind an injectable interface, a CLI command, and tests that mock the LLM client. The LLM discovers candidate semantic relationships; existing scanner/backtest code remains responsible for price, fee, depth, and capital checks.

Supported deterministic relation formats:

- `implies`: buy consequent YES + antecedent NO.
- `equivalent`: buy YES/NO cross-bundles in both directions.
- `mutually_exclusive`: buy both NO tokens.
- `collectively_exhaustive`: buy both YES tokens.
- `complement`: buy both YES and both NO bundles.

**Tech Stack:** Python 3.9 standard library, `unittest`, NDJSON input, JSON rule output, OpenAI Responses API with Structured Outputs for real runs.

---

### Task 1: Market Text Extraction Tests

**Files:**

- Create: `tests/test_rule_discovery.py`
- Create: `poly_strategy/rule_discovery.py`

- [x] Write tests for reading `raw_polymarket_gamma_market` NDJSON rows.
- [x] Test that non-Gamma rows are ignored.
- [x] Test that malformed or missing `raw` rows are skipped rather than crashing.
- [x] Test that `outcomes` supports both JSON strings and lists.
- [x] Test that the extracted record contains `market_id`, `question`, `description`, `outcomes`, `end_date`, `category`, and `slug`.
- [x] Run `python3 -m unittest discover -s tests -v` and confirm the new tests fail because the module is not implemented yet.

Implementation details:

- Add a frozen `MarketText` dataclass.
- Add `read_market_texts(path: Path) -> List[MarketText]`.
- Keep this module pure: no network calls and no OpenAI imports.

### Task 2: Candidate Schema And Filtering

**Files:**

- Update: `tests/test_rule_discovery.py`
- Update: `poly_strategy/rule_discovery.py`

- [x] Add tests for valid candidate implication conversion.
- [x] Add tests rejecting low confidence candidates.
- [x] Add tests rejecting candidates with risk flags.
- [x] Add tests rejecting unknown market IDs.
- [x] Add tests rejecting self-implications.
- [x] Add tests recording but not trading `equivalent`, `mutually_exclusive`, and `unknown`.
- [x] Run tests and confirm failures.
- [x] Implement the candidate dataclasses and filtering functions.

Implementation details:

- Add `RelationCandidate`.
- Add `DiscoveredRuleSet`.
- Add `filter_implications(candidates, known_market_ids, min_confidence)`.
- Convert `a_implies_b` into `{antecedent: market_a_id, consequent: market_b_id}`.
- Convert `b_implies_a` in the opposite direction.
- Do not auto-expand `equivalent` in MVP unless separate tests are added.

### Task 3: Rule File Writer

**Files:**

- Update: `tests/test_rule_discovery.py`
- Update: `poly_strategy/rule_discovery.py`
- Optional update: `rules/example-implications.json`

- [x] Add tests for writing a versioned LLM rule file.
- [x] Assert the file includes `version`, `source`, `generated_at`, `min_confidence`, `implications`, and `candidates`.
- [x] Assert the `implications` array remains compatible with current `backtest --rules`.
- [x] Implement `write_discovered_rules(path, ruleset) -> int`.
- [x] Keep output deterministic by sorting implications by `(antecedent, consequent)`.

Expected output shape:

```json
{
  "version": 1,
  "source": "llm_discovery",
  "generated_at": "2026-05-08T00:00:00Z",
  "min_confidence": 0.95,
  "implications": [
    {
      "antecedent": "A",
      "consequent": "B",
      "confidence": 0.97,
      "source_relation": "implies",
      "reason": "A yes resolution necessarily satisfies B's yes condition."
    }
  ],
  "candidates": []
}
```

### Task 4: OpenAI Responses Client

**Files:**

- Create: `poly_strategy/openai_rules.py`
- Create: `tests/test_openai_rules.py`

- [x] Add tests for prompt payload construction without making a network call.
- [x] Add tests that orderbook prices are not included in the LLM input.
- [x] Add tests parsing a successful structured response into `RelationCandidate` objects.
- [x] Add tests for missing API key and invalid model response errors.
- [x] Implement `OpenAIRuleDiscoveryClient`.

Implementation details:

- Use the Responses API endpoint `POST https://api.openai.com/v1/responses`.
- Use `text.format.type = "json_schema"` with `strict = true`.
- Require `OPENAI_API_KEY` for real calls.
- Accept `model`, `timeout`, and optional `base_url`.
- Keep the HTTP implementation small and injectable so tests can supply a fake transport.
- Do not call OpenAI from unit tests.

Manual command for real verification:

```bash
OPENAI_API_KEY=... python3 -m poly_strategy.cli discover-rules \
  --raw data/polymarket-gamma.ndjson \
  --out rules/candidate-implications.json \
  --model "$OPENAI_MODEL"
```

### Task 5: Discovery Orchestrator

**Files:**

- Update: `poly_strategy/rule_discovery.py`
- Update: `tests/test_rule_discovery.py`

- [x] Add tests for batching markets by `--batch-size`.
- [x] Add tests for `--max-markets`.
- [x] Add tests that empty input writes an empty valid rule file.
- [x] Implement `discover_rules(raw_path, out_path, client, batch_size, min_confidence, max_markets=None)`.

Implementation details:

- Batch order should be deterministic.
- Each batch returns candidate relations.
- All candidates are merged, filtered once against the full known market ID set, then written.
- For MVP, fail the command if a batch API call fails. Add retry logic later only if needed.

### Task 6: Backtest Rule Loader Compatibility

**Files:**

- Update: `tests/test_backtest.py`
- Update: `poly_strategy/backtest.py`

- [x] Add tests proving old rule files still load.
- [x] Add tests proving extended LLM rule files load.
- [x] Add tests that LLM implication entries with `trade_allowed=false`, low confidence, or risk flags are ignored if they appear in `implications`.
- [x] Update `load_rules(path, min_confidence=0.95)` while keeping current caller behavior stable.

Implementation details:

- Legacy rules without confidence or trade metadata should still load.
- Extended rules should be conservative:
  - Reject `trade_allowed=false`.
  - Reject `confidence < min_confidence`.
  - Reject non-empty `risk_flags`.
- The scanner should continue receiving only `ImplicationRule` objects.

### Task 7: CLI Command

**Files:**

- Update: `tests/test_cli.py`
- Update: `poly_strategy/cli.py`

- [x] Add CLI tests for `discover-rules` using a fake client or monkeypatchable factory.
- [x] Add arguments:
  - `--raw`
  - `--out`
  - `--model`
  - `--batch-size`
  - `--min-confidence`
  - `--max-markets`
  - `--timeout`
- [x] Print a concise summary: markets read, candidates found, implications written.
- [x] Return non-zero with a clear error if `OPENAI_API_KEY` is missing for a real run.

Default choices:

- `--batch-size 20`
- `--min-confidence 0.95`
- `--timeout 60`
- `--model` defaults to `OPENAI_MODEL`; if neither is set, exit with a clear error.

### Task 8: README Update

**Files:**

- Update: `README.md`

- [x] Document the full workflow:
  - collect metadata
  - discover rules
  - collect binary orderbooks
  - backtest rules
- [x] State that this is a research/backtest system, not an auto-trader.
- [x] Add examples using proxy collection and small capital sizing.

Example:

```bash
python3 -m poly_strategy.cli collect-polymarket \
  --out data/polymarket-gamma.ndjson \
  --limit 200 \
  --proxy 127.0.0.1:10808

OPENAI_API_KEY=... python3 -m poly_strategy.cli discover-rules \
  --raw data/polymarket-gamma.ndjson \
  --out rules/candidate-implications.json \
  --model "$OPENAI_MODEL" \
  --min-confidence 0.95

python3 -m poly_strategy.cli collect-polymarket-binaries \
  --out data/polymarket-binaries.ndjson \
  --limit 200 \
  --iterations 30 \
  --interval 5 \
  --proxy 127.0.0.1:10808

python3 -m poly_strategy.cli backtest data/polymarket-binaries.ndjson \
  --rules rules/candidate-implications.json \
  --min-net-edge 0.002 \
  --max-capital-per-trade 20
```

### Task 9: Full Verification

**Files:**

- All changed files.

- [x] Run `python3 -m unittest discover -s tests -v`.
- [x] Run a no-network CLI test path with a tiny fixture.
- [ ] If `OPENAI_API_KEY` is available, run one manual discovery on a small raw file with `--max-markets 20`.
- [ ] Run backtest with the generated rule file.
- [ ] Record whether any paper opportunities are found.

Completion criteria:

- Unit tests pass.
- `discover-rules` writes a valid rule file.
- `backtest --rules` accepts that file.
- No OpenAI API call occurs in automated tests.
- The final response clearly states that the system is still research/backtest only and not live trading.
