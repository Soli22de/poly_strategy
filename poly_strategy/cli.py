import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import URLError

from poly_strategy.backtest import load_rule_set, replay_ndjson, snapshots_from_ndjson_lines
from poly_strategy.collectors import (
    collect_polymarket_binary_snapshots_loop,
    collect_polymarket_binary_snapshots_for_rules,
    collect_polymarket_binary_snapshots_for_rules_loop,
    collect_polymarket_books,
    collect_polymarket_gamma,
    write_sample_snapshot,
)
from poly_strategy.openai_rules import (
    OpenAIConfigError,
    OpenAIExhaustiveGroupVerifierClient,
    OpenAIResponseError,
    OpenAIRuleDiscoveryClient,
)
from poly_strategy.execution import (
    ExecutionConfigError,
    ExecutionError,
    PolymarketClobExecutor,
    build_execution_plan,
    plan_to_row,
)
from poly_strategy.exhaustive_groups import promote_exhaustive_groups, result_to_row
from poly_strategy.monitoring import IncrementalReplayState, stable_current_opportunities
from poly_strategy.paper_analysis import analyze_paper_monitor_report
from poly_strategy.paper import opportunity_key, select_paper_trades, trade_to_row, rejection_to_row, opportunity_to_row
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
                bankroll=args.bankroll,
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
                max_workers=args.book_workers,
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
                max_workers=args.book_workers,
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
                    args.book_workers,
                )
                result = replay_ndjson(
                    Path(args.out),
                    min_net_edge=args.min_net_edge,
                    max_capital_per_trade=args.max_capital_per_trade,
                    bankroll=args.bankroll,
                    rules_path=Path(args.rules),
                )
                current_opportunities = _current_monitor_opportunities(result)
                stable_opportunities = _stable_current_opportunities(
                    result,
                    args.min_run_observations,
                    args.min_run_seconds,
                )
                current_runs = _current_monitor_runs(result)
                print(
                    f"iteration={index + 1} snapshots={result.snapshot_count} "
                    f"current_opportunities={len(current_opportunities)} "
                    f"stable_opportunities={len(stable_opportunities)} "
                    f"opportunities={result.opportunity_count} paper_edge={result.paper_edge:.6f}"
                )
                _print_current_monitor_details(current_opportunities, current_runs)
                if index < args.iterations - 1 and args.interval > 0:
                    time.sleep(args.interval)
            print(f"wrote={total} out={args.out}")
            return 0
        if args.command == "paper-monitor":
            return _run_paper_monitor(args)
        if args.command == "paper-report":
            result = replay_ndjson(
                Path(args.path),
                min_net_edge=args.min_net_edge,
                max_capital_per_trade=args.max_capital_per_trade,
                bankroll=args.bankroll,
                rules_path=Path(args.rules) if args.rules else None,
            )
            row = _paper_report_row(result)
            if args.out:
                Path(args.out).parent.mkdir(parents=True, exist_ok=True)
                Path(args.out).write_text(json.dumps(row, indent=2, sort_keys=True) + "\n")
                print(f"wrote=1 out={args.out}")
            else:
                print(json.dumps(row, sort_keys=True))
            return 0
        if args.command == "paper-analyze":
            row = analyze_paper_monitor_report(
                Path(args.path),
                top_n=args.top,
                snapshots_path=Path(args.snapshots) if args.snapshots else None,
                rules_path=Path(args.rules) if args.rules else None,
                near_miss_top_n=args.near_miss_top,
                near_miss_min_net_edge=args.near_miss_min_net_edge,
            )
            if args.out:
                Path(args.out).parent.mkdir(parents=True, exist_ok=True)
                Path(args.out).write_text(json.dumps(row, indent=2, sort_keys=True) + "\n")
                print(f"wrote=1 out={args.out}")
            else:
                print(json.dumps(row, sort_keys=True))
            return 0
        if args.command == "execute-latest":
            result = replay_ndjson(
                Path(args.path),
                min_net_edge=args.min_net_edge,
                max_capital_per_trade=args.max_capital_per_trade,
                bankroll=args.bankroll,
                rules_path=Path(args.rules) if args.rules else None,
            )
            rows = _execution_plan_rows(result, args)
            _write_jsonl_or_stdout(rows, args.out)
            if args.out:
                print(f"wrote={len(rows)} out={args.out}")
            return 0
        if args.command == "execute-rules-once":
            count = collect_polymarket_binary_snapshots_for_rules(
                Path(args.snapshots_out),
                Path(args.gamma),
                Path(args.rules),
                args.timeout,
                args.proxy,
                args.book_workers,
            )
            result = replay_ndjson(
                Path(args.snapshots_out),
                min_net_edge=args.min_net_edge,
                max_capital_per_trade=args.max_capital_per_trade,
                bankroll=args.bankroll,
                rules_path=Path(args.rules),
            )
            rows = _execution_plan_rows(result, args)
            _write_jsonl_or_stdout(rows, args.out)
            if args.out:
                print(f"snapshots={count} plans={len(rows)} out={args.out}")
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
        if args.command == "verify-exhaustive-groups":
            model = args.model or os.environ.get("OPENAI_MODEL")
            if not model:
                print("error: model is required via --model or OPENAI_MODEL", file=sys.stderr)
                return 1
            client = OpenAIExhaustiveGroupVerifierClient(
                model=model,
                timeout=args.timeout,
                base_url=args.base_url,
                retries=args.retries,
                max_output_tokens=args.max_output_tokens,
                reasoning_effort=args.reasoning_effort,
                verbosity=args.verbosity,
            )
            result = promote_exhaustive_groups(
                Path(args.gamma),
                Path(args.rules_in),
                Path(args.rules_out),
                Path(args.snapshots),
                client,
                min_net_edge=args.min_net_edge,
                top_n=args.top,
                min_confidence=args.min_confidence,
            )
            row = result_to_row(result)
            if args.report_out:
                Path(args.report_out).parent.mkdir(parents=True, exist_ok=True)
                Path(args.report_out).write_text(json.dumps(row, indent=2, sort_keys=True) + "\n")
            print(
                f"candidates={result.candidates_found} verified={result.verified_count} "
                f"added={result.added_count} rejected={result.rejected_count} "
                f"skipped_existing={result.skipped_existing_count} out={args.rules_out}"
            )
            return 0
    except (
        OSError,
        URLError,
        TimeoutError,
        RuntimeError,
        ValueError,
        OpenAIConfigError,
        OpenAIResponseError,
        ExecutionConfigError,
        ExecutionError,
    ) as exc:
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
    backtest.add_argument("--bankroll", type=float, help="cap simulated bankroll per timestamp batch")
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
    collect_binaries.add_argument("--book-workers", type=int, default=1, help="parallel CLOB book fetch workers")

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
    collect_rule_markets.add_argument("--book-workers", type=int, default=1, help="parallel CLOB book fetch workers")

    monitor = subparsers.add_parser("monitor-rules", help="collect rule markets repeatedly and replay opportunities")
    monitor.add_argument("--out", required=True, help="output NDJSON path")
    monitor.add_argument("--gamma", required=True, help="raw Polymarket Gamma NDJSON path")
    monitor.add_argument("--rules", required=True, help="rule JSON path")
    monitor.add_argument("--timeout", type=float, default=10.0, help="HTTP timeout in seconds")
    monitor.add_argument("--proxy", help="HTTP proxy, for example 127.0.0.1:10808")
    monitor.add_argument("--iterations", type=int, default=1, help="number of monitor iterations")
    monitor.add_argument("--interval", type=float, default=5.0, help="seconds between iterations")
    monitor.add_argument("--book-workers", type=int, default=1, help="parallel CLOB book fetch workers")
    monitor.add_argument("--min-net-edge", type=float, default=0.0, help="minimum edge per share")
    monitor.add_argument("--max-capital-per-trade", type=float, help="cap simulated capital per opportunity")
    monitor.add_argument("--bankroll", type=float, help="cap simulated bankroll per monitor iteration")
    monitor.add_argument("--min-run-observations", type=int, default=1, help="stable opportunity observations to report")
    monitor.add_argument("--min-run-seconds", type=float, default=0.0, help="stable opportunity duration to report")

    paper_monitor = subparsers.add_parser(
        "paper-monitor",
        help="run a resilient targeted collection loop and append paper-trading JSONL reports",
    )
    paper_monitor.add_argument("--gamma", required=True, help="raw Polymarket Gamma NDJSON path")
    paper_monitor.add_argument("--rules", required=True, help="rule JSON path")
    paper_monitor.add_argument("--snapshots-out", required=True, help="append refreshed snapshots here")
    paper_monitor.add_argument("--report-out", required=True, help="append per-iteration paper reports here")
    paper_monitor.add_argument("--timeout", type=float, default=10.0, help="HTTP timeout in seconds")
    paper_monitor.add_argument("--proxy", help="HTTP proxy, for example 127.0.0.1:10808")
    paper_monitor.add_argument("--iterations", type=int, default=1, help="number of monitor iterations")
    paper_monitor.add_argument("--interval", type=float, default=5.0, help="seconds between iterations")
    paper_monitor.add_argument("--book-workers", type=int, default=1, help="parallel CLOB book fetch workers")
    paper_monitor.add_argument("--min-net-edge", type=float, default=0.0, help="minimum edge per share")
    paper_monitor.add_argument("--max-capital-per-trade", type=float, help="cap simulated capital per opportunity")
    paper_monitor.add_argument("--bankroll", type=float, help="cap simulated bankroll per monitor iteration")
    paper_monitor.add_argument("--min-run-observations", type=int, default=1, help="stable opportunity observations to report")
    paper_monitor.add_argument("--min-run-seconds", type=float, default=0.0, help="stable opportunity duration to report")
    paper_monitor.add_argument("--skip-book-errors", action="store_true", help="skip markets whose CLOB books fail")
    paper_monitor.add_argument("--continue-on-error", action="store_true", help="record iteration errors and keep looping")
    paper_monitor.add_argument(
        "--max-opportunities-per-iteration",
        type=int,
        default=10,
        help="maximum current/stable opportunities to include in each report row",
    )
    paper_monitor.add_argument(
        "--max-errors-per-iteration",
        type=int,
        default=20,
        help="maximum collection error details to include in each report row",
    )

    report = subparsers.add_parser("paper-report", help="write a JSON paper-trading replay report")
    report.add_argument("path", help="input NDJSON path")
    report.add_argument("--rules", help="JSON file with discovered rules")
    report.add_argument("--out", help="output JSON path; prints JSON to stdout when omitted")
    report.add_argument("--min-net-edge", type=float, default=0.0, help="minimum edge per share")
    report.add_argument("--max-capital-per-trade", type=float, help="cap simulated capital per opportunity")
    report.add_argument("--bankroll", type=float, help="cap simulated bankroll per timestamp batch")

    analyze = subparsers.add_parser("paper-analyze", help="summarize a paper-monitor JSONL report")
    analyze.add_argument("path", help="paper-monitor JSONL report path")
    analyze.add_argument("--out", help="output JSON path; prints JSON to stdout when omitted")
    analyze.add_argument("--top", type=int, default=10, help="top opportunities and markets to include")
    analyze.add_argument("--snapshots", help="optional snapshot NDJSON path for near-miss diagnostics")
    analyze.add_argument("--rules", help="optional rule JSON path for relation near-miss diagnostics")
    analyze.add_argument("--near-miss-top", type=int, default=10, help="near-miss rows to include")
    analyze.add_argument(
        "--near-miss-min-net-edge",
        type=float,
        default=0.0,
        help="minimum net edge threshold used to classify near misses",
    )

    execute = subparsers.add_parser("execute-latest", help="build or submit execution plans for latest opportunities")
    execute.add_argument("path", help="input NDJSON snapshot path")
    execute.add_argument("--rules", help="JSON file with discovered rules")
    execute.add_argument("--out", help="output NDJSON execution plan path")
    execute.add_argument("--min-net-edge", type=float, default=0.0, help="minimum edge per share")
    execute.add_argument("--max-capital-per-trade", type=float, help="cap capital per opportunity")
    execute.add_argument("--bankroll", type=float, help="cap simulated bankroll for latest timestamp")
    execute.add_argument("--min-run-observations", type=int, default=1, help="minimum latest-run observations before planning")
    execute.add_argument("--min-run-seconds", type=float, default=0.0, help="minimum latest-run duration before planning")
    execute.add_argument("--max-trades", type=int, default=1, help="maximum plans to build or submit")
    execute.add_argument("--slippage-bps", type=float, default=50.0, help="buy limit cushion in basis points")
    execute.add_argument("--tick-size", default="0.01", help="CLOB market tick size")
    execute.add_argument("--order-type", default="FOK", help="SDK order type, default FOK")
    execute.add_argument("--neg-risk", action="store_true", help="set neg_risk option for SDK order creation")
    execute.add_argument("--live", action="store_true", help="submit orders through py-clob-client-v2")
    execute.add_argument("--allow-live", action="store_true", help="second live-trading confirmation flag")
    execute.add_argument("--allow-nonatomic-live", action="store_true", help="acknowledge multi-leg live order risk")

    execute_once = subparsers.add_parser(
        "execute-rules-once",
        help="refresh rule-market books once, then build or submit latest execution plans",
    )
    execute_once.add_argument("--gamma", required=True, help="raw Polymarket Gamma NDJSON path")
    execute_once.add_argument("--rules", required=True, help="rule JSON path")
    execute_once.add_argument("--snapshots-out", required=True, help="append refreshed snapshots here")
    execute_once.add_argument("--out", help="output NDJSON execution plan path")
    execute_once.add_argument("--timeout", type=float, default=10.0, help="HTTP timeout in seconds")
    execute_once.add_argument("--proxy", help="HTTP proxy, for example 127.0.0.1:10808")
    execute_once.add_argument("--book-workers", type=int, default=1, help="parallel CLOB book fetch workers")
    execute_once.add_argument("--min-net-edge", type=float, default=0.0, help="minimum edge per share")
    execute_once.add_argument("--max-capital-per-trade", type=float, help="cap capital per opportunity")
    execute_once.add_argument("--bankroll", type=float, help="cap simulated bankroll for latest timestamp")
    execute_once.add_argument("--min-run-observations", type=int, default=1, help="minimum latest-run observations before planning")
    execute_once.add_argument("--min-run-seconds", type=float, default=0.0, help="minimum latest-run duration before planning")
    execute_once.add_argument("--max-trades", type=int, default=1, help="maximum plans to build or submit")
    execute_once.add_argument("--slippage-bps", type=float, default=50.0, help="buy limit cushion in basis points")
    execute_once.add_argument("--tick-size", default="0.01", help="CLOB market tick size")
    execute_once.add_argument("--order-type", default="FOK", help="SDK order type, default FOK")
    execute_once.add_argument("--neg-risk", action="store_true", help="set neg_risk option for SDK order creation")
    execute_once.add_argument("--live", action="store_true", help="submit orders through py-clob-client-v2")
    execute_once.add_argument("--allow-live", action="store_true", help="second live-trading confirmation flag")
    execute_once.add_argument("--allow-nonatomic-live", action="store_true", help="acknowledge multi-leg live order risk")

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

    verify_groups = subparsers.add_parser(
        "verify-exhaustive-groups",
        help="verify near-miss exhaustive group candidates and write promoted rules",
    )
    verify_groups.add_argument("--gamma", required=True, help="input raw Polymarket Gamma NDJSON path")
    verify_groups.add_argument("--rules-in", required=True, help="existing rule JSON path")
    verify_groups.add_argument("--rules-out", required=True, help="output rule JSON path")
    verify_groups.add_argument("--snapshots", required=True, help="snapshot NDJSON path for near-miss candidates")
    verify_groups.add_argument("--report-out", help="optional JSON verification report path")
    verify_groups.add_argument("--model", help="OpenAI model name; defaults to OPENAI_MODEL")
    verify_groups.add_argument("--base-url", help="OpenAI-compatible base URL; defaults to OPENAI_BASE_URL or OpenAI")
    verify_groups.add_argument("--min-net-edge", type=float, default=0.002, help="minimum diagnostic net edge to verify")
    verify_groups.add_argument("--top", type=int, default=10, help="maximum diagnostic groups to verify")
    verify_groups.add_argument("--min-confidence", type=float, default=0.95, help="minimum verification confidence")
    verify_groups.add_argument("--timeout", type=float, default=60.0, help="HTTP timeout in seconds")
    verify_groups.add_argument("--retries", type=int, default=2, help="retry count for retryable OpenAI-compatible API errors")
    verify_groups.add_argument("--max-output-tokens", type=int, default=2000, help="Responses API max_output_tokens")
    verify_groups.add_argument("--reasoning-effort", default="medium", help="Responses API reasoning effort")
    verify_groups.add_argument("--verbosity", help="optional Responses API text verbosity")

    return parser


