# poly_strategy

Small research toolkit for prediction-market data collection and offline opportunity replay.

This is not an auto-trader. The first goal is to record snapshots and test whether fee-aware opportunities survive realistic filters.

## Commands

Create a synthetic snapshot:

```bash
python3 -m poly_strategy.cli sample --out data/sample.ndjson
```

Replay snapshots:

```bash
python3 -m poly_strategy.cli backtest data/sample.ndjson
```

Try collecting Polymarket Gamma market metadata:

```bash
python3 -m poly_strategy.cli collect-polymarket --out data/polymarket-gamma.ndjson --limit 20 --timeout 10
```

Use a local HTTP proxy if direct access is unstable:

```bash
python3 -m poly_strategy.cli collect-polymarket --out data/polymarket-gamma.ndjson --limit 20 --timeout 10 --proxy 127.0.0.1:10808
```

Try collecting specific Polymarket CLOB books:

```bash
python3 -m poly_strategy.cli collect-polymarket --out data/books.ndjson --token-id TOKEN_ID --timeout 10
```

Discover conservative implication rules from raw Gamma market metadata with an OpenAI-compatible Responses API:

```bash
export OPENAI_API_KEY=...
export OPENAI_MODEL=...
export OPENAI_BASE_URL=https://api.wwcloud.app

python3 -m poly_strategy.cli discover-rules \
  --raw data/polymarket-gamma.ndjson \
  --out rules/candidate-implications.json \
  --batch-size 10 \
  --min-confidence 0.95 \
  --max-markets 100 \
  --max-output-tokens 4000 \
  --reasoning-effort medium
```

You can also pass the model and base URL explicitly:

```bash
python3 -m poly_strategy.cli discover-rules \
  --raw data/polymarket-gamma.ndjson \
  --out rules/candidate-implications.json \
  --model MODEL_NAME \
  --base-url https://api.wwcloud.app
```

The LLM stage only proposes semantic relations. It does not place trades and does not receive orderbook prices.

Supported deterministic relation formats:

- `implications`: if `A YES => B YES`, scan `buy B YES + buy A NO < 1 - costs`.
- `equivalent`: if `A YES iff B YES`, scan both `buy A YES + buy B NO` and `buy B YES + buy A NO`.
- `mutually_exclusive`: if `A YES` and `B YES` cannot both happen, scan `buy A NO + buy B NO`.
- `collectively_exhaustive`: if at least one of `A YES` or `B YES` must happen, scan `buy A YES + buy B YES`.
- `complement`: if exactly one of `A YES` or `B YES` must happen, scan both `YES + YES` and `NO + NO` bundles.

For incremental discovery, reuse a previous rule file as cache:

```bash
python3 -m poly_strategy.cli discover-rules \
  --raw data/polymarket-gamma.ndjson \
  --out rules/candidate-implications.json \
  --cache rules/candidate-implications.json \
  --model gpt-5.5 \
  --base-url https://api.wwcloud.app
```

New rule files include `processed_market_ids`, so a later incremental run skips markets that were already reviewed even if the LLM found no relation for them. If the cache fully covers the raw input, `discover-rules --cache ...` can refresh the normalized rule file without an API call or model.

Collect only markets referenced by a rule file:

```bash
python3 -m poly_strategy.cli collect-rule-markets \
  --gamma data/polymarket-gamma.ndjson \
  --rules rules/candidate-implications.json \
  --out data/rule-markets.ndjson \
  --proxy 127.0.0.1:10808 \
  --book-workers 8
```

Watch those markets repeatedly and replay opportunities:

```bash
python3 -m poly_strategy.cli monitor-rules \
  --gamma data/polymarket-gamma.ndjson \
  --rules rules/candidate-implications.json \
  --out data/rule-monitor.ndjson \
  --interval 5 \
  --iterations 12 \
  --min-net-edge 0.002 \
  --max-capital-per-trade 20 \
  --book-workers 8
```

`monitor-rules` appends each targeted snapshot batch, replays the cumulative file, and prints current-iteration opportunities plus active run duration/edge when any opportunity survives the `--min-net-edge` filter.

For a longer paper-trading run, use `paper-monitor`. It keeps the same targeted collection loop, but writes structured JSONL for every iteration plus a final summary. Use `--skip-book-errors` so one failed CLOB book does not discard the whole batch, and `--continue-on-error` for unattended runs:

```bash
python3 -m poly_strategy.cli paper-monitor \
  --gamma data/polymarket-gamma.ndjson \
  --rules rules/candidate-implications.json \
  --snapshots-out data/paper-monitor-snapshots.ndjson \
  --report-out data/paper-monitor-report.jsonl \
  --proxy 127.0.0.1:10808 \
  --interval 5 \
  --iterations 17280 \
  --book-workers 8 \
  --min-net-edge 0.002 \
  --max-capital-per-trade 20 \
  --bankroll 100 \
  --min-run-observations 2 \
  --min-run-seconds 3 \
  --skip-book-errors \
  --continue-on-error
```

