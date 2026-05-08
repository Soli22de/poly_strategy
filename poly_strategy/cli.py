import argparse
import os
import sys
import time
from pathlib import Path
from urllib.error import URLError

from poly_strategy.backtest import replay_ndjson
from poly_strategy.collectors import (
    collect_polymarket_binary_snapshots_loop,
    collect_polymarket_binary_snapshots_for_rules,
    collect_polymarket_binary_snapshots_for_rules_loop,
    collect_polymarket_books,
    collect_polymarket_gamma,
    write_sample_snapshot,
)
from poly_strategy.openai_rules import OpenAIConfigError, OpenAIResponseError, OpenAIRuleDiscoveryClient
from poly_strategy.rule_discovery import discover_rules


def main(argv=None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "sample":
            count = write_sample_snapshot(Path(args.out))
            print(f"wrote={count} out={args.out}")
            return 0
        if args.command == "backtest":
            result = replay_ndjson(
                Path(args.path),
                min_net_edge=args.min_net_edge,
                max_capital_per_trade=args.max_capital_per_trade,
                rules_path=Path(args.rules) if args.rules else None,
            )
            print(
                f"snapshots={result.snapshot_count} opportunities={result.opportunity_count} "
                f"total_edge={result.total_edge:.6f} paper_trades={result.paper_trade_count} "
                f"paper_capital={result.paper_capital_used:.6f} paper_edge={result.paper_edge:.6f} "
                f"runs={len(result.runs)}"
            )
            for opportunity in result.opportunities:
                print(
                    f"{opportunity.kind} qty={opportunity.quantity:g} "
                    f"cost={opportunity.cost_per_share:.6f} edge={opportunity.net_edge_per_share:.6f} "
                    f"total={opportunity.total_edge:.6f}"
                )
            for run in result.runs:
                print(
                    f"run market={run.market_id} observations={run.observation_count} "
                    f"duration_seconds={run.duration_seconds:.3f} max_edge={run.max_edge_per_share:.6f}"
                )
            return 0
        if args.command == "collect-polymarket":
            if args.token_id:
                count = collect_polymarket_books(Path(args.out), args.token_id, args.timeout, args.proxy)
            else:
                count = collect_polymarket_gamma(Path(args.out), args.limit, args.timeout, args.proxy)
            print(f"wrote={count} out={args.out}")
            return 0
        if args.command == "collect-polymarket-binaries":
            count = collect_polymarket_binary_snapshots_loop(
                Path(args.out),
                args.limit,
                args.timeout,
                args.proxy,
                args.interval,
                args.iterations,
            )
            print(f"wrote={count} out={args.out}")
            return 0
        if args.command == "collect-rule-markets":
            count = collect_polymarket_binary_snapshots_for_rules_loop(
                Path(args.out),
                Path(args.gamma),
                Path(args.rules),
                args.timeout,
                args.proxy,
                args.interval,
                args.iterations,
            )
            print(f"wrote={count} out={args.out}")
            return 0
        if args.command == "monitor-rules":
            total = 0
            for index in range(args.iterations):
                total += collect_polymarket_binary_snapshots_for_rules(
                    Path(args.out),
                    Path(args.gamma),
                    Path(args.rules),
                    args.timeout,
                    args.proxy,
                )
                result = replay_ndjson(
                    Path(args.out),
                    min_net_edge=args.min_net_edge,
                    max_capital_per_trade=args.max_capital_per_trade,
                    rules_path=Path(args.rules),
                )
                current_opportunities = _current_monitor_opportunities(result)
                current_runs = _current_monitor_runs(result)
                print(
                    f"iteration={index + 1} snapshots={result.snapshot_count} "
                    f"current_opportunities={len(current_opportunities)} "
                    f"opportunities={result.opportunity_count} paper_edge={result.paper_edge:.6f}"
                )
                _print_current_monitor_details(current_opportunities, current_runs)
                if index < args.iterations - 1 and args.interval > 0:
                    time.sleep(args.interval)
            print(f"wrote={total} out={args.out}")
            return 0
        if args.command == "discover-rules":
            model = args.model or os.environ.get("OPENAI_MODEL")
            if not model and not args.cache:
                print("error: model is required via --model or OPENAI_MODEL", file=sys.stderr)
                return 1
            client = None
            if model:
                client = OpenAIRuleDiscoveryClient(
                    model=model,
                    timeout=args.timeout,
                    base_url=args.base_url,
                    retries=args.retries,
                    max_output_tokens=args.max_output_tokens,
                    reasoning_effort=args.reasoning_effort,
                    verbosity=args.verbosity,
                )
            result = discover_rules(
                Path(args.raw),
                Path(args.out),
                client,
                batch_size=args.batch_size,
                min_confidence=args.min_confidence,
                max_markets=args.max_markets,
                cache_path=Path(args.cache) if args.cache else None,
                context_market_limit=args.context_market_limit,
            )
            print(
                f"markets={result.markets_read} candidates={result.candidates_found} "
                f"implications={result.implications_written} "
                f"mutual_exclusions={result.mutual_exclusions_written} "
                f"equivalents={result.equivalents_written} "
                f"collectively_exhaustive={result.collectively_exhaustive_written} "
                f"complements={result.complements_written} out={args.out}"
            )
            return 0
    except (OSError, URLError, TimeoutError, RuntimeError, ValueError, OpenAIConfigError, OpenAIResponseError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    parser.print_help()
    return 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="poly-strategy")
    subparsers = parser.add_subparsers(dest="command")

    sample = subparsers.add_parser("sample", help="write a small synthetic snapshot")
    sample.add_argument("--out", required=True, help="output NDJSON path")

    backtest = subparsers.add_parser("backtest", help="replay NDJSON snapshots")
    backtest.add_argument("path", help="input NDJSON path")
    backtest.add_argument("--min-net-edge", type=float, default=0.0, help="minimum edge per share")
    backtest.add_argument("--max-capital-per-trade", type=float, help="cap simulated capital per opportunity")
    backtest.add_argument("--rules", help="JSON file with implication rules")

    collect = subparsers.add_parser("collect-polymarket", help="collect Polymarket public data")
    collect.add_argument("--out", required=True, help="output NDJSON path")
    collect.add_argument("--limit", type=int, default=100, help="Gamma market count when no token IDs are provided")
    collect.add_argument("--timeout", type=float, default=10.0, help="HTTP timeout in seconds")
    collect.add_argument("--proxy", help="HTTP proxy, for example 127.0.0.1:10808")
    collect.add_argument("--token-id", action="append", help="CLOB token ID to collect; can be repeated")

    collect_binaries = subparsers.add_parser(
        "collect-polymarket-binaries",
        help="collect Gamma markets plus YES/NO CLOB books into backtestable snapshots",
    )
    collect_binaries.add_argument("--out", required=True, help="output NDJSON path")
    collect_binaries.add_argument("--limit", type=int, default=100, help="Gamma market count to inspect")
    collect_binaries.add_argument("--timeout", type=float, default=10.0, help="HTTP timeout in seconds")
    collect_binaries.add_argument("--proxy", help="HTTP proxy, for example 127.0.0.1:10808")
    collect_binaries.add_argument("--iterations", type=int, default=1, help="number of collection iterations")
    collect_binaries.add_argument("--interval", type=float, default=0.0, help="seconds between iterations")

    collect_rule_markets = subparsers.add_parser(
        "collect-rule-markets",
        help="collect only markets referenced by a rule file",
    )
    collect_rule_markets.add_argument("--out", required=True, help="output NDJSON path")
    collect_rule_markets.add_argument("--gamma", required=True, help="raw Polymarket Gamma NDJSON path")
    collect_rule_markets.add_argument("--rules", required=True, help="rule JSON path")
    collect_rule_markets.add_argument("--timeout", type=float, default=10.0, help="HTTP timeout in seconds")
    collect_rule_markets.add_argument("--proxy", help="HTTP proxy, for example 127.0.0.1:10808")
    collect_rule_markets.add_argument("--iterations", type=int, default=1, help="number of collection iterations")
    collect_rule_markets.add_argument("--interval", type=float, default=0.0, help="seconds between iterations")

    monitor = subparsers.add_parser("monitor-rules", help="collect rule markets repeatedly and replay opportunities")
    monitor.add_argument("--out", required=True, help="output NDJSON path")
    monitor.add_argument("--gamma", required=True, help="raw Polymarket Gamma NDJSON path")
    monitor.add_argument("--rules", required=True, help="rule JSON path")
    monitor.add_argument("--timeout", type=float, default=10.0, help="HTTP timeout in seconds")
    monitor.add_argument("--proxy", help="HTTP proxy, for example 127.0.0.1:10808")
    monitor.add_argument("--iterations", type=int, default=1, help="number of monitor iterations")
    monitor.add_argument("--interval", type=float, default=5.0, help="seconds between iterations")
    monitor.add_argument("--min-net-edge", type=float, default=0.0, help="minimum edge per share")
    monitor.add_argument("--max-capital-per-trade", type=float, help="cap simulated capital per opportunity")

    discover = subparsers.add_parser("discover-rules", help="discover implication rules with an OpenAI-compatible API")
    discover.add_argument("--raw", required=True, help="input raw Polymarket Gamma NDJSON path")
    discover.add_argument("--out", required=True, help="output JSON rule path")
    discover.add_argument("--model", help="OpenAI model name; defaults to OPENAI_MODEL")
    discover.add_argument("--base-url", help="OpenAI-compatible base URL; defaults to OPENAI_BASE_URL or OpenAI")
    discover.add_argument("--batch-size", type=int, default=10, help="markets per LLM discovery batch")
    discover.add_argument("--min-confidence", type=float, default=0.95, help="minimum candidate confidence")
    discover.add_argument("--max-markets", type=int, help="limit input markets for a small run")
    discover.add_argument("--cache", help="existing rule JSON to reuse for incremental discovery")
    discover.add_argument("--context-market-limit", type=int, default=40, help="old markets to include with each new-market LLM batch")
    discover.add_argument("--timeout", type=float, default=60.0, help="HTTP timeout in seconds")
    discover.add_argument("--retries", type=int, default=2, help="retry count for retryable OpenAI-compatible API errors")
    discover.add_argument("--max-output-tokens", type=int, default=4000, help="Responses API max_output_tokens")
    discover.add_argument("--reasoning-effort", default="medium", help="Responses API reasoning effort")
    discover.add_argument("--verbosity", help="optional Responses API text verbosity")

    return parser


def _current_monitor_opportunities(result) -> list:
    current_ts = getattr(result, "last_snapshot_ts", None)
    if not current_ts:
        return []
    return [opportunity for opportunity in getattr(result, "opportunities", []) if opportunity.ts == current_ts]


def _current_monitor_runs(result) -> list:
    current_ts = getattr(result, "last_snapshot_ts", None)
    if not current_ts:
        return []
    return [run for run in getattr(result, "runs", []) if run.end_ts == current_ts]


def _print_current_monitor_details(opportunities, runs) -> None:
    for opportunity in opportunities:
        legs = ",".join(f"{leg.market_id}:{leg.token}:{leg.quantity:g}@{leg.average_price:g}" for leg in opportunity.legs)
        print(
            f"opportunity kind={opportunity.kind} qty={opportunity.quantity:g} "
            f"cost={opportunity.cost_per_share:.6f} edge={opportunity.net_edge_per_share:.6f} "
            f"total={opportunity.total_edge:.6f} legs={legs}"
        )

    for run in runs:
        print(
            f"run market={run.market_id} observations={run.observation_count} "
            f"duration_seconds={run.duration_seconds:.3f} max_edge={run.max_edge_per_share:.6f}"
        )


if __name__ == "__main__":
    raise SystemExit(main())