def _run_paper_monitor(args) -> int:
    if args.iterations < 1:
        raise ValueError("iterations must be at least 1")
    if args.interval < 0:
        raise ValueError("interval must be non-negative")
    if args.max_opportunities_per_iteration < 0:
        raise ValueError("max opportunities per iteration must be non-negative")
    if args.max_errors_per_iteration < 0:
        raise ValueError("max errors per iteration must be non-negative")

    snapshots_path = Path(args.snapshots_out)
    report_path = Path(args.report_out)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    rule_set = load_rule_set(Path(args.rules))
    replay_state = IncrementalReplayState()
    snapshot_offset = _file_size(snapshots_path)

    total_snapshots_collected = 0
    completed_iterations = 0
    error_iterations = 0

    for index in range(args.iterations):
        iteration = index + 1
        collection_errors = []
        phase = "collect"
        snapshots_collected = 0
        try:
            snapshots_collected = collect_polymarket_binary_snapshots_for_rules(
                snapshots_path,
                Path(args.gamma),
                Path(args.rules),
                args.timeout,
                args.proxy,
                args.book_workers,
                skip_book_errors=args.skip_book_errors,
                errors=collection_errors,
            )
            total_snapshots_collected += snapshots_collected
            phase = "scan"
            appended_text, new_snapshot_offset = _read_appended_text(snapshots_path, snapshot_offset)
            snapshots = list(snapshots_from_ndjson_lines(appended_text.splitlines()))
            snapshot_offset = new_snapshot_offset
            if snapshots_collected != len(snapshots):
                collection_errors.append(
                    {
                        "kind": "snapshot_count_mismatch",
                        "message": "collector count did not match appended binary snapshot rows",
                        "collector_count": snapshots_collected,
                        "parsed_count": len(snapshots),
                    }
                )
            batch_result = replay_state.apply_snapshots(
                snapshots,
                rule_set,
                min_net_edge=args.min_net_edge,
                max_capital_per_trade=args.max_capital_per_trade,
                bankroll=args.bankroll,
            )
            current_opportunities = batch_result.current_opportunities
            stable_opportunities = stable_current_opportunities(
                current_opportunities,
                batch_result.current_runs,
                min_run_observations=args.min_run_observations,
                min_run_seconds=args.min_run_seconds,
            )
            stable_selection = select_paper_trades(
                stable_opportunities,
                max_capital_per_trade=args.max_capital_per_trade,
                bankroll=args.bankroll,
            )
            row = _paper_monitor_iteration_row(
                iteration,
                snapshots_collected,
                replay_state,
                current_opportunities,
                stable_opportunities,
                stable_selection,
                batch_result.current_runs,
                collection_errors,
                args,
            )
            phase = "write_report"
            _append_jsonl_row(report_path, row)
            completed_iterations += 1
            print(
                f"iteration={iteration} snapshots_collected={snapshots_collected} "
                f"current_opportunities={len(current_opportunities)} "
                f"stable_opportunities={len(stable_opportunities)} "
                f"stable_paper_edge={row['stable_paper_edge']:.6f} "
                f"errors={len(collection_errors)}"
            )
        except (OSError, URLError, TimeoutError, RuntimeError, ValueError) as exc:
            if not args.continue_on_error:
                raise
            error_iterations += 1
            row = _paper_monitor_error_row(iteration, exc, collection_errors, args, phase, snapshots_collected)
            _append_jsonl_row(report_path, row)
            print(f"iteration={iteration} error={exc}", file=sys.stderr)

        if index < args.iterations - 1 and args.interval > 0:
            time.sleep(args.interval)

    summary = _paper_monitor_summary_row(
        args,
        total_snapshots_collected,
        completed_iterations,
        error_iterations,
        replay_state,
    )
    _append_jsonl_row(report_path, summary)
    print(
        f"wrote_snapshots={total_snapshots_collected} completed_iterations={completed_iterations} "
        f"error_iterations={error_iterations} report={args.report_out}"
    )
    return 0


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