At a 5 second interval, `--iterations 17280` is roughly one day. The report rows include current opportunities, stable opportunities after the run-duration filter, simulated stable paper trades, collection error counts, and the cumulative replay totals.

Write a conflict-aware paper trading report. This sorts opportunities by edge per capital, reserves overlapping leg liquidity so the same visible ask depth is not counted twice, and applies both per-trade and per-iteration bankroll caps:

```bash
python3 -m poly_strategy.cli paper-report data/rule-monitor.ndjson \
  --rules rules/candidate-implications.json \
  --min-net-edge 0.002 \
  --max-capital-per-trade 20 \
  --bankroll 100 \
  --out data/paper-report.json
```

Build dry-run execution plans from the latest snapshot batch:

```bash
python3 -m poly_strategy.cli execute-latest data/rule-monitor.ndjson \
  --rules rules/candidate-implications.json \
  --min-net-edge 0.002 \
  --min-run-observations 2 \
  --min-run-seconds 3 \
  --max-capital-per-trade 20 \
  --bankroll 100 \
  --out data/execution-plans.ndjson
```

For a safer pre-trade path, refresh the targeted rule-market books immediately before planning:

```bash
python3 -m poly_strategy.cli execute-rules-once \
  --gamma data/polymarket-gamma.ndjson \
  --rules rules/candidate-implications.json \
  --snapshots-out data/execute-refresh.ndjson \
  --out data/execution-plans.ndjson \
  --proxy 127.0.0.1:10808 \
  --book-workers 8 \
  --min-net-edge 0.002 \
  --min-run-observations 1 \
  --max-capital-per-trade 20 \
  --bankroll 100
```

Live submission is intentionally disabled by default. To submit with the official Polymarket CLOB Python SDK v2, install `py_clob_client_v2`, set `POLYMARKET_PRIVATE_KEY` and optional L2 API credential environment variables, then pass both `--live` and `--allow-live`. Multi-leg arbitrage execution is not atomic, so live submission of plans with more than one order also requires `--allow-nonatomic-live`. The generated orders are FOK buy orders with a configurable slippage cushion and tick size.

Collect backtestable binary snapshots by combining Gamma market discovery with YES/NO CLOB books:

```bash
python3 -m poly_strategy.cli collect-polymarket-binaries --out data/live-binaries.ndjson --limit 50 --timeout 12 --proxy 127.0.0.1:10808
```

Then replay them:

```bash
python3 -m poly_strategy.cli backtest data/live-binaries.ndjson
```

Run repeated collection for a short smoke test:

```bash
python3 -m poly_strategy.cli collect-polymarket-binaries \
  --out data/live-binaries.ndjson \
  --limit 25 \
  --iterations 3 \
  --interval 5 \
  --timeout 12 \
  --proxy 127.0.0.1:10808
```

Run a longer one-hour sample:

```bash
python3 -m poly_strategy.cli collect-polymarket-binaries \
  --out data/hourly-binaries.ndjson \
  --limit 50 \
  --iterations 720 \
  --interval 5 \
  --timeout 12 \
  --proxy 127.0.0.1:10808
```

Replay with small-bankroll limits:

```bash
python3 -m poly_strategy.cli backtest data/hourly-binaries.ndjson \
  --min-net-edge 0.005 \
  --max-capital-per-trade 25
```

Add hand-reviewed implication rules for markets where one event logically implies another:

```json
{
  "implications": [
    {
      "antecedent": "france-wins-world-cup",
      "consequent": "france-reaches-final"
    }
  ]
}
```

For an implication `A => B`, the scanner tests:

```text
buy B YES + buy A NO < 1 - costs
```

Replay with rules:

```bash
python3 -m poly_strategy.cli backtest data/hourly-binaries.ndjson \
  --rules rules/candidate-implications.json \
  --min-net-edge 0.005 \
  --max-capital-per-trade 25
```

Output fields:

- `opportunities`: raw detected structure opportunities.
- `total_edge`: theoretical total edge if each full visible opportunity is filled.
- `paper_trades`: opportunities after paper-trade sizing.
- `paper_rejections`: paper opportunities skipped because bankroll or overlapping visible liquidity was already reserved.
- `by_kind`: aggregate opportunity and paper-trading totals by opportunity type.
- `paper_capital`: simulated capital used after `--max-capital-per-trade`.
- `paper_edge`: edge after paper-trade sizing.
- `runs`: consecutive snapshot runs where the same opportunity persisted.

For this research stage, a signal is worth deeper work only if it repeatedly shows:

- positive `paper_edge` after a non-trivial `--min-net-edge`;
- enough `runs` with duration above your observed execution latency;
- enough capital capacity at your intended trade size.

## Snapshot Format

The current backtest consumes `binary_snapshot` rows:

```json
{"type":"binary_snapshot","venue":"polymarket","market_id":"sample","fee_rate":0.0,"yes":{"asks":[[0.45,10]],"bids":[]},"no":{"asks":[[0.53,7]],"bids":[]}}
```

It detects the simplest structure opportunity:

```text
buy YES + buy NO < 1 - costs
```
