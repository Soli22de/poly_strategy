import argparse
import os
import sys
from pathlib import Path
from urllib.error import URLError

from poly_strategy.backtest import replay_ndjson
from poly_strategy.collectors import (
    collect_polymarket_binary_snapshots_loop,
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
        if args.command == "discover-rules":
            model = args.model or os.environ.get("OPENAI_MODEL")
            if not model:
                print("error: model is required via --model or OPENAI_MODEL", file=sys.stderr)
                return 1
            client = OpenAIRuleDiscoveryClient(
                model=model,
                timeout=args.timeout,
                base_url=args.base_url,
            )
            result = discover_rules(
                Path(args.raw),
                Path(args.out),
                client,
                batch_size=args.batch_size,
                min_confidence=args.min_confidence,
                max_markets=args.max_markets,
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
    except (OSError, URLError, TimeoutError, RuntimeError, OpenAIConfigError, OpenAIResponseError) as exc:
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

    discover = subparsers.add_parser("discover-rules", help="discover implication rules with an OpenAI-compatible API")
    discover.add_argument("--raw", required=True, help="input raw Polymarket Gamma NDJSON path")
    discover.add_argument("--out", required=True, help="output JSON rule path")
    discover.add_argument("--model", help="OpenAI model name; defaults to OPENAI_MODEL")
    discover.add_argument("--base-url", help="OpenAI-compatible base URL; defaults to OPENAI_BASE_URL or OpenAI")
    discover.add_argument("--batch-size", type=int, default=20, help="markets per LLM discovery batch")
    discover.add_argument("--min-confidence", type=float, default=0.95, help="minimum candidate confidence")
    discover.add_argument("--max-markets", type=int, help="limit input markets for a small run")
    discover.add_argument("--timeout", type=float, default=60.0, help="HTTP timeout in seconds")

    return parser


if __name__ == "__main__":
    raise SystemExit(main())