def _stable_current_opportunities(result, min_run_observations: int = 1, min_run_seconds: float = 0.0) -> list:
    current = _current_monitor_opportunities(result)
    if min_run_observations <= 1 and min_run_seconds <= 0:
        return current

    stable_keys = {
        run.key
        for run in _current_monitor_runs(result)
        if run.observation_count >= min_run_observations and run.duration_seconds >= min_run_seconds
    }
    return [opportunity for opportunity in current if opportunity_key(opportunity) in stable_keys]


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


def _paper_report_row(result) -> dict:
    return {
        "type": "paper_report",
        "snapshot_count": result.snapshot_count,
        "opportunity_count": result.opportunity_count,
        "paper_trade_count": result.paper_trade_count,
        "paper_rejection_count": len(result.paper_rejections),
        "paper_capital_used": result.paper_capital_used,
        "paper_edge": result.paper_edge,
        "paper_roi": result.paper_edge / result.paper_capital_used if result.paper_capital_used > 0 else 0.0,
        "last_snapshot_ts": result.last_snapshot_ts,
        "by_kind": _paper_summary_by_kind(result),
        "opportunities": [opportunity_to_row(opportunity) for opportunity in result.opportunities],
        "paper_trades": [trade_to_row(trade) for trade in result.paper_trades],
        "paper_rejections": [rejection_to_row(rejection) for rejection in result.paper_rejections],
        "runs": [_run_to_row(run) for run in result.runs],
    }


