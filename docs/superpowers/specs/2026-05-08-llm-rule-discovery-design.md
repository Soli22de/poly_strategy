# LLM Rule Discovery Design

## Current System

The repository currently implements a local research system, not an execution bot:

- `collect-polymarket` records raw Polymarket Gamma market metadata or raw CLOB books.
- `collect-polymarket-binaries` records backtestable binary market snapshots with YES and NO books.
- `backtest` replays snapshots and scans deterministic opportunities:
  - Same-market `YES + NO < 1` bundles.
  - Manual implication rules such as `A => B`.
  - Capital-capped paper sizing.

The missing part is automated discovery of cross-market logical rules. Those rules are exactly where an LLM is useful, because the raw opportunity is often semantic: one question's resolution implies another question's resolution, but the market IDs and text differ.

## Goal

Add an offline LLM-assisted rule discovery stage that turns Polymarket market metadata into candidate implication rules, then lets the existing deterministic scanner and backtester decide whether any rule is economically tradable.

The system should be:

- Fully automatic in batch mode.
- Conservative by default.
- Backtest-first.
- Compatible with small capital.
- Explicitly separated from order placement.

## Non-Goals

This design does not add:

- Live order placement.
- Private-key handling.
- A market-making engine.
- LLM-based buy or sell decisions.
- Real-time LLM calls every few seconds.
- Forecasting whether an event will happen.

The LLM proposes semantic relationships. The scanner decides whether prices, depth, fees, and capital constraints make the relationship worth trading.

## Architecture

Pipeline:

1. Collect raw market metadata from Polymarket Gamma.
2. Extract compact market text records.
3. Batch records into small discovery jobs.
4. Ask OpenAI Responses API for structured JSON candidate relations.
5. Normalize and filter candidates.
6. Write a rule file compatible with `backtest --rules`.
7. Replay collected orderbook snapshots against those rules.

Critical boundary:

- LLM output is untrusted input.
- Only filtered rules reach the scanner.
- Only deterministic orderbook math creates paper opportunities.
- No trade should be submitted solely because the LLM says a rule exists.

## Data Flow

Input NDJSON row:

```json
{
  "type": "raw_polymarket_gamma_market",
  "market_id": "12345",
  "raw": {
    "question": "Will candidate X win the 2026 election?",
    "description": "...",
    "outcomes": "[\"Yes\", \"No\"]",
    "endDate": "2026-11-04T00:00:00Z",
    "category": "Politics"
  }
}
```

Internal market text record:

```json
{
  "market_id": "12345",
  "question": "Will candidate X win the 2026 election?",
  "description": "...",
  "outcomes": ["Yes", "No"],
  "end_date": "2026-11-04T00:00:00Z",
  "category": "Politics",
  "slug": "will-candidate-x-win-the-2026-election"
}
```

The LLM receives only compact fields needed to reason about event semantics. It should not receive orderbook prices, because prices can bias semantic rule discovery and are handled later by the scanner.

## LLM Task

For each batch, identify relationships between binary markets:

- `implies`: If market A resolves YES, market B must resolve YES.
- `equivalent`: A YES and B YES are logically the same event.
- `mutually_exclusive`: A YES and B YES cannot both happen.
- `collectively_exhaustive`: At least one of A YES or B YES must happen.
- `complement`: Exactly one of A YES or B YES must happen.
- `unknown`: insufficient confidence.

The scanner maps these relations to deterministic buy bundles:

- `implies`: buy consequent YES and antecedent NO.
- `equivalent`: buy one side YES and the other side NO in both directions.
- `mutually_exclusive`: buy both NO tokens.
- `collectively_exhaustive`: buy both YES tokens.
- `complement`: buy both YES tokens and both NO tokens.

## Structured Output Contract

The OpenAI Responses request should use Structured Outputs with `text.format.type = "json_schema"` and `strict = true`, following the official Responses API and Structured Outputs docs:

- https://platform.openai.com/docs/api-reference/responses
- https://platform.openai.com/docs/guides/structured-outputs?api-mode=responses

The response shape should be:

```json
{
  "relations": [
    {
      "relation_type": "implies",
      "market_a_id": "A",
      "market_b_id": "B",
      "direction": "a_implies_b",
      "confidence": 0.97,
      "trade_allowed": true,
      "risk_flags": [],
      "reason": "A yes resolution necessarily satisfies B's yes condition."
    }
  ]
}
```

Allowed values:

- `relation_type`: `implies`, `equivalent`, `mutually_exclusive`, `collectively_exhaustive`, `complement`, `unknown`.
- `direction`: `a_implies_b`, `b_implies_a`, `bidirectional`, `none`.
- `confidence`: number from `0` to `1`.
- `trade_allowed`: boolean.
- `risk_flags`: list of strings.

Standard risk flags:

- `different_resolution_source`
- `different_deadline`
- `ambiguous_wording`
- `conditional_or_fallback_resolution`
- `non_binary_or_non_yes_no`
- `stale_or_closed_market`
- `insufficient_information`
- `possible_subject_mismatch`

## Filtering Rules

A candidate may become a tradable implication only if:

- `relation_type == "implies"`.
- Direction is `a_implies_b` or `b_implies_a`.
- `trade_allowed == true`.
- `confidence >= min_confidence`, default `0.95`.
- `risk_flags` is empty.
- Both market IDs exist in the current raw input.
- The antecedent and consequent are not the same market.

Equivalent markets can be expanded into two implications only after the same filters pass. For the first implementation, record them but do not expand them automatically unless tests cover the behavior.

## Rule File Format

The output should preserve compatibility with the existing `backtest --rules` format:

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
  "candidates": [
    {
      "relation_type": "implies",
      "market_a_id": "A",
      "market_b_id": "B",
      "direction": "a_implies_b",
      "confidence": 0.97,
      "trade_allowed": true,
      "risk_flags": [],
      "reason": "A yes resolution necessarily satisfies B's yes condition."
    }
  ]
}
```

`backtest.load_rules` should remain backward compatible with old files that only contain:

```json
{"implications": [{"antecedent": "A", "consequent": "B"}]}
```

Legacy rules are accepted as explicit user-provided rules. LLM-discovered rules are filtered before they are written and may also be filtered when read.

## CLI

New command:

```bash
python3 -m poly_strategy.cli discover-rules \
  --raw data/polymarket-gamma.ndjson \
  --out rules/candidate-implications.json \
  --model MODEL_NAME \
  --batch-size 20 \
  --min-confidence 0.95
```

Environment:

- `OPENAI_API_KEY` is required for real API calls.
- `OPENAI_MODEL` may provide a default model if `--model` is omitted.
- `OPENAI_BASE_URL` may point to an OpenAI-compatible endpoint, such as `https://api.wwcloud.app`.
- `HTTPS_PROXY` or existing CLI proxy support can be added later if needed.

The first implementation should also support a no-network path for tests by injecting a fake client, not by calling the OpenAI API in unit tests.

## Prompt Policy

The prompt must force conservative behavior:

- Prefer false negatives over false positives.
- Mark `trade_allowed=false` if resolution text differs.
- Mark risk flags instead of guessing.
- Do not infer real-world probabilities.
- Do not use price, liquidity, or market popularity.
- Return only relations between provided market IDs.

The prompt should explicitly define `A => B` as:

> If market A resolves YES, market B must resolve YES under their written resolution criteria.

## Error Handling

Expected failures:

- Missing `OPENAI_API_KEY`: CLI exits with a clear error.
- Invalid model response: reject the batch and write no rules from it.
- Unknown market ID in model output: drop candidate.
- API timeout or rate limit: fail the command for MVP; retry logic can be added later.
- Empty input: write an empty valid rule file.

## Testing Strategy

Unit tests should cover:

- Parsing raw Gamma NDJSON into compact market records.
- Prompt input generation excludes orderbook prices.
- Response validation accepts valid structured candidates.
- Filtering rejects low confidence, risk flags, unknown IDs, self-rules, and non-implies relations.
- Rule file output remains compatible with `backtest --rules`.
- CLI uses an injected fake discovery client in tests.

Network tests should be manual only:

```bash
OPENAI_API_KEY=... python3 -m poly_strategy.cli discover-rules \
  --raw data/polymarket-gamma.ndjson \
  --out rules/candidate-implications.json \
  --model "$OPENAI_MODEL"
```

Then:

```bash
python3 -m poly_strategy.cli backtest data/polymarket-binaries.ndjson \
  --rules rules/candidate-implications.json \
  --min-net-edge 0.002 \
  --max-capital-per-trade 20
```

## Operational Meaning

For small capital, the practical target is not pure exchange-level high frequency. It is a fast deterministic scanner over slowly refreshed semantic rules:

- Rule discovery cadence: minutes to hours.
- Orderbook snapshot cadence: seconds to tens of seconds, depending on rate limits and hardware.
- Trading decision cadence in a future bot: deterministic, price-driven, and rule-gated.

The MVP should prove whether semantic rules create repeated paper opportunities before any execution work is considered.