def _paper_monitor_iteration_row(
    iteration: int,
    snapshots_collected: int,
    result,
    current_opportunities: list,
    stable_opportunities: list,
    stable_selection,
    current_runs: list,
    errors: list,
    args,
) -> dict:
    stable_paper_capital_used = sum(trade.capital_used for trade in stable_selection.trades)
    stable_paper_edge = sum(trade.edge for trade in stable_selection.trades)
    top_current = _top_opportunity_rows(current_opportunities, args.max_opportunities_per_iteration)
    top_stable = _top_opportunity_rows(stable_opportunities, args.max_opportunities_per_iteration)
    top_stable_trades = [
        trade_to_row(trade)
        for trade in sorted(stable_selection.trades, key=lambda trade: trade.roi, reverse=True)[
            : args.max_opportunities_per_iteration
        ]
    ]
    return {
        "type": "paper_monitor_iteration",
        "ts": _utc_now(),
        "iteration": iteration,
        "snapshots_collected": snapshots_collected,
        "snapshot_count": result.snapshot_count,
        "opportunity_count": result.opportunity_count,
        "current_opportunity_count": len(current_opportunities),
        "stable_opportunity_count": len(stable_opportunities),
        "paper_trade_count": result.paper_trade_count,
        "paper_rejection_count": len(result.paper_rejections),
        "paper_capital_used": result.paper_capital_used,
        "paper_edge": result.paper_edge,
        "paper_roi": result.paper_edge / result.paper_capital_used if result.paper_capital_used > 0 else 0.0,
        "stable_paper_trade_count": len(stable_selection.trades),
        "stable_paper_rejection_count": len(stable_selection.rejections),
        "stable_paper_capital_used": stable_paper_capital_used,
        "stable_paper_edge": stable_paper_edge,
        "stable_paper_roi": stable_paper_edge / stable_paper_capital_used if stable_paper_capital_used > 0 else 0.0,
        "last_snapshot_ts": result.last_snapshot_ts,
        "current_opportunities": top_current,
        "stable_opportunities": top_stable,
        "stable_paper_trades": top_stable_trades,
        "current_runs": [_run_to_row(run) for run in current_runs],
        "error_count": len(errors),
        "errors": errors[: args.max_errors_per_iteration],
    }


def _paper_monitor_error_row(
    iteration: int,
    exc: Exception,
    errors: list,
    args,
    phase: str,
    snapshots_collected: int,
) -> dict:
    return {
        "type": "paper_monitor_iteration_error",
        "ts": _utc_now(),
        "iteration": iteration,
        "phase": phase,
        "snapshots_collected": snapshots_collected,
        "error_type": exc.__class__.__name__,
        "message": str(exc),
        "error_count": len(errors),
        "errors": errors[: args.max_errors_per_iteration],
    }


def _paper_monitor_summary_row(args, snapshots_collected: int, completed_iterations: int, error_iterations: int, result) -> dict:
    row = {
        "type": "paper_monitor_summary",
        "ts": _utc_now(),
        "iterations_requested": args.iterations,
        "completed_iterations": completed_iterations,
        "error_iterations": error_iterations,
        "snapshots_collected": snapshots_collected,
        "snapshots_path": args.snapshots_out,
        "report_path": args.report_out,
    }
    if result is not None:
        row.update(
            {
                "snapshot_count": result.snapshot_count,
                "opportunity_count": result.opportunity_count,
                "paper_trade_count": result.paper_trade_count,
                "paper_capital_used": result.paper_capital_used,
                "paper_edge": result.paper_edge,
                "paper_roi": result.paper_edge / result.paper_capital_used if result.paper_capital_used > 0 else 0.0,
                "last_snapshot_ts": result.last_snapshot_ts,
                "run_count": len(result.runs),
                "by_kind": _paper_summary_by_kind(result),
            }
        )
    return row


def _top_opportunity_rows(opportunities: list, limit: int) -> list:
    if limit == 0:
        return []
    return [
        opportunity_to_row(opportunity)
        for opportunity in sorted(opportunities, key=lambda opportunity: opportunity.net_edge_per_share, reverse=True)[:limit]
    ]


def _run_to_row(run) -> dict:
    return {
        "key": run.key,
        "market_id": run.market_id,
        "start_ts": run.start_ts,
        "end_ts": run.end_ts,
        "observation_count": run.observation_count,
        "duration_seconds": run.duration_seconds,
        "max_edge_per_share": run.max_edge_per_share,
    }


def _paper_summary_by_kind(result) -> list:
    summary = {}
    for opportunity in result.opportunities:
        row = summary.setdefault(
            opportunity.kind,
            {
                "kind": opportunity.kind,
                "opportunity_count": 0,
                "paper_trade_count": 0,
                "paper_rejection_count": 0,
                "total_edge": 0.0,
                "paper_capital_used": 0.0,
                "paper_edge": 0.0,
                "max_edge_per_share": 0.0,
                "max_run_duration_seconds": 0.0,
            },
        )
        row["opportunity_count"] += 1
        row["total_edge"] += opportunity.total_edge
        row["max_edge_per_share"] = max(row["max_edge_per_share"], opportunity.net_edge_per_share)

    for trade in result.paper_trades:
        row = summary.setdefault(trade.opportunity.kind, {"kind": trade.opportunity.kind})
        row.setdefault("opportunity_count", 0)
        row.setdefault("paper_rejection_count", 0)
        row.setdefault("total_edge", 0.0)
        row.setdefault("max_edge_per_share", 0.0)
        row.setdefault("max_run_duration_seconds", 0.0)
        row["paper_trade_count"] = row.get("paper_trade_count", 0) + 1
        row["paper_capital_used"] = row.get("paper_capital_used", 0.0) + trade.capital_used
        row["paper_edge"] = row.get("paper_edge", 0.0) + trade.edge

    for rejection in result.paper_rejections:
        row = summary.setdefault(rejection.opportunity.kind, {"kind": rejection.opportunity.kind})
        row["paper_rejection_count"] = row.get("paper_rejection_count", 0) + 1

    max_run_duration_by_key = {}
    for run in result.runs:
        max_run_duration_by_key[run.key] = max(max_run_duration_by_key.get(run.key, 0.0), run.duration_seconds)
    for opportunity in result.opportunities:
        duration = max_run_duration_by_key.get(opportunity_key(opportunity))
        if duration is None:
            continue
        row = summary[opportunity.kind]
        row["max_run_duration_seconds"] = max(row["max_run_duration_seconds"], duration)

    return sorted(summary.values(), key=lambda row: (row["kind"]))


def _execution_plan_rows(result, args) -> list:
    selection = select_paper_trades(
        _stable_current_opportunities(
            result,
            args.min_run_observations,
            args.min_run_seconds,
        ),
        max_capital_per_trade=args.max_capital_per_trade,
        bankroll=args.bankroll,
    )
    plans = [
        build_execution_plan(
            trade,
            slippage_bps=args.slippage_bps,
            tick_size=args.tick_size,
            neg_risk=args.neg_risk,
            order_type=args.order_type,
            dry_run=not args.live,
        )
        for trade in selection.trades[: args.max_trades]
    ]
    rows = [plan_to_row(plan) for plan in plans]
    if args.live and rows:
        if not args.allow_live:
            raise ExecutionConfigError("--allow-live is required with --live")
        executor = PolymarketClobExecutor()
        for row, plan in zip(rows, plans):
            row["responses"] = executor.post_plan(
                plan,
                allow_live=True,
                allow_nonatomic=args.allow_nonatomic_live,
            )
    return rows


def _write_jsonl_or_stdout(rows: list, out: str) -> None:
    if out:
        path = Path(out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + ("\n" if rows else ""))
    else:
        for row in rows:
            print(json.dumps(row, sort_keys=True))


def _append_jsonl_row(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")


def _file_size(path: Path) -> int:
    if not path.exists():
        return 0
    return path.stat().st_size


def _read_appended_text(path: Path, offset: int) -> tuple:
    if not path.exists():
        return "", offset
    with path.open("rb") as handle:
        handle.seek(offset)
        data = handle.read()
        return data.decode("utf-8"), handle.tell()


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


if __name__ == "__main__":
    raise SystemExit(main())
