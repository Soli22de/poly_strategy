import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import URLError

from poly_strategy.alerts import latest_alert_market_ids, latest_monitor_alerts, write_alerts
from poly_strategy.backtest import load_rule_set, replay_ndjson, snapshots_from_ndjson_lines
from poly_strategy.collectors import (
    collect_polymarket_binary_snapshots_loop,
    collect_polymarket_binary_snapshots_for_market_ids,
    collect_polymarket_binary_snapshots_for_rules,
    collect_polymarket_binary_snapshots_for_rules_loop,
    collect_polymarket_books,
    collect_polymarket_data_trades,
    collect_kalshi_markets,
    collect_kalshi_markets_by_event_tickers,
    collect_kalshi_markets_pages,
    collect_kalshi_orderbooks,
    collect_polymarket_gamma_pages,
    collect_polymarket_gamma_markets_by_id,
    kalshi_binary_snapshot_rows_from_orderbook_lines,
    market_id_alias_map,
    raw_gamma_markets_from_ndjson,
    write_kalshi_binary_snapshots,
    write_sample_snapshot,
)
from poly_strategy.cross_platform import (
    apply_cross_platform_verifications,
    cross_platform_pairs,
    cross_platform_signal_rows,
    event_tickers_from_cross_platform_candidates,
    expand_cross_platform_event_candidates,
    match_polymarket_kalshi_markets,
    normalize_cross_platform_match_report,
    opportunity_match_report_from_scan,
    write_cross_platform_signal_rows,
)
from poly_strategy.openai_rules import (
    OpenAIConfigError,
    OpenAICrossPlatformVerifierClient,
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
    reconcile_execution_responses,
)
from poly_strategy.execution_checks import pretrade_check_row
from poly_strategy.external_signals import (
    external_signal_report,
    ingest_external_signals,
    polymarket_market_ids_from_external_signals,
)
from poly_strategy.exhaustive_groups import promotion_candidate_count, promote_exhaustive_groups, result_to_row
from poly_strategy.maker import (
    maker_adaptive_quote_report,
    maker_fill_sim_report,
    maker_hedge_scan_report,
    maker_hedge_sim_report,
    maker_hybrid_scan_report,
    maker_hybrid_sim_report,
    maker_hybrid_tape_sim_report,
    maker_scan_report,
)
from poly_strategy.monitoring import IncrementalReplayState, stable_current_opportunities
from poly_strategy.notifications import notify_alerts
from poly_strategy.paper_analysis import analyze_paper_monitor_report, optimization_target_market_ids
from poly_strategy.paper import opportunity_key, select_paper_trades, trade_to_row, rejection_to_row, opportunity_to_row
from poly_strategy.realtime import (
    DEFAULT_WS_MAX_SIZE,
    POLYMARKET_MARKET_WS_URL,
    monitor_polymarket_watchlist,
    stream_polymarket_watchlist,
)
from poly_strategy.risk import risk_check_execution_plan, update_risk_state_from_execution_result
from poly_strategy.rule_discovery import discover_rules
from poly_strategy.scanner import find_cross_venue_same_binary
from poly_strategy.success import success_status_report, write_success_status
from poly_strategy.watchlist import build_polymarket_watchlist, write_watchlist


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
                gamma_path=Path(args.gamma) if args.gamma else None,
                min_paper_roi=args.min_paper_roi,
                min_paper_edge=args.min_paper_edge,
                min_paper_quantity=args.min_paper_quantity,
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
            if args.token_id and args.market_id:
                raise ValueError("--token-id and --market-id cannot be used together")
            if args.token_id:
                count = collect_polymarket_books(Path(args.out), args.token_id, args.timeout, args.proxy)
            elif args.market_id:
                count = collect_polymarket_gamma_markets_by_id(
                    Path(args.out),
                    args.market_id,
                    args.timeout,
                    args.proxy,
                )
            else:
                count = collect_polymarket_gamma_pages(
                    Path(args.out),
                    args.limit,
                    args.pages,
                    args.timeout,
                    args.proxy,
                    args.offset,
                )
            print(f"wrote={count} out={args.out}")
            return 0
        if args.command == "collect-polymarket-binaries":
            market_ids = list(args.market_id or [])
            if args.market_ids_file:
                market_ids.extend(_read_lines(Path(args.market_ids_file)))
            if market_ids:
                if not args.gamma:
                    raise ValueError("--gamma is required when collecting specific market IDs")
                count = 0
                for index in range(args.iterations):
                    count += collect_polymarket_binary_snapshots_for_market_ids(
                        Path(args.out),
                        Path(args.gamma),
                        market_ids,
                        args.timeout,
                        args.proxy,
                        max_workers=args.book_workers,
                        skip_book_errors=args.skip_book_errors,
                        refresh_missing_gamma=args.refresh_missing_gamma,
                        expand_neg_risk_groups=not args.no_expand_neg_risk_groups,
                        max_markets=args.max_markets,
                    )
                    if index < args.iterations - 1 and args.interval > 0:
                        time.sleep(args.interval)
            else:
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
        if args.command == "collect-polymarket-trades":
            market_ids = list(args.market_id or [])
            if args.market_ids_file:
                market_ids.extend(_read_lines(Path(args.market_ids_file)))
            if args.hybrid_scan:
                market_ids.extend(_market_ids_from_hybrid_scan(Path(args.hybrid_scan), args.top_markets))
            collection_errors = []
            count = collect_polymarket_data_trades(
                Path(args.out),
                Path(args.gamma),
                market_ids,
                limit=args.limit,
                timeout=args.timeout,
                proxy=args.proxy,
                side=args.side,
                offset=args.offset,
                per_market=args.per_market,
                max_workers=args.trade_workers,
                skip_errors=args.skip_errors,
                errors=collection_errors,
                retries=args.retries,
            )
            print(f"wrote={count} errors={len(collection_errors)} out={args.out}")
            return 0
        if args.command == "collect-kalshi":
            if args.all_pages:
                count = collect_kalshi_markets_pages(
                    Path(args.out),
                    args.limit,
                    args.timeout,
                    args.proxy,
                    cursor=args.cursor,
                    status=args.status,
                    tickers=args.ticker,
                    pages=None,
                )
            elif args.pages and args.pages > 1:
                count = collect_kalshi_markets_pages(
                    Path(args.out),
                    args.limit,
                    args.timeout,
                    args.proxy,
                    cursor=args.cursor,
                    status=args.status,
                    tickers=args.ticker,
                    pages=args.pages,
                )
            else:
                count = collect_kalshi_markets(
                    Path(args.out),
                    args.limit,
                    args.timeout,
                    args.proxy,
                    cursor=args.cursor,
                    status=args.status,
                    tickers=args.ticker,
                )
            print(f"wrote={count} out={args.out}")
            return 0
        if args.command == "collect-kalshi-event-markets":
            event_tickers = list(args.event_ticker or [])
            if args.candidates:
                event_tickers.extend(
                    event_tickers_from_cross_platform_candidates(json.loads(Path(args.candidates).read_text()))
                )
            count = collect_kalshi_markets_by_event_tickers(
                Path(args.out),
                event_tickers,
                args.limit,
                args.timeout,
                args.proxy,
                status=args.status,
            )
            print(f"events={len(set(event_tickers))} wrote={count} out={args.out}")
            return 0
        if args.command == "collect-kalshi-orderbooks":
            tickers = list(args.ticker or [])
            if args.tickers_file:
                tickers.extend(_read_lines(Path(args.tickers_file)))
            count = collect_kalshi_orderbooks(Path(args.out), tickers, args.timeout, args.proxy)
            print(f"wrote={count} out={args.out}")
            return 0
        if args.command == "kalshi-snapshots":
            count = write_kalshi_binary_snapshots(Path(args.orderbooks), Path(args.out))
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
                expand_neg_risk_groups=not args.no_expand_neg_risk_groups,
                max_markets=args.max_markets,
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
                    expand_neg_risk_groups=not args.no_expand_neg_risk_groups,
                    max_markets=args.max_markets,
                )
                result = replay_ndjson(
                    Path(args.out),
                    min_net_edge=args.min_net_edge,
                    max_capital_per_trade=args.max_capital_per_trade,
                    bankroll=args.bankroll,
                    rules_path=Path(args.rules),
                    gamma_path=Path(args.gamma),
                    min_paper_roi=args.min_paper_roi,
                    min_paper_edge=args.min_paper_edge,
                    min_paper_quantity=args.min_paper_quantity,
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
                gamma_path=Path(args.gamma) if args.gamma else None,
                min_paper_roi=args.min_paper_roi,
                min_paper_edge=args.min_paper_edge,
                min_paper_quantity=args.min_paper_quantity,
            )
            row = _paper_report_row(result)
            if args.out:
                Path(args.out).parent.mkdir(parents=True, exist_ok=True)
                Path(args.out).write_text(json.dumps(row, indent=2, sort_keys=True) + "\n")
                print(f"wrote=1 out={args.out}")
            else:
                print(json.dumps(row, sort_keys=True))
            return 0
        if args.command in {"paper-analyze", "monitor-analyze"}:
            row = analyze_paper_monitor_report(
                Path(args.path),
                top_n=args.top,
                snapshots_path=Path(args.snapshots) if args.snapshots else None,
                rules_path=Path(args.rules) if args.rules else None,
                gamma_path=Path(args.gamma) if args.gamma else None,
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
        if args.command == "optimization-target-markets":
            report = json.loads(Path(args.analysis).read_text())
            market_ids = optimization_target_market_ids(
                report,
                lever=args.lever,
                top_targets=args.top_targets,
                max_markets=args.max_markets,
            )
            if args.out:
                Path(args.out).parent.mkdir(parents=True, exist_ok=True)
                Path(args.out).write_text("\n".join(market_ids) + ("\n" if market_ids else ""))
                print(f"market_ids={len(market_ids)} lever={args.lever} out={args.out}")
            else:
                print(json.dumps({"market_ids": market_ids, "market_id_count": len(market_ids)}, sort_keys=True))
            return 0
        if args.command == "maker-scan":
            row = maker_scan_report(
                Path(args.snapshots),
                rules_path=Path(args.rules) if args.rules else None,
                gamma_path=Path(args.gamma) if args.gamma else None,
                tick_size=args.tick_size,
                min_edge=args.min_edge,
                min_roi=args.min_roi,
                max_capital=args.max_capital,
                max_leg_count=args.max_leg_count,
                top_n=args.top,
                include_yes_no_pairs=args.include_yes_no_pairs,
                quote_mode=args.quote_mode,
                quote_offset_ticks=args.quote_offset_ticks,
            )
            if args.out:
                Path(args.out).parent.mkdir(parents=True, exist_ok=True)
                Path(args.out).write_text(json.dumps(row, indent=2, sort_keys=True) + "\n")
                print(f"candidates={row['candidate_count']} out={args.out}")
            else:
                print(json.dumps(row, sort_keys=True))
            return 0
        if args.command == "maker-fill-sim":
            row = maker_fill_sim_report(
                Path(args.snapshots),
                rules_path=Path(args.rules) if args.rules else None,
                gamma_path=Path(args.gamma) if args.gamma else None,
                tick_size=args.tick_size,
                min_edge=args.min_edge,
                min_roi=args.min_roi,
                max_capital=args.max_capital,
                max_leg_count=args.max_leg_count,
                quote_mode=args.quote_mode,
                quote_offset_ticks=args.quote_offset_ticks,
                horizon_seconds=args.horizon_seconds,
                max_candidates_per_batch=args.max_candidates_per_batch,
                top_n=args.top,
                include_yes_no_pairs=args.include_yes_no_pairs,
            )
            if args.out:
                Path(args.out).parent.mkdir(parents=True, exist_ok=True)
                Path(args.out).write_text(json.dumps(row, indent=2, sort_keys=True) + "\n")
                print(
                    f"observations={row['candidate_observation_count']} completed={row['completed_count']} "
                    f"partial={row['partial_count']} out={args.out}"
                )
            else:
                print(json.dumps(row, sort_keys=True))
            return 0
        if args.command == "maker-adaptive-sim":
            row = maker_adaptive_quote_report(
                Path(args.snapshots),
                rules_path=Path(args.rules) if args.rules else None,
                gamma_path=Path(args.gamma) if args.gamma else None,
                tick_size=args.tick_size,
                min_edge=args.min_edge,
                min_roi=args.min_roi,
                max_capital=args.max_capital,
                max_leg_count=args.max_leg_count,
                quote_offset_ticks_options=_parse_int_csv(args.quote_offset_ticks),
                include_improve_bid=not args.no_improve_bid,
                horizon_seconds=args.horizon_seconds,
                max_candidates_per_batch=args.max_candidates_per_batch,
                top_n=args.top,
                include_yes_no_pairs=args.include_yes_no_pairs,
                partial_loss_rate=args.partial_loss_rate,
                min_observations=args.min_observations,
            )
            if args.out:
                Path(args.out).parent.mkdir(parents=True, exist_ok=True)
                Path(args.out).write_text(json.dumps(row, indent=2, sort_keys=True) + "\n")
                recommendation = row.get("recommended_config") or {}
                print(
                    f"status={row['status']} configs={len(row['ranked_configs'])} "
                    f"recommended={recommendation.get('quote_mode')}:{recommendation.get('quote_offset_ticks')} "
                    f"out={args.out}"
                )
            else:
                print(json.dumps(row, sort_keys=True))
            return 0
        if args.command == "maker-hedge-scan":
            row = maker_hedge_scan_report(
                Path(args.snapshots),
                rules_path=Path(args.rules) if args.rules else None,
                gamma_path=Path(args.gamma) if args.gamma else None,
                tick_size=args.tick_size,
                min_edge=args.min_edge,
                min_roi=args.min_roi,
                max_capital=args.max_capital,
                max_leg_count=args.max_leg_count,
                top_n=args.top,
                include_yes_no_pairs=args.include_yes_no_pairs,
                quote_mode=args.quote_mode,
                quote_offset_ticks=args.quote_offset_ticks,
            )
            if args.out:
                Path(args.out).parent.mkdir(parents=True, exist_ok=True)
                Path(args.out).write_text(json.dumps(row, indent=2, sort_keys=True) + "\n")
                print(f"candidates={row['candidate_count']} out={args.out}")
            else:
                print(json.dumps(row, sort_keys=True))
            return 0
        if args.command == "maker-hedge-sim":
            row = maker_hedge_sim_report(
                Path(args.snapshots),
                rules_path=Path(args.rules) if args.rules else None,
                gamma_path=Path(args.gamma) if args.gamma else None,
                tick_size=args.tick_size,
                min_edge=args.min_edge,
                min_roi=args.min_roi,
                max_capital=args.max_capital,
                max_leg_count=args.max_leg_count,
                quote_mode=args.quote_mode,
                quote_offset_ticks=args.quote_offset_ticks,
                horizon_seconds=args.horizon_seconds,
                max_candidates_per_batch=args.max_candidates_per_batch,
                top_n=args.top,
                include_yes_no_pairs=args.include_yes_no_pairs,
            )
            if args.out:
                Path(args.out).parent.mkdir(parents=True, exist_ok=True)
                Path(args.out).write_text(json.dumps(row, indent=2, sort_keys=True) + "\n")
                print(
                    f"observations={row['candidate_observation_count']} completed={row['completed_count']} "
                    f"unsafe={row['unsafe_fill_count']} out={args.out}"
                )
            else:
                print(json.dumps(row, sort_keys=True))
            return 0
        if args.command == "maker-hybrid-scan":
            row = maker_hybrid_scan_report(
                Path(args.snapshots),
                rules_path=Path(args.rules) if args.rules else None,
                gamma_path=Path(args.gamma) if args.gamma else None,
                tick_size=args.tick_size,
                min_edge=args.min_edge,
                min_roi=args.min_roi,
                max_capital=args.max_capital,
                max_leg_count=args.max_leg_count,
                min_maker_legs=args.min_maker_legs,
                max_maker_legs=args.max_maker_legs,
                maker_selection_pool_size=args.maker_selection_pool_size,
                max_maker_combinations=args.max_maker_combinations,
                top_n=args.top,
                include_yes_no_pairs=args.include_yes_no_pairs,
                quote_mode=args.quote_mode,
                quote_offset_ticks=args.quote_offset_ticks,
            )
            if args.out:
                Path(args.out).parent.mkdir(parents=True, exist_ok=True)
                Path(args.out).write_text(json.dumps(row, indent=2, sort_keys=True) + "\n")
                print(f"candidates={row['candidate_count']} out={args.out}")
            else:
                print(json.dumps(row, sort_keys=True))
            return 0
        if args.command == "maker-hybrid-sim":
            row = maker_hybrid_sim_report(
                Path(args.snapshots),
                rules_path=Path(args.rules) if args.rules else None,
                gamma_path=Path(args.gamma) if args.gamma else None,
                tick_size=args.tick_size,
                min_edge=args.min_edge,
                min_roi=args.min_roi,
                max_capital=args.max_capital,
                max_leg_count=args.max_leg_count,
                min_maker_legs=args.min_maker_legs,
                max_maker_legs=args.max_maker_legs,
                maker_selection_pool_size=args.maker_selection_pool_size,
                max_maker_combinations=args.max_maker_combinations,
                quote_mode=args.quote_mode,
                fill_model=args.fill_model,
                quote_offset_ticks=args.quote_offset_ticks,
                horizon_seconds=args.horizon_seconds,
                max_candidates_per_batch=args.max_candidates_per_batch,
                top_n=args.top,
                include_yes_no_pairs=args.include_yes_no_pairs,
            )
            if args.out:
                Path(args.out).parent.mkdir(parents=True, exist_ok=True)
                Path(args.out).write_text(json.dumps(row, indent=2, sort_keys=True) + "\n")
                print(
                    f"observations={row['candidate_observation_count']} completed={row['completed_count']} "
                    f"partial={row['partial_maker_fill_count']} unsafe={row['unsafe_fill_count']} out={args.out}"
                )
            else:
                print(json.dumps(row, sort_keys=True))
            return 0
        if args.command == "maker-hybrid-tape-sim":
            row = maker_hybrid_tape_sim_report(
                Path(args.snapshots),
                Path(args.trades),
                rules_path=Path(args.rules) if args.rules else None,
                gamma_path=Path(args.gamma) if args.gamma else None,
                tick_size=args.tick_size,
                min_edge=args.min_edge,
                min_roi=args.min_roi,
                max_capital=args.max_capital,
                max_leg_count=args.max_leg_count,
                min_maker_legs=args.min_maker_legs,
                max_maker_legs=args.max_maker_legs,
                maker_selection_pool_size=args.maker_selection_pool_size,
                max_maker_combinations=args.max_maker_combinations,
                quote_mode=args.quote_mode,
                quote_offset_ticks=args.quote_offset_ticks,
                horizon_seconds=args.horizon_seconds,
                max_candidates_per_batch=args.max_candidates_per_batch,
                top_n=args.top,
                include_yes_no_pairs=args.include_yes_no_pairs,
            )
            if args.out:
                Path(args.out).parent.mkdir(parents=True, exist_ok=True)
                Path(args.out).write_text(json.dumps(row, indent=2, sort_keys=True) + "\n")
                print(
                    f"trades={row['trade_count']} observations={row['candidate_observation_count']} "
                    f"completed={row['completed_count']} out={args.out}"
                )
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
                gamma_path=Path(args.gamma) if args.gamma else None,
                min_paper_roi=args.min_paper_roi,
                min_paper_edge=args.min_paper_edge,
                min_paper_quantity=args.min_paper_quantity,
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
                expand_neg_risk_groups=not args.no_expand_neg_risk_groups,
                max_markets=args.max_markets,
            )
            result = replay_ndjson(
                Path(args.snapshots_out),
                min_net_edge=args.min_net_edge,
                max_capital_per_trade=args.max_capital_per_trade,
                bankroll=args.bankroll,
                rules_path=Path(args.rules),
                gamma_path=Path(args.gamma),
                min_paper_roi=args.min_paper_roi,
                min_paper_edge=args.min_paper_edge,
                min_paper_quantity=args.min_paper_quantity,
            )
            rows = _execution_plan_rows(result, args)
            _write_jsonl_or_stdout(rows, args.out)
            if args.out:
                print(f"snapshots={count} plans={len(rows)} out={args.out}")
            return 0
        if args.command == "execute-alerts":
            market_ids = latest_alert_market_ids(Path(args.alerts), max_alerts=args.max_alerts)
            if not market_ids:
                _write_jsonl_or_stdout([], args.out)
                if args.out:
                    print(f"alerts=0 snapshots=0 plans=0 out={args.out}")
                return 0
            collection_errors = []
            count = collect_polymarket_binary_snapshots_for_market_ids(
                Path(args.snapshots_out),
                Path(args.gamma),
                market_ids,
                args.timeout,
                args.proxy,
                args.book_workers,
                skip_book_errors=args.skip_book_errors,
                errors=collection_errors,
                expand_neg_risk_groups=not args.no_expand_neg_risk_groups,
                refresh_missing_gamma=args.refresh_missing_gamma,
            )
            result = replay_ndjson(
                Path(args.snapshots_out),
                min_net_edge=args.min_net_edge,
                max_capital_per_trade=args.max_capital_per_trade,
                bankroll=args.bankroll,
                rules_path=Path(args.rules),
                gamma_path=Path(args.gamma),
                min_paper_roi=args.min_paper_roi,
                min_paper_edge=args.min_paper_edge,
                min_paper_quantity=args.min_paper_quantity,
            )
            rows = _execution_plan_rows(result, args)
            for row in rows:
                row["source_alerts_path"] = args.alerts
                row["source_alert_market_ids"] = market_ids
                row["refreshed_snapshot_count"] = count
                if collection_errors:
                    row["collection_errors"] = collection_errors
            _write_jsonl_or_stdout(rows, args.out)
            if args.out:
                print(f"alerts={len(market_ids)} snapshots={count} plans={len(rows)} out={args.out}")
            return 0
        if args.command == "risk-check-plans":
            rows = []
            for row in _read_jsonl_rows(Path(args.path)):
                if row.get("type") != "execution_plan":
                    continue
                row["risk_check"] = risk_check_execution_plan(
                    row,
                    state_path=Path(args.risk_state) if args.risk_state else None,
                    kill_switch_path=Path(args.kill_switch) if args.kill_switch else None,
                    max_trade_notional=args.max_trade_notional,
                    max_daily_loss=args.max_daily_loss,
                    max_daily_orders=args.max_daily_orders,
                    max_order_count=args.max_order_count,
                    live=not row.get("dry_run", True),
                )
                if args.require_risk_pass and not row["risk_check"]["passed"]:
                    continue
                rows.append(row)
            _write_jsonl_or_stdout(rows, args.out)
            if args.out:
                print(f"wrote={len(rows)} out={args.out}")
            return 0
        if args.command == "success-status":
            row = success_status_report(
                monitor_report_path=Path(args.monitor_report) if args.monitor_report else None,
                execution_plans_path=Path(args.execution_plans) if args.execution_plans else None,
                maker_adaptive_path=Path(args.maker_adaptive) if args.maker_adaptive else None,
                maker_hedge_path=Path(args.maker_hedge) if args.maker_hedge else None,
                maker_hybrid_path=Path(args.maker_hybrid) if args.maker_hybrid else None,
                maker_hybrid_tape_path=Path(args.maker_hybrid_tape) if args.maker_hybrid_tape else None,
                cross_platform_scan_path=Path(args.cross_platform_scan) if args.cross_platform_scan else None,
                min_maker_hybrid_tape_edge_at_cap=args.min_maker_hybrid_tape_edge_at_cap,
                min_cross_platform_capital_edge=args.min_cross_platform_capital_edge,
            )
            if args.out:
                write_success_status(
                    Path(args.out),
                    row,
                    success_log_path=Path(args.success_log) if args.success_log else None,
                )
                print(f"status={row['status']} out={args.out}")
            else:
                print(json.dumps(row, sort_keys=True))
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
                    api_mode=args.api_mode,
                )
            fallback_client = None
            if args.fallback_model:
                fallback_client = OpenAIRuleDiscoveryClient(
                    model=args.fallback_model,
                    timeout=args.timeout,
                    base_url=args.base_url,
                    retries=args.retries,
                    max_output_tokens=args.max_output_tokens,
                    reasoning_effort=args.reasoning_effort,
                    verbosity=args.verbosity,
                    api_mode=args.api_mode,
                )
            semantic_model = args.semantic_model or os.environ.get("OPENAI_SEMANTIC_MODEL")
            semantic_client = None
            if semantic_model and args.semantic_retry_empty_batches:
                semantic_client = OpenAIRuleDiscoveryClient(
                    model=semantic_model,
                    api_key=os.environ.get("OPENAI_SEMANTIC_API_KEY") or os.environ.get("OPENAI_API_KEY"),
                    timeout=_optional_float(args.semantic_timeout, os.environ.get("OPENAI_SEMANTIC_TIMEOUT"), args.timeout),
                    base_url=args.semantic_base_url or os.environ.get("OPENAI_SEMANTIC_BASE_URL"),
                    retries=args.retries,
                    max_output_tokens=args.max_output_tokens,
                    reasoning_effort=args.reasoning_effort,
                    verbosity=args.verbosity,
                    api_mode=args.semantic_api_mode or os.environ.get("OPENAI_SEMANTIC_API_MODE"),
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
                continue_on_client_error=args.continue_on_client_error,
                client_workers=args.client_workers,
                retry_failed_batches=args.retry_failed_batches,
                retry_failed_batch_size=args.retry_failed_batch_size,
                fallback_client=fallback_client,
                fallback_retry_failed_batches=args.fallback_retry_failed_batches,
                fallback_retry_failed_batch_size=args.fallback_retry_failed_batch_size,
                semantic_client=semantic_client,
                semantic_retry_empty_batches=args.semantic_retry_empty_batches,
                semantic_min_liquidity=args.semantic_min_liquidity,
                semantic_min_volume_24h=args.semantic_min_volume_24h,
                topic_cluster=args.topic_cluster,
                max_new_markets=args.max_new_markets,
            )
            print(
                f"markets={result.markets_read} candidates={result.candidates_found} "
                f"implications={result.implications_written} "
                f"mutual_exclusions={result.mutual_exclusions_written} "
                f"equivalents={result.equivalents_written} "
                f"collectively_exhaustive={result.collectively_exhaustive_written} "
                f"complements={result.complements_written} "
                f"failed_batches={getattr(result, 'failed_batches', 0)} out={args.out}"
            )
            return 0
        if args.command == "verify-exhaustive-groups":
            if args.skip_when_no_candidates and promotion_candidate_count(
                Path(args.snapshots),
                Path(args.rules_in),
                min_net_edge=args.min_net_edge,
                top_n=args.top,
                gamma_path=Path(args.gamma),
            ) == 0:
                row = {
                    "type": "exhaustive_group_promotion",
                    "candidates_found": 0,
                    "verified_count": 0,
                    "added_count": 0,
                    "rejected_count": 0,
                    "skipped_existing_count": 0,
                    "out_path": args.rules_out,
                    "rows": [],
                    "status": "skipped_no_candidates",
                }
                if args.report_out:
                    Path(args.report_out).parent.mkdir(parents=True, exist_ok=True)
                    Path(args.report_out).write_text(json.dumps(row, indent=2, sort_keys=True) + "\n")
                if Path(args.rules_in).exists() and args.rules_out != args.rules_in:
                    Path(args.rules_out).parent.mkdir(parents=True, exist_ok=True)
                    Path(args.rules_out).write_text(Path(args.rules_in).read_text())
                print(f"candidates=0 verified=0 added=0 rejected=0 skipped_existing=0 out={args.rules_out}")
                return 0
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
                api_mode=args.api_mode,
            )
            semantic_model = args.semantic_model or os.environ.get("OPENAI_SEMANTIC_MODEL")
            semantic_client = None
            if semantic_model:
                semantic_client = OpenAIExhaustiveGroupVerifierClient(
                    model=semantic_model,
                    api_key=os.environ.get("OPENAI_SEMANTIC_API_KEY") or os.environ.get("OPENAI_API_KEY"),
                    timeout=_optional_float(args.semantic_timeout, os.environ.get("OPENAI_SEMANTIC_TIMEOUT"), args.timeout),
                    base_url=args.semantic_base_url or os.environ.get("OPENAI_SEMANTIC_BASE_URL"),
                    retries=args.retries,
                    max_output_tokens=args.max_output_tokens,
                    reasoning_effort=args.reasoning_effort,
                    verbosity=args.verbosity,
                    api_mode=args.semantic_api_mode or os.environ.get("OPENAI_SEMANTIC_API_MODE"),
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
                state_path=Path(args.state) if args.state else None,
                recheck_hours=args.recheck_hours,
                semantic_client=semantic_client,
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
        if args.command == "ingest-external-signals":
            headers = _headers_from_args(args.header)
            count = ingest_external_signals(
                Path(args.out),
                args.source,
                input_path=Path(args.input) if args.input else None,
                url=args.url,
                timeout=args.timeout,
                proxy=args.proxy,
                headers=headers,
                oddpool_quota_state_path=Path(args.oddpool_quota_state) if args.oddpool_quota_state else None,
                oddpool_monthly_quota=args.oddpool_monthly_quota,
                oddpool_min_interval_seconds=args.oddpool_min_interval_seconds,
            )
            print(f"wrote={count} out={args.out}")
            return 0
        if args.command == "external-signal-report":
            row = external_signal_report(Path(args.path))
            if args.out:
                Path(args.out).parent.mkdir(parents=True, exist_ok=True)
                Path(args.out).write_text(json.dumps(row, indent=2, sort_keys=True) + "\n")
                print(f"wrote=1 out={args.out}")
            else:
                print(json.dumps(row, sort_keys=True))
            return 0
        if args.command == "collect-external-signal-markets":
            errors = []
            market_ids = polymarket_market_ids_from_external_signals(Path(args.external_signals), limit=args.limit)
            known_aliases = {}
            if Path(args.out).exists():
                known_aliases = market_id_alias_map(raw_gamma_markets_from_ndjson(Path(args.out)))
            missing_market_ids = [market_id for market_id in market_ids if market_id not in known_aliases]
            count = collect_polymarket_gamma_markets_by_id(
                Path(args.out),
                missing_market_ids,
                args.timeout,
                args.proxy,
                skip_errors=args.skip_errors,
                errors=errors,
                max_workers=args.max_workers,
            )
            row = {
                "type": "external_signal_market_collection",
                "external_signals": args.external_signals,
                "out": args.out,
                "market_id_count": len(market_ids),
                "known_market_id_count": len(market_ids) - len(missing_market_ids),
                "missing_market_id_count": len(missing_market_ids),
                "written_count": count,
                "error_count": len(errors),
                "errors": errors[: args.max_errors],
            }
            if args.report_out:
                Path(args.report_out).parent.mkdir(parents=True, exist_ok=True)
                Path(args.report_out).write_text(json.dumps(row, indent=2, sort_keys=True) + "\n")
            print(
                f"market_ids={len(market_ids)} missing={len(missing_market_ids)} "
                f"wrote={count} errors={len(errors)} out={args.out}"
            )
            return 0
        if args.command == "match-cross-platform":
            row = match_polymarket_kalshi_markets(
                Path(args.polymarket_gamma),
                Path(args.kalshi_markets),
                min_score=args.min_score,
                top_n=args.top,
            )
            if args.signals_out:
                count = write_cross_platform_signal_rows(
                    cross_platform_signal_rows(row, verified_only=args.verified_only),
                    Path(args.signals_out),
                )
                row["signals_written"] = count
                row["signals_out"] = args.signals_out
            if args.out:
                Path(args.out).parent.mkdir(parents=True, exist_ok=True)
                Path(args.out).write_text(json.dumps(row, indent=2, sort_keys=True) + "\n")
                print(f"wrote=1 out={args.out}")
            else:
                print(json.dumps(row, sort_keys=True))
            return 0
        if args.command == "expand-cross-platform-candidates":
            row = expand_cross_platform_event_candidates(
                json.loads(Path(args.candidates).read_text()),
                Path(args.kalshi_markets),
                polymarket_gamma_path=Path(args.polymarket_gamma) if args.polymarket_gamma else None,
                top_n=args.top,
                min_score=args.min_score,
            )
            if args.signals_out:
                count = write_cross_platform_signal_rows(
                    cross_platform_signal_rows(row, verified_only=args.verified_only),
                    Path(args.signals_out),
                )
                row["signals_written"] = count
                row["signals_out"] = args.signals_out
            if args.out:
                Path(args.out).parent.mkdir(parents=True, exist_ok=True)
                Path(args.out).write_text(json.dumps(row, indent=2, sort_keys=True) + "\n")
                print(f"matches={row['match_count']} out={args.out}")
            else:
                print(json.dumps(row, sort_keys=True))
            return 0
        if args.command == "verify-cross-platform-matches":
            clients = _cross_platform_verifier_clients(args)
            if not clients:
                print("error: model is required via --model or OPENAI_MODEL", file=sys.stderr)
                return 1
            match_report = normalize_cross_platform_match_report(json.loads(Path(args.matches).read_text()), top_n=args.top)
            matches = list(match_report.get("top", []))[: args.top]
            verifications = []
            verification_errors = []
            provider_attempts = []
            batch_jobs = list(enumerate(_chunks(matches, args.batch_size), start=1))
            if args.client_workers <= 1 or len(batch_jobs) <= 1:
                batch_results = [_verify_cross_platform_batch(batch_index, batch, clients) for batch_index, batch in batch_jobs]
            else:
                with ThreadPoolExecutor(max_workers=min(args.client_workers, len(batch_jobs))) as executor:
                    futures = {
                        executor.submit(_verify_cross_platform_batch, batch_index, batch, clients): batch_index
                        for batch_index, batch in batch_jobs
                    }
                    batch_results = [future.result() for future in as_completed(futures)]
                batch_results.sort(key=lambda item: item["batch_index"])
            for batch_result in batch_results:
                verifications.extend(batch_result["verifications"])
                verification_errors.extend(batch_result["errors"])
                provider_attempts.extend(batch_result["provider_attempts"])
                if batch_result["failed"] and not args.continue_on_error:
                    raise OpenAIResponseError("all configured cross-platform verifier providers failed")
            row = apply_cross_platform_verifications(match_report, verifications)
            row["llm_verification_row_count"] = len(verifications)
            row["llm_provider_attempts"] = provider_attempts
            if verification_errors:
                row["verification_errors"] = verification_errors
            if args.signals_out:
                count = write_cross_platform_signal_rows(
                    cross_platform_signal_rows(row, verified_only=args.verified_only),
                    Path(args.signals_out),
                )
                row["signals_written"] = count
                row["signals_out"] = args.signals_out
            if args.out:
                Path(args.out).parent.mkdir(parents=True, exist_ok=True)
                Path(args.out).write_text(json.dumps(row, indent=2, sort_keys=True) + "\n")
                print(
                    f"verified={row.get('llm_verified_count', 0)} rejected={row.get('llm_rejected_count', 0)} "
                    f"parsed={row.get('llm_verification_row_count', 0)} out={args.out}"
                )
            else:
                print(json.dumps(row, sort_keys=True))
            return 0
        if args.command == "scan-cross-platform-once":
            row = _scan_cross_platform_once(args)
            if args.out:
                Path(args.out).parent.mkdir(parents=True, exist_ok=True)
                Path(args.out).write_text(json.dumps(row, indent=2, sort_keys=True) + "\n")
                print(
                    f"pairs={row['pair_count']} snapshots={row['snapshot_count']} "
                    f"opportunities={row['opportunity_count']} out={args.out}"
                )
            else:
                print(json.dumps(row, sort_keys=True))
            return 0
        if args.command == "filter-cross-platform-opportunities":
            scan_report = json.loads(Path(args.scan).read_text())
            scan_report["path"] = args.scan
            row = opportunity_match_report_from_scan(
                scan_report,
                json.loads(Path(args.matches).read_text()),
                top_n=args.top,
                min_net_edge=args.min_net_edge,
                require_option_match=not args.no_option_match,
            )
            if args.out:
                Path(args.out).parent.mkdir(parents=True, exist_ok=True)
                Path(args.out).write_text(json.dumps(row, indent=2, sort_keys=True) + "\n")
                print(f"matches={row['match_count']} out={args.out}")
            else:
                print(json.dumps(row, sort_keys=True))
            return 0
        if args.command == "build-watchlist":
            rows = build_polymarket_watchlist(
                Path(args.gamma),
                Path(args.rules),
                expand_neg_risk_groups=not args.no_expand_neg_risk_groups,
                include_top_markets=args.include_top_markets,
                include_top_neg_risk_groups=args.include_top_neg_risk_groups,
                min_liquidity=args.min_liquidity,
                min_volume_24h=args.min_volume_24h,
                max_markets=args.max_markets,
                external_signals_path=Path(args.external_signals) if args.external_signals else None,
            )
            count = write_watchlist(rows, Path(args.out))
            print(f"wrote={count} out={args.out}")
            return 0
        if args.command == "stream-polymarket-watchlist":
            count = stream_polymarket_watchlist(
                Path(args.watchlist),
                Path(args.out),
                snapshot_out_path=Path(args.snapshots_out) if args.snapshots_out else None,
                max_messages=args.max_messages,
                snapshot_interval_seconds=args.snapshot_interval,
                ws_max_size=args.ws_max_size,
                url=args.url,
            )
            print(f"messages={count} out={args.out}")
            return 0
        if args.command == "realtime-monitor-watchlist":
            summary = monitor_polymarket_watchlist(
                Path(args.watchlist),
                Path(args.report_out),
                rules_path=Path(args.rules),
                gamma_path=Path(args.gamma),
                updates_out_path=Path(args.updates_out) if args.updates_out else None,
                snapshots_out_path=Path(args.snapshots_out) if args.snapshots_out else None,
                latest_snapshots_out_path=Path(args.latest_snapshots_out) if args.latest_snapshots_out else None,
                max_messages=args.max_messages,
                max_iterations=args.max_iterations,
                snapshot_interval_seconds=args.snapshot_interval,
                stale_timeout_seconds=args.stale_timeout,
                reconnect_delay_seconds=args.reconnect_delay,
                max_reconnects=args.max_reconnects,
                min_net_edge=args.min_net_edge,
                max_capital_per_trade=args.max_capital_per_trade,
                bankroll=args.bankroll,
                min_paper_roi=args.min_paper_roi,
                min_paper_edge=args.min_paper_edge,
                min_paper_quantity=args.min_paper_quantity,
                min_run_observations=args.min_run_observations,
                min_run_seconds=args.min_run_seconds,
                max_opportunities_per_iteration=args.max_opportunities_per_iteration,
                ws_max_size=args.ws_max_size,
                url=args.url,
                seed_orderbooks=args.seed_orderbooks,
                seed_timeout=args.seed_timeout,
                seed_proxy=args.seed_proxy,
                seed_max_workers=args.seed_workers,
                progress=_print_realtime_monitor_progress,
            )
            print(
                f"messages={summary['messages_seen']} iterations={summary['iterations_completed']} "
                f"snapshots={summary['snapshots_collected']} opportunities={summary['opportunity_count']} "
                f"paper_edge={summary['paper_edge']:.6f} report={args.report_out}"
            )
            return 0
        if args.command == "monitor-alerts":
            rows = latest_monitor_alerts(
                Path(args.path),
                min_paper_roi=args.min_paper_roi,
                min_paper_edge=args.min_paper_edge,
                include_current=args.include_current,
                max_alerts=args.max_alerts,
            )
            if args.out:
                count = write_alerts(
                    rows,
                    Path(args.out),
                    state_path=Path(args.state) if args.state else None,
                    cooldown_seconds=args.cooldown_seconds,
                )
                print(f"wrote={count} out={args.out}")
            else:
                for row in rows:
                    print(json.dumps(row, sort_keys=True))
            return 0
        if args.command == "notify-alerts":
            rows = notify_alerts(
                Path(args.path),
                max_alerts=args.max_alerts,
                webhook_url=args.webhook_url or os.environ.get("ALERT_WEBHOOK_URL"),
                telegram_bot_token=args.telegram_bot_token or os.environ.get("TELEGRAM_BOT_TOKEN"),
                telegram_chat_id=args.telegram_chat_id or os.environ.get("TELEGRAM_CHAT_ID"),
                discord_webhook_url=args.discord_webhook_url or os.environ.get("DISCORD_WEBHOOK_URL"),
                desktop=args.desktop,
                dry_run=args.dry_run,
                timeout=args.timeout,
                proxy=args.proxy,
            )
            _write_jsonl_or_stdout(rows, args.out)
            if args.out:
                print(f"wrote={len(rows)} out={args.out}")
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
    _add_paper_filter_args(backtest)
    backtest.add_argument("--rules", help="JSON file with implication rules")
    backtest.add_argument("--gamma", help="raw Polymarket Gamma NDJSON path for neg-risk group paper scans")

    collect = subparsers.add_parser("collect-polymarket", help="collect Polymarket public data")
    collect.add_argument("--out", required=True, help="output NDJSON path")
    collect.add_argument("--limit", type=int, default=100, help="Gamma market count per page when no token IDs are provided")
    collect.add_argument("--pages", type=int, default=1, help="Gamma pages to collect when no token or market IDs are provided")
    collect.add_argument("--offset", type=int, default=0, help="starting Gamma offset when collecting pages")
    collect.add_argument("--timeout", type=float, default=10.0, help="HTTP timeout in seconds")
    collect.add_argument("--proxy", help="HTTP proxy, for example 127.0.0.1:10808")
    collect.add_argument("--token-id", action="append", help="CLOB token ID to collect; can be repeated")
    collect.add_argument("--market-id", action="append", help="Gamma market ID to collect; can be repeated")

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
    collect_binaries.add_argument("--gamma", help="raw Polymarket Gamma NDJSON path when collecting specific market IDs")
    collect_binaries.add_argument("--market-id", action="append", help="Gamma market ID; can be repeated")
    collect_binaries.add_argument("--market-ids-file", help="newline-delimited Gamma market IDs")
    collect_binaries.add_argument("--refresh-missing-gamma", action="store_true", help="fetch missing Gamma metadata by market ID")
    collect_binaries.add_argument("--max-markets", type=int, help="cap collected markets after optional neg-risk expansion")
    collect_binaries.add_argument("--skip-book-errors", action="store_true", help="skip CLOB book errors instead of failing")
    collect_binaries.add_argument(
        "--no-expand-neg-risk-groups",
        action="store_true",
        help="do not expand selected markets to their full known negRiskMarketID group",
    )

    collect_trades = subparsers.add_parser(
        "collect-polymarket-trades",
        help="collect Polymarket public trade prints from the Data API for selected Gamma markets",
    )
    collect_trades.add_argument("--out", required=True, help="output raw Polymarket trade NDJSON path")
    collect_trades.add_argument("--gamma", required=True, help="raw Polymarket Gamma NDJSON path")
    collect_trades.add_argument("--market-id", action="append", help="Gamma market ID or condition ID; can be repeated")
    collect_trades.add_argument("--market-ids-file", help="newline-delimited Gamma market IDs")
    collect_trades.add_argument("--hybrid-scan", help="maker-hybrid-scan JSON path; collects markets from top candidates")
    collect_trades.add_argument("--top-markets", type=int, default=10, help="top hybrid candidates to use for market IDs")
    collect_trades.add_argument("--limit", type=int, default=500, help="maximum trade rows per request")
    collect_trades.add_argument("--offset", type=int, default=0, help="Data API pagination offset")
    collect_trades.add_argument("--side", choices=["BUY", "SELL"], help="optional Data API side filter")
    collect_trades.add_argument(
        "--per-market",
        action="store_true",
        help="request each condition ID separately so active markets do not crowd out quieter ones",
    )
    collect_trades.add_argument("--trade-workers", type=int, default=1, help="parallel trade requests when --per-market is set")
    collect_trades.add_argument("--skip-errors", action="store_true", help="skip trade fetch errors instead of failing the run")
    collect_trades.add_argument("--retries", type=int, default=0, help="retry failed trade fetch requests this many times")
    collect_trades.add_argument("--timeout", type=float, default=10.0, help="HTTP timeout in seconds")
    collect_trades.add_argument("--proxy", help="HTTP proxy, for example 127.0.0.1:10808")

    collect_kalshi = subparsers.add_parser("collect-kalshi", help="collect Kalshi market metadata")
    collect_kalshi.add_argument("--out", required=True, help="output raw Kalshi market NDJSON path")
    collect_kalshi.add_argument("--limit", type=int, default=100, help="markets per request")
    collect_kalshi.add_argument("--cursor", help="optional pagination cursor")
    collect_kalshi.add_argument("--status", default="open", help="market status filter; empty string disables")
    collect_kalshi.add_argument("--ticker", action="append", help="optional Kalshi ticker filter")
    collect_kalshi.add_argument("--pages", type=int, default=1, help="number of pages to fetch")
    collect_kalshi.add_argument("--all-pages", action="store_true", help="fetch until the API cursor is exhausted")
    collect_kalshi.add_argument("--timeout", type=float, default=10.0, help="HTTP timeout in seconds")
    collect_kalshi.add_argument("--proxy", help="HTTP proxy, for example 127.0.0.1:10808")

    collect_kalshi_event_markets = subparsers.add_parser(
        "collect-kalshi-event-markets",
        help="collect Kalshi market metadata for event tickers from cross-platform candidates",
    )
    collect_kalshi_event_markets.add_argument("--out", required=True, help="output raw Kalshi market NDJSON path")
    collect_kalshi_event_markets.add_argument("--candidates", help="cross-platform candidate JSON with kalshi_event_ticker values")
    collect_kalshi_event_markets.add_argument("--event-ticker", action="append", help="Kalshi event ticker; can be repeated")
    collect_kalshi_event_markets.add_argument("--limit", type=int, default=1000, help="maximum markets per event")
    collect_kalshi_event_markets.add_argument("--status", default="open", help="market status filter; empty string disables")
    collect_kalshi_event_markets.add_argument("--timeout", type=float, default=10.0, help="HTTP timeout in seconds")
    collect_kalshi_event_markets.add_argument("--proxy", help="HTTP proxy, for example 127.0.0.1:10808")

    collect_kalshi_books = subparsers.add_parser("collect-kalshi-orderbooks", help="collect Kalshi orderbooks by ticker")
    collect_kalshi_books.add_argument("--out", required=True, help="output raw Kalshi orderbook NDJSON path")
    collect_kalshi_books.add_argument("--ticker", action="append", help="Kalshi ticker; can be repeated")
    collect_kalshi_books.add_argument("--tickers-file", help="newline-delimited Kalshi tickers")
    collect_kalshi_books.add_argument("--timeout", type=float, default=10.0, help="HTTP timeout in seconds")
    collect_kalshi_books.add_argument("--proxy", help="HTTP proxy, for example 127.0.0.1:10808")

    kalshi_snapshots = subparsers.add_parser("kalshi-snapshots", help="convert raw Kalshi orderbooks to binary snapshots")
    kalshi_snapshots.add_argument("--orderbooks", required=True, help="raw Kalshi orderbook NDJSON path")
    kalshi_snapshots.add_argument("--out", required=True, help="append Kalshi binary snapshots here")

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
    collect_rule_markets.add_argument("--max-markets", type=int, help="cap collected rule markets for a small run")
    collect_rule_markets.add_argument(
        "--no-expand-neg-risk-groups",
        action="store_true",
        help="do not automatically collect known markets sharing a referenced negRiskMarketID",
    )

    monitor = subparsers.add_parser("monitor-rules", help="collect rule markets repeatedly and replay opportunities")
    monitor.add_argument("--out", required=True, help="output NDJSON path")
    monitor.add_argument("--gamma", required=True, help="raw Polymarket Gamma NDJSON path")
    monitor.add_argument("--rules", required=True, help="rule JSON path")
    monitor.add_argument("--timeout", type=float, default=10.0, help="HTTP timeout in seconds")
    monitor.add_argument("--proxy", help="HTTP proxy, for example 127.0.0.1:10808")
    monitor.add_argument("--iterations", type=int, default=1, help="number of monitor iterations")
    monitor.add_argument("--interval", type=float, default=5.0, help="seconds between iterations")
    monitor.add_argument("--book-workers", type=int, default=1, help="parallel CLOB book fetch workers")
    monitor.add_argument("--max-markets", type=int, help="cap collected rule markets for a small run")
    monitor.add_argument("--min-net-edge", type=float, default=0.0, help="minimum edge per share")
    monitor.add_argument("--max-capital-per-trade", type=float, help="cap simulated capital per opportunity")
    monitor.add_argument("--bankroll", type=float, help="cap simulated bankroll per monitor iteration")
    _add_paper_filter_args(monitor)
    monitor.add_argument("--min-run-observations", type=int, default=1, help="stable opportunity observations to report")
    monitor.add_argument("--min-run-seconds", type=float, default=0.0, help="stable opportunity duration to report")
    monitor.add_argument(
        "--no-expand-neg-risk-groups",
        action="store_true",
        help="do not automatically collect known markets sharing a referenced negRiskMarketID",
    )

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
    paper_monitor.add_argument("--max-markets", type=int, help="cap collected rule markets for a small run")
    paper_monitor.add_argument("--min-net-edge", type=float, default=0.0, help="minimum edge per share")
    paper_monitor.add_argument("--max-capital-per-trade", type=float, help="cap simulated capital per opportunity")
    paper_monitor.add_argument("--bankroll", type=float, help="cap simulated bankroll per monitor iteration")
    _add_paper_filter_args(paper_monitor)
    paper_monitor.add_argument("--min-run-observations", type=int, default=1, help="stable opportunity observations to report")
    paper_monitor.add_argument("--min-run-seconds", type=float, default=0.0, help="stable opportunity duration to report")
    paper_monitor.add_argument("--skip-book-errors", action="store_true", help="skip markets whose CLOB books fail")
    paper_monitor.add_argument("--continue-on-error", action="store_true", help="record iteration errors and keep looping")
    paper_monitor.add_argument(
        "--no-expand-neg-risk-groups",
        action="store_true",
        help="do not automatically collect known markets sharing a referenced negRiskMarketID",
    )
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
    report.add_argument("--gamma", help="raw Polymarket Gamma NDJSON path for neg-risk group paper scans")
    report.add_argument("--out", help="output JSON path; prints JSON to stdout when omitted")
    report.add_argument("--min-net-edge", type=float, default=0.0, help="minimum edge per share")
    report.add_argument("--max-capital-per-trade", type=float, help="cap simulated capital per opportunity")
    report.add_argument("--bankroll", type=float, help="cap simulated bankroll per timestamp batch")
    _add_paper_filter_args(report)

    analyze = subparsers.add_parser("paper-analyze", help="summarize a paper-monitor JSONL report")
    analyze.add_argument("path", help="paper-monitor JSONL report path")
    analyze.add_argument("--out", help="output JSON path; prints JSON to stdout when omitted")
    analyze.add_argument("--top", type=int, default=10, help="top opportunities and markets to include")
    analyze.add_argument("--snapshots", help="optional snapshot NDJSON path for near-miss diagnostics")
    analyze.add_argument("--rules", help="optional rule JSON path for relation near-miss diagnostics")
    analyze.add_argument("--gamma", help="optional raw Gamma NDJSON path for near-miss neg-risk diagnostics")
    analyze.add_argument("--near-miss-top", type=int, default=10, help="near-miss rows to include")
    analyze.add_argument(
        "--near-miss-min-net-edge",
        type=float,
        default=0.0,
        help="minimum net edge threshold used to classify near misses",
    )

    monitor_analyze = subparsers.add_parser(
        "monitor-analyze",
        help="summarize a paper or realtime monitor JSONL report",
    )
    monitor_analyze.add_argument("path", help="monitor JSONL report path")
    monitor_analyze.add_argument("--out", help="output JSON path; prints JSON to stdout when omitted")
    monitor_analyze.add_argument("--top", type=int, default=10, help="top opportunities and markets to include")
    monitor_analyze.add_argument("--snapshots", help="optional snapshot NDJSON path for near-miss diagnostics")
    monitor_analyze.add_argument("--rules", help="optional rule JSON path for relation near-miss diagnostics")
    monitor_analyze.add_argument("--gamma", help="optional raw Gamma NDJSON path for near-miss neg-risk diagnostics")
    monitor_analyze.add_argument("--near-miss-top", type=int, default=10, help="near-miss rows to include")
    monitor_analyze.add_argument(
        "--near-miss-min-net-edge",
        type=float,
        default=0.0,
        help="minimum net edge threshold used to classify near misses",
    )

    optimization_markets = subparsers.add_parser(
        "optimization-target-markets",
        help="extract market IDs from monitor-analysis optimization targets",
    )
    optimization_markets.add_argument("analysis", help="monitor-analysis JSON path")
    optimization_markets.add_argument("--out", help="newline-delimited output path; prints JSON when omitted")
    optimization_markets.add_argument("--lever", default="maker_fee_avoidance", help="target lever, or top/all")
    optimization_markets.add_argument("--top-targets", type=int, default=1, help="number of matching targets to use")
    optimization_markets.add_argument("--max-markets", type=int, help="cap returned market IDs")

    maker_scan = subparsers.add_parser(
        "maker-scan",
        help="scan latest snapshots for passive maker basket candidates without submitting orders",
    )
    maker_scan.add_argument("--snapshots", required=True, help="binary snapshot NDJSON path")
    maker_scan.add_argument("--rules", help="JSON file with discovered rules")
    maker_scan.add_argument("--gamma", help="raw Polymarket Gamma NDJSON path for neg-risk groups")
    maker_scan.add_argument("--out", help="output maker scan JSON path; prints JSON when omitted")
    maker_scan.add_argument("--tick-size", type=float, default=0.001, help="passive quote tick size")
    maker_scan.add_argument(
        "--quote-offset-ticks",
        type=int,
        default=1,
        help="for near_ask, quote this many ticks below best ask",
    )
    maker_scan.add_argument("--min-edge", type=float, default=0.0, help="minimum maker edge per completed bundle")
    maker_scan.add_argument("--min-roi", type=float, help="minimum maker ROI per completed bundle")
    maker_scan.add_argument("--max-capital", type=float, help="capital cap used for suggested quantity and expected edge")
    maker_scan.add_argument("--max-leg-count", type=int, default=30, help="maximum basket leg count")
    maker_scan.add_argument("--top", type=int, default=25, help="top candidates to include")
    maker_scan.add_argument(
        "--quote-mode",
        choices=["near_ask", "improve_bid"],
        default="near_ask",
        help="near_ask quotes one tick below ask; improve_bid quotes one tick above bid",
    )
    maker_scan.add_argument(
        "--include-yes-no-pairs",
        action="store_true",
        help="include single-market paired maker quotes; these are market-making candidates, not arbitrage",
    )

    maker_fill = subparsers.add_parser(
        "maker-fill-sim",
        help="simulate whether passive maker basket candidates would have filled in later snapshots",
    )
    maker_fill.add_argument("--snapshots", required=True, help="historical binary snapshot NDJSON path")
    maker_fill.add_argument("--rules", help="JSON file with discovered rules")
    maker_fill.add_argument("--gamma", help="raw Polymarket Gamma NDJSON path for neg-risk groups")
    maker_fill.add_argument("--out", help="output maker fill simulation JSON path; prints JSON when omitted")
    maker_fill.add_argument("--tick-size", type=float, default=0.001, help="passive quote tick size")
    maker_fill.add_argument("--quote-mode", choices=["near_ask", "improve_bid"], default="near_ask")
    maker_fill.add_argument(
        "--quote-offset-ticks",
        type=int,
        default=1,
        help="for near_ask, quote this many ticks below best ask",
    )
    maker_fill.add_argument("--min-edge", type=float, default=0.0, help="minimum maker edge per completed bundle")
    maker_fill.add_argument("--min-roi", type=float, help="minimum maker ROI per completed bundle")
    maker_fill.add_argument("--max-capital", type=float, help="capital cap used for suggested quantity and expected edge")
    maker_fill.add_argument("--max-leg-count", type=int, default=30, help="maximum basket leg count")
    maker_fill.add_argument("--horizon-seconds", type=float, default=300.0, help="seconds after quote time to look for fills")
    maker_fill.add_argument("--max-candidates-per-batch", type=int, default=25, help="top maker candidates to simulate per timestamp")
    maker_fill.add_argument("--top", type=int, default=25, help="top fill results to include")
    maker_fill.add_argument("--include-yes-no-pairs", action="store_true", help="include single-market paired maker quotes")

    maker_adaptive = subparsers.add_parser(
        "maker-adaptive-sim",
        help="compare passive maker quote offsets by historical fill and conservative EV",
    )
    maker_adaptive.add_argument("--snapshots", required=True, help="historical binary snapshot NDJSON path")
    maker_adaptive.add_argument("--rules", help="JSON file with discovered rules")
    maker_adaptive.add_argument("--gamma", help="raw Polymarket Gamma NDJSON path for neg-risk groups")
    maker_adaptive.add_argument("--out", help="output adaptive maker simulation JSON path; prints JSON when omitted")
    maker_adaptive.add_argument("--tick-size", type=float, default=0.001, help="passive quote tick size")
    maker_adaptive.add_argument(
        "--quote-offset-ticks",
        default="1,2,3,5,10",
        help="comma-separated near_ask quote offsets to compare",
    )
    maker_adaptive.add_argument("--no-improve-bid", action="store_true", help="do not include bid-plus-one-tick quotes")
    maker_adaptive.add_argument("--min-edge", type=float, default=0.0, help="minimum maker edge per completed bundle")
    maker_adaptive.add_argument("--min-roi", type=float, help="minimum maker ROI per completed bundle")
    maker_adaptive.add_argument(
        "--max-capital",
        type=float,
        help="capital cap used for suggested quantity, edge, and partial-fill risk",
    )
    maker_adaptive.add_argument("--max-leg-count", type=int, default=30, help="maximum basket leg count")
    maker_adaptive.add_argument("--horizon-seconds", type=float, default=300.0, help="seconds after quote time to look for fills")
    maker_adaptive.add_argument(
        "--max-candidates-per-batch",
        type=int,
        default=25,
        help="top maker candidates to simulate per timestamp and quote config",
    )
    maker_adaptive.add_argument("--partial-loss-rate", type=float, default=1.0, help="capital haircut for partial maker fills")
    maker_adaptive.add_argument("--min-observations", type=int, default=5, help="minimum observations required to recommend a config")
    maker_adaptive.add_argument("--top", type=int, default=25, help="top quote configs to include")
    maker_adaptive.add_argument("--include-yes-no-pairs", action="store_true", help="include single-market paired maker quotes")

    maker_hedge_scan = subparsers.add_parser(
        "maker-hedge-scan",
        help="scan latest snapshots for one-maker-leg plus immediate-taker-hedge candidates",
    )
    maker_hedge_scan.add_argument("--snapshots", required=True, help="binary snapshot NDJSON path")
    maker_hedge_scan.add_argument("--rules", help="JSON file with discovered rules")
    maker_hedge_scan.add_argument("--gamma", help="raw Polymarket Gamma NDJSON path for neg-risk groups")
    maker_hedge_scan.add_argument("--out", help="output maker hedge scan JSON path; prints JSON when omitted")
    maker_hedge_scan.add_argument("--tick-size", type=float, default=0.001, help="passive quote tick size")
    maker_hedge_scan.add_argument(
        "--quote-offset-ticks",
        type=int,
        default=1,
        help="for near_ask, quote this many ticks below best ask",
    )
    maker_hedge_scan.add_argument("--min-edge", type=float, default=0.0, help="minimum edge after maker fill and taker hedge")
    maker_hedge_scan.add_argument("--min-roi", type=float, help="minimum ROI after maker fill and taker hedge")
    maker_hedge_scan.add_argument("--max-capital", type=float, help="capital cap used for suggested quantity and expected edge")
    maker_hedge_scan.add_argument("--max-leg-count", type=int, default=30, help="maximum basket leg count")
    maker_hedge_scan.add_argument("--top", type=int, default=25, help="top candidates to include")
    maker_hedge_scan.add_argument("--quote-mode", choices=["near_ask", "improve_bid"], default="near_ask")
    maker_hedge_scan.add_argument("--include-yes-no-pairs", action="store_true", help="include single-market paired hedges")

    maker_hedge_sim = subparsers.add_parser(
        "maker-hedge-sim",
        help="simulate one-maker-leg candidates and immediate taker hedge using later snapshots",
    )
    maker_hedge_sim.add_argument("--snapshots", required=True, help="historical binary snapshot NDJSON path")
    maker_hedge_sim.add_argument("--rules", help="JSON file with discovered rules")
    maker_hedge_sim.add_argument("--gamma", help="raw Polymarket Gamma NDJSON path for neg-risk groups")
    maker_hedge_sim.add_argument("--out", help="output maker hedge simulation JSON path; prints JSON when omitted")
    maker_hedge_sim.add_argument("--tick-size", type=float, default=0.001, help="passive quote tick size")
    maker_hedge_sim.add_argument("--quote-mode", choices=["near_ask", "improve_bid"], default="near_ask")
    maker_hedge_sim.add_argument(
        "--quote-offset-ticks",
        type=int,
        default=1,
        help="for near_ask, quote this many ticks below best ask",
    )
    maker_hedge_sim.add_argument("--min-edge", type=float, default=0.0, help="minimum realized edge after hedge")
    maker_hedge_sim.add_argument("--min-roi", type=float, help="minimum expected ROI before simulation")
    maker_hedge_sim.add_argument("--max-capital", type=float, help="capital cap used for suggested quantity and expected edge")
    maker_hedge_sim.add_argument("--max-leg-count", type=int, default=30, help="maximum basket leg count")
    maker_hedge_sim.add_argument("--horizon-seconds", type=float, default=300.0, help="seconds after quote time to look for maker fill")
    maker_hedge_sim.add_argument("--max-candidates-per-batch", type=int, default=25, help="top maker hedge candidates per timestamp")
    maker_hedge_sim.add_argument("--top", type=int, default=25, help="top simulation results to include")
    maker_hedge_sim.add_argument("--include-yes-no-pairs", action="store_true", help="include single-market paired hedges")

    maker_hybrid_scan = subparsers.add_parser(
        "maker-hybrid-scan",
        help="scan latest snapshots for multi-maker-leg candidates followed by immediate taker hedge",
    )
    maker_hybrid_scan.add_argument("--snapshots", required=True, help="binary snapshot NDJSON path")
    maker_hybrid_scan.add_argument("--rules", help="JSON file with discovered rules")
    maker_hybrid_scan.add_argument("--gamma", help="raw Polymarket Gamma NDJSON path for neg-risk groups")
    maker_hybrid_scan.add_argument("--out", help="output maker hybrid scan JSON path; prints JSON when omitted")
    maker_hybrid_scan.add_argument("--tick-size", type=float, default=0.001, help="passive quote tick size")
    maker_hybrid_scan.add_argument("--quote-mode", choices=["near_ask", "improve_bid"], default="near_ask")
    maker_hybrid_scan.add_argument(
        "--quote-offset-ticks",
        type=int,
        default=1,
        help="for near_ask, quote this many ticks below best ask",
    )
    maker_hybrid_scan.add_argument("--min-edge", type=float, default=0.0, help="minimum edge after maker fills and taker hedge")
    maker_hybrid_scan.add_argument("--min-roi", type=float, help="minimum ROI after maker fills and taker hedge")
    maker_hybrid_scan.add_argument("--max-capital", type=float, help="capital cap used for suggested quantity and expected edge")
    maker_hybrid_scan.add_argument("--max-leg-count", type=int, default=80, help="maximum basket leg count")
    maker_hybrid_scan.add_argument("--min-maker-legs", type=int, default=2, help="minimum maker legs that must fill before hedging")
    maker_hybrid_scan.add_argument("--max-maker-legs", type=int, default=3, help="maximum maker legs that must fill before hedging")
    maker_hybrid_scan.add_argument("--maker-selection-pool-size", type=int, default=8, help="top maker-saving legs to search")
    maker_hybrid_scan.add_argument("--max-maker-combinations", type=int, default=25, help="maximum maker leg combinations per basket and k")
    maker_hybrid_scan.add_argument("--top", type=int, default=25, help="top candidates to include")
    maker_hybrid_scan.add_argument("--include-yes-no-pairs", action="store_true", help="include single-market paired hedges")

    maker_hybrid_sim = subparsers.add_parser(
        "maker-hybrid-sim",
        help="simulate multi-maker-leg candidates and immediate taker hedge using later snapshots",
    )
    maker_hybrid_sim.add_argument("--snapshots", required=True, help="historical binary snapshot NDJSON path")
    maker_hybrid_sim.add_argument("--rules", help="JSON file with discovered rules")
    maker_hybrid_sim.add_argument("--gamma", help="raw Polymarket Gamma NDJSON path for neg-risk groups")
    maker_hybrid_sim.add_argument("--out", help="output maker hybrid simulation JSON path; prints JSON when omitted")
    maker_hybrid_sim.add_argument("--tick-size", type=float, default=0.001, help="passive quote tick size")
    maker_hybrid_sim.add_argument("--quote-mode", choices=["near_ask", "improve_bid"], default="near_ask")
    maker_hybrid_sim.add_argument(
        "--fill-model",
        choices=["crossed_ask", "touch_bid"],
        default="crossed_ask",
        help="crossed_ask is conservative; touch_bid is diagnostic only and may overstate maker fills",
    )
    maker_hybrid_sim.add_argument(
        "--quote-offset-ticks",
        type=int,
        default=1,
        help="for near_ask, quote this many ticks below best ask",
    )
    maker_hybrid_sim.add_argument("--min-edge", type=float, default=0.0, help="minimum realized edge after hedge")
    maker_hybrid_sim.add_argument("--min-roi", type=float, help="minimum expected ROI before simulation")
    maker_hybrid_sim.add_argument("--max-capital", type=float, help="capital cap used for suggested quantity and expected edge")
    maker_hybrid_sim.add_argument("--max-leg-count", type=int, default=80, help="maximum basket leg count")
    maker_hybrid_sim.add_argument("--min-maker-legs", type=int, default=2, help="minimum maker legs that must fill before hedging")
    maker_hybrid_sim.add_argument("--max-maker-legs", type=int, default=3, help="maximum maker legs that must fill before hedging")
    maker_hybrid_sim.add_argument("--maker-selection-pool-size", type=int, default=8, help="top maker-saving legs to search")
    maker_hybrid_sim.add_argument("--max-maker-combinations", type=int, default=25, help="maximum maker leg combinations per basket and k")
    maker_hybrid_sim.add_argument("--horizon-seconds", type=float, default=300.0, help="seconds after quote time to look for maker fills")
    maker_hybrid_sim.add_argument("--max-candidates-per-batch", type=int, default=25, help="top maker hybrid candidates per timestamp")
    maker_hybrid_sim.add_argument("--top", type=int, default=25, help="top simulation results to include")
    maker_hybrid_sim.add_argument("--include-yes-no-pairs", action="store_true", help="include single-market paired hedges")

    maker_hybrid_tape = subparsers.add_parser(
        "maker-hybrid-tape-sim",
        help="validate maker-hybrid candidates against public SELL trade prints before taker hedge",
    )
    maker_hybrid_tape.add_argument("--snapshots", required=True, help="historical binary snapshot NDJSON path")
    maker_hybrid_tape.add_argument("--trades", required=True, help="raw Polymarket data trade NDJSON path")
    maker_hybrid_tape.add_argument("--rules", help="JSON file with discovered rules")
    maker_hybrid_tape.add_argument("--gamma", help="raw Polymarket Gamma NDJSON path for neg-risk groups")
    maker_hybrid_tape.add_argument("--out", help="output maker hybrid tape simulation JSON path; prints JSON when omitted")
    maker_hybrid_tape.add_argument("--tick-size", type=float, default=0.001, help="passive quote tick size")
    maker_hybrid_tape.add_argument("--quote-mode", choices=["near_ask", "improve_bid"], default="near_ask")
    maker_hybrid_tape.add_argument(
        "--quote-offset-ticks",
        type=int,
        default=1,
        help="for near_ask, quote this many ticks below best ask",
    )
    maker_hybrid_tape.add_argument("--min-edge", type=float, default=0.0, help="minimum realized edge after hedge")
    maker_hybrid_tape.add_argument("--min-roi", type=float, help="minimum expected ROI before simulation")
    maker_hybrid_tape.add_argument("--max-capital", type=float, help="capital cap used for suggested quantity and expected edge")
    maker_hybrid_tape.add_argument("--max-leg-count", type=int, default=80, help="maximum basket leg count")
    maker_hybrid_tape.add_argument("--min-maker-legs", type=int, default=2, help="minimum maker legs that must fill before hedging")
    maker_hybrid_tape.add_argument("--max-maker-legs", type=int, default=3, help="maximum maker legs that must fill before hedging")
    maker_hybrid_tape.add_argument("--maker-selection-pool-size", type=int, default=8, help="top maker-saving legs to search")
    maker_hybrid_tape.add_argument("--max-maker-combinations", type=int, default=25, help="maximum maker leg combinations per basket and k")
    maker_hybrid_tape.add_argument("--horizon-seconds", type=float, default=300.0, help="seconds after quote time to look for trade prints")
    maker_hybrid_tape.add_argument("--max-candidates-per-batch", type=int, default=25, help="top maker hybrid candidates per timestamp")
    maker_hybrid_tape.add_argument("--top", type=int, default=25, help="top simulation results to include")
    maker_hybrid_tape.add_argument("--include-yes-no-pairs", action="store_true", help="include single-market paired hedges")

    execute = subparsers.add_parser("execute-latest", help="build or submit execution plans for latest opportunities")
    execute.add_argument("path", help="input NDJSON snapshot path")
    execute.add_argument("--rules", help="JSON file with discovered rules")
    execute.add_argument("--gamma", help="raw Polymarket Gamma NDJSON path for neg-risk group paper scans")
    execute.add_argument("--out", help="output NDJSON execution plan path")
    execute.add_argument("--min-net-edge", type=float, default=0.0, help="minimum edge per share")
    execute.add_argument("--max-capital-per-trade", type=float, help="cap capital per opportunity")
    execute.add_argument("--bankroll", type=float, help="cap simulated bankroll for latest timestamp")
    _add_paper_filter_args(execute)
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
    _add_pretrade_check_args(execute)
    _add_risk_args(execute)

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
    execute_once.add_argument("--max-markets", type=int, help="cap collected rule markets for a small run")
    execute_once.add_argument(
        "--no-expand-neg-risk-groups",
        action="store_true",
        help="do not automatically collect known markets sharing a referenced negRiskMarketID",
    )
    execute_once.add_argument("--min-net-edge", type=float, default=0.0, help="minimum edge per share")
    execute_once.add_argument("--max-capital-per-trade", type=float, help="cap capital per opportunity")
    execute_once.add_argument("--bankroll", type=float, help="cap simulated bankroll for latest timestamp")
    _add_paper_filter_args(execute_once)
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
    _add_pretrade_check_args(execute_once)
    _add_risk_args(execute_once)

    execute_alerts = subparsers.add_parser(
        "execute-alerts",
        help="refresh alert market books, then build dry-run execution plans with pretrade checks",
    )
    execute_alerts.add_argument("alerts", help="opportunity_alert NDJSON path")
    execute_alerts.add_argument("--gamma", required=True, help="raw Polymarket Gamma NDJSON path")
    execute_alerts.add_argument("--rules", required=True, help="rule JSON path")
    execute_alerts.add_argument("--snapshots-out", required=True, help="append refreshed alert snapshots here")
    execute_alerts.add_argument("--out", help="output NDJSON execution plan path")
    execute_alerts.add_argument("--max-alerts", type=int, default=20, help="latest alerts to refresh")
    execute_alerts.add_argument("--timeout", type=float, default=10.0, help="HTTP timeout in seconds")
    execute_alerts.add_argument("--proxy", help="HTTP proxy, for example 127.0.0.1:10808")
    execute_alerts.add_argument("--book-workers", type=int, default=1, help="parallel CLOB book fetch workers")
    execute_alerts.add_argument("--skip-book-errors", action="store_true", help="continue when individual books fail")
    execute_alerts.add_argument(
        "--refresh-missing-gamma",
        action="store_true",
        help="fetch missing Gamma market metadata by alert market id before refreshing quotes",
    )
    execute_alerts.add_argument(
        "--no-expand-neg-risk-groups",
        action="store_true",
        help="do not automatically collect known markets sharing a referenced negRiskMarketID",
    )
    execute_alerts.add_argument("--min-net-edge", type=float, default=0.0, help="minimum edge per share")
    execute_alerts.add_argument("--max-capital-per-trade", type=float, help="cap capital per opportunity")
    execute_alerts.add_argument("--bankroll", type=float, help="cap simulated bankroll for latest timestamp")
    _add_paper_filter_args(execute_alerts)
    execute_alerts.add_argument("--min-run-observations", type=int, default=1, help="minimum latest-run observations before planning")
    execute_alerts.add_argument("--min-run-seconds", type=float, default=0.0, help="minimum latest-run duration before planning")
    execute_alerts.add_argument("--max-trades", type=int, default=1, help="maximum plans to build or submit")
    execute_alerts.add_argument("--slippage-bps", type=float, default=50.0, help="buy limit cushion in basis points")
    execute_alerts.add_argument("--tick-size", default="0.01", help="CLOB market tick size")
    execute_alerts.add_argument("--order-type", default="FOK", help="SDK order type, default FOK")
    execute_alerts.add_argument("--neg-risk", action="store_true", help="set neg_risk option for SDK order creation")
    execute_alerts.add_argument("--live", action="store_true", help="submit orders through py-clob-client-v2")
    execute_alerts.add_argument("--allow-live", action="store_true", help="second live-trading confirmation flag")
    execute_alerts.add_argument("--allow-nonatomic-live", action="store_true", help="acknowledge multi-leg live order risk")
    _add_pretrade_check_args(execute_alerts)
    _add_risk_args(execute_alerts)

    risk_check = subparsers.add_parser("risk-check-plans", help="apply risk controls to existing execution_plan NDJSON")
    risk_check.add_argument("path", help="execution_plan NDJSON path")
    risk_check.add_argument("--out", help="output checked execution_plan NDJSON path; prints JSONL when omitted")
    _add_risk_args(risk_check)

    success_status = subparsers.add_parser(
        "success-status",
        help="summarize whether the monitor has found a paper, dry-run, or live success candidate",
    )
    success_status.add_argument("--monitor-report", help="realtime/paper monitor JSONL path")
    success_status.add_argument("--execution-plans", help="latest execution_plan NDJSON path")
    success_status.add_argument("--maker-adaptive", help="maker adaptive quote report JSON path")
    success_status.add_argument("--maker-hedge", help="maker hedge simulation report JSON path")
    success_status.add_argument("--maker-hybrid", help="maker hybrid simulation report JSON path")
    success_status.add_argument("--maker-hybrid-tape", help="maker hybrid public trade tape simulation report JSON path")
    success_status.add_argument("--cross-platform-scan", help="latest cross_platform_scan_report JSON path")
    success_status.add_argument(
        "--min-maker-hybrid-tape-edge-at-cap",
        type=float,
        default=0.0,
        help="minimum capital-capped public tape edge required to treat a maker-hybrid tape candidate as actionable",
    )
    success_status.add_argument(
        "--min-cross-platform-capital-edge",
        type=float,
        default=0.0,
        help="minimum capital-capped edge required to treat a cross-platform scan as actionable",
    )
    success_status.add_argument("--out", help="output status JSON path; prints JSON when omitted")
    success_status.add_argument("--success-log", help="append non-empty success statuses to this NDJSON log")

    discover = subparsers.add_parser("discover-rules", help="discover implication rules with an OpenAI-compatible API")
    discover.add_argument("--raw", required=True, help="input raw Polymarket Gamma NDJSON path")
    discover.add_argument("--out", required=True, help="output JSON rule path")
    discover.add_argument("--model", help="OpenAI model name; defaults to OPENAI_MODEL")
    discover.add_argument("--fallback-model", help="OpenAI model name for retrying remaining failed batches")
    discover.add_argument("--semantic-model", help="high-recall model for empty important batch retries; defaults to OPENAI_SEMANTIC_MODEL")
    discover.add_argument("--base-url", help="OpenAI-compatible base URL; defaults to OPENAI_BASE_URL or OpenAI")
    discover.add_argument("--api-mode", choices=["responses", "chat", "messages"], help="OpenAI-compatible API mode; defaults to OPENAI_API_MODE or responses")
    discover.add_argument("--semantic-base-url", help="semantic model base URL; defaults to OPENAI_SEMANTIC_BASE_URL")
    discover.add_argument("--semantic-api-mode", choices=["responses", "chat", "messages"], help="semantic model API mode; defaults to OPENAI_SEMANTIC_API_MODE")
    discover.add_argument("--semantic-timeout", type=float, help="semantic model HTTP timeout; defaults to OPENAI_SEMANTIC_TIMEOUT or --timeout")
    discover.add_argument("--batch-size", type=int, default=10, help="markets per LLM discovery batch")
    discover.add_argument("--min-confidence", type=float, default=0.95, help="minimum candidate confidence")
    discover.add_argument(
        "--semantic-retry-empty-batches",
        action="store_true",
        help="retry important discovery batches with --semantic-model when the main provider returns no relations",
    )
    discover.add_argument("--semantic-min-liquidity", type=float, default=0.0, help="minimum market liquidity for semantic empty-batch retry")
    discover.add_argument("--semantic-min-volume-24h", type=float, default=0.0, help="minimum 24h volume for semantic empty-batch retry")
    discover.add_argument("--max-markets", type=int, help="limit input markets for a small run")
    discover.add_argument(
        "--max-new-markets",
        type=int,
        help="limit uncached markets sent to the LLM in this run; remaining markets stay pending for later refreshes",
    )
    discover.add_argument("--cache", help="existing rule JSON to reuse for incremental discovery")
    discover.add_argument("--context-market-limit", type=int, default=40, help="old markets to include with each new-market LLM batch")
    discover.add_argument("--timeout", type=float, default=60.0, help="HTTP timeout in seconds")
    discover.add_argument("--retries", type=int, default=2, help="retry count for retryable OpenAI-compatible API errors")
    discover.add_argument("--max-output-tokens", type=int, default=4000, help="maximum model output tokens")
    discover.add_argument("--reasoning-effort", default="medium", help="OpenAI-compatible reasoning effort")
    discover.add_argument("--verbosity", help="optional Responses API text verbosity")
    discover.add_argument("--client-workers", type=int, default=1, help="parallel LLM discovery batch workers")
    discover.add_argument(
        "--retry-failed-batches",
        type=int,
        default=0,
        help="extra in-run retry passes for failed LLM batches when --continue-on-client-error is set",
    )
    discover.add_argument(
        "--retry-failed-batch-size",
        type=int,
        default=1,
        help="batch size for in-run failed-batch retries",
    )
    discover.add_argument(
        "--fallback-retry-failed-batches",
        type=int,
        default=0,
        help="extra retry passes using --fallback-model for remaining failed batches",
    )
    discover.add_argument(
        "--fallback-retry-failed-batch-size",
        type=int,
        default=1,
        help="batch size for fallback model failed-batch retries",
    )
    discover.add_argument(
        "--continue-on-client-error",
        action="store_true",
        help="record failed LLM batches and continue with successful batches",
    )
    discover.add_argument(
        "--topic-cluster",
        action="store_true",
        help="group new markets by topic before LLM batching",
    )

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
    verify_groups.add_argument("--api-mode", choices=["responses", "chat", "messages"], help="OpenAI-compatible API mode; defaults to OPENAI_API_MODE or responses")
    verify_groups.add_argument("--semantic-model", help="high-recall verifier model; defaults to OPENAI_SEMANTIC_MODEL")
    verify_groups.add_argument("--semantic-base-url", help="semantic verifier base URL; defaults to OPENAI_SEMANTIC_BASE_URL")
    verify_groups.add_argument("--semantic-api-mode", choices=["responses", "chat", "messages"], help="semantic verifier API mode; defaults to OPENAI_SEMANTIC_API_MODE")
    verify_groups.add_argument("--semantic-timeout", type=float, help="semantic verifier HTTP timeout; defaults to OPENAI_SEMANTIC_TIMEOUT or --timeout")
    verify_groups.add_argument("--min-net-edge", type=float, default=0.002, help="minimum diagnostic net edge to verify")
    verify_groups.add_argument("--top", type=int, default=10, help="maximum diagnostic groups to verify")
    verify_groups.add_argument("--min-confidence", type=float, default=0.95, help="minimum verification confidence")
    verify_groups.add_argument("--timeout", type=float, default=60.0, help="HTTP timeout in seconds")
    verify_groups.add_argument("--retries", type=int, default=2, help="retry count for retryable OpenAI-compatible API errors")
    verify_groups.add_argument("--max-output-tokens", type=int, default=2000, help="maximum model output tokens")
    verify_groups.add_argument("--reasoning-effort", default="medium", help="OpenAI-compatible reasoning effort")
    verify_groups.add_argument("--verbosity", help="optional Responses API text verbosity")
    verify_groups.add_argument("--state", help="promotion cache JSON path for rejected/added groups")
    verify_groups.add_argument("--recheck-hours", type=float, default=24.0, help="hours before rechecking a rejected group")
    verify_groups.add_argument(
        "--skip-when-no-candidates",
        action="store_true",
        help="avoid requiring model/API key when no near-miss groups meet --min-net-edge",
    )

    ingest_signals = subparsers.add_parser(
        "ingest-external-signals",
        help="normalize external scanner alerts into external_signal NDJSON",
    )
    ingest_signals.add_argument("--source", required=True, help="signal source name, for example oddpool")
    ingest_signals.add_argument("--out", required=True, help="append normalized external signals here")
    input_group = ingest_signals.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--input", help="input JSON or NDJSON path")
    input_group.add_argument("--url", action="append", help="input JSON URL; can be repeated")
    ingest_signals.add_argument("--timeout", type=float, default=10.0, help="HTTP timeout in seconds for URL input")
    ingest_signals.add_argument("--proxy", help="HTTP proxy for URL input, for example 127.0.0.1:10808")
    ingest_signals.add_argument(
        "--header",
        action="append",
        default=[],
        help="HTTP header for URL input, formatted as Name=Value; can be repeated",
    )
    ingest_signals.add_argument("--oddpool-quota-state", help="optional Oddpool Free quota ledger JSON path")
    ingest_signals.add_argument("--oddpool-monthly-quota", type=int, default=1000, help="Oddpool Free monthly request quota")
    ingest_signals.add_argument(
        "--oddpool-min-interval-seconds",
        type=float,
        default=1.0,
        help="minimum seconds between Oddpool requests",
    )

    signal_report = subparsers.add_parser("external-signal-report", help="summarize normalized external signals")
    signal_report.add_argument("path", help="external signal NDJSON path")
    signal_report.add_argument("--out", help="output JSON path; prints JSON to stdout when omitted")

    collect_signal_markets = subparsers.add_parser(
        "collect-external-signal-markets",
        help="append Gamma market rows for Polymarket market IDs referenced by external signals",
    )
    collect_signal_markets.add_argument("--external-signals", required=True, help="external signal NDJSON path")
    collect_signal_markets.add_argument("--out", required=True, help="Polymarket Gamma NDJSON path to append")
    collect_signal_markets.add_argument("--report-out", help="write collection summary JSON here")
    collect_signal_markets.add_argument("--limit", type=int, help="maximum unique Polymarket market IDs to refresh")
    collect_signal_markets.add_argument("--timeout", type=float, default=10.0, help="HTTP timeout in seconds")
    collect_signal_markets.add_argument("--proxy", help="HTTP proxy, for example 127.0.0.1:10808")
    collect_signal_markets.add_argument("--skip-errors", action="store_true", help="skip external signal market IDs that Gamma cannot resolve")
    collect_signal_markets.add_argument("--max-errors", type=int, default=20, help="maximum errors to include in report")
    collect_signal_markets.add_argument("--max-workers", type=int, default=8, help="parallel Gamma market fetch workers")

    match_cross = subparsers.add_parser("match-cross-platform", help="match Polymarket Gamma markets to Kalshi markets")
    match_cross.add_argument("--polymarket-gamma", required=True, help="raw Polymarket Gamma NDJSON path")
    match_cross.add_argument("--kalshi-markets", required=True, help="raw Kalshi market NDJSON path")
    match_cross.add_argument("--out", help="output JSON match report path")
    match_cross.add_argument("--signals-out", help="append candidate matches as external_signal rows")
    match_cross.add_argument("--min-score", type=float, default=0.35, help="minimum title-token Jaccard score")
    match_cross.add_argument("--top", type=int, default=100, help="maximum matches to include")
    match_cross.add_argument("--verified-only", action="store_true", help="write only semantically verified same-binary signals")

    expand_cross = subparsers.add_parser(
        "expand-cross-platform-candidates",
        help="expand Kalshi event-level candidates into market-ticker match candidates",
    )
    expand_cross.add_argument("--candidates", required=True, help="cross-platform event candidate JSON path")
    expand_cross.add_argument("--kalshi-markets", required=True, help="raw Kalshi market NDJSON path")
    expand_cross.add_argument("--polymarket-gamma", help="raw Polymarket Gamma NDJSON path for resolution details")
    expand_cross.add_argument("--out", help="output JSON match report path")
    expand_cross.add_argument("--signals-out", help="append candidate matches as external_signal rows")
    expand_cross.add_argument("--top", type=int, default=300, help="maximum expanded market matches to include")
    expand_cross.add_argument("--min-score", type=float, default=0.0, help="minimum expanded text score")
    expand_cross.add_argument("--verified-only", action="store_true", help="write only verified same-binary signals")

    verify_cross = subparsers.add_parser(
        "verify-cross-platform-matches",
        help="LLM-verify Polymarket/Kalshi same-binary match candidates",
    )
    verify_cross.add_argument("--matches", required=True, help="cross_platform_match_report JSON path")
    verify_cross.add_argument("--out", help="output verified cross-platform match report path")
    verify_cross.add_argument("--signals-out", help="append verified matches as external_signal rows")
    verify_cross.add_argument("--top", type=int, default=50, help="top match candidates to verify")
    verify_cross.add_argument("--batch-size", type=int, default=5, help="match candidates per LLM verification request")
    verify_cross.add_argument("--client-workers", type=int, default=1, help="parallel LLM verification batch workers")
    verify_cross.add_argument("--continue-on-error", action="store_true", help="keep verified rows from successful batches when a batch fails")
    verify_cross.add_argument("--verified-only", action="store_true", help="write only verified same-binary signals")
    verify_cross.add_argument("--model", help="OpenAI model name; defaults to OPENAI_MODEL")
    verify_cross.add_argument("--base-url", help="OpenAI-compatible base URL; defaults to OPENAI_BASE_URL or OpenAI")
    verify_cross.add_argument("--api-mode", choices=["responses", "chat", "messages"], help="OpenAI-compatible API mode; defaults to OPENAI_API_MODE or responses")
    verify_cross.add_argument("--secondary-model", help="secondary model; defaults to OPENAI_SECONDARY_MODEL")
    verify_cross.add_argument("--secondary-base-url", help="secondary OpenAI-compatible base URL; defaults to OPENAI_SECONDARY_BASE_URL")
    verify_cross.add_argument("--secondary-api-mode", choices=["responses", "chat", "messages"], help="secondary API mode; defaults to OPENAI_SECONDARY_API_MODE")
    verify_cross.add_argument("--backup-model", help="backup model; defaults to OPENAI_BACKUP_MODEL")
    verify_cross.add_argument("--backup-base-url", help="backup OpenAI-compatible base URL; defaults to OPENAI_BACKUP_BASE_URL")
    verify_cross.add_argument("--backup-api-mode", choices=["responses", "chat", "messages"], help="backup API mode; defaults to OPENAI_BACKUP_API_MODE")
    verify_cross.add_argument("--semantic-model", help="high-recall verifier model; defaults to OPENAI_SEMANTIC_MODEL")
    verify_cross.add_argument("--semantic-base-url", help="semantic OpenAI-compatible base URL; defaults to OPENAI_SEMANTIC_BASE_URL")
    verify_cross.add_argument("--semantic-api-mode", choices=["responses", "chat", "messages"], help="semantic API mode; defaults to OPENAI_SEMANTIC_API_MODE")
    verify_cross.add_argument("--fallback-model", help="fallback model; defaults to OPENAI_FALLBACK_MODEL")
    verify_cross.add_argument("--fallback-base-url", help="fallback OpenAI-compatible base URL; defaults to OPENAI_FALLBACK_BASE_URL")
    verify_cross.add_argument("--fallback-api-mode", choices=["responses", "chat", "messages"], help="fallback API mode; defaults to OPENAI_FALLBACK_API_MODE")
    verify_cross.add_argument("--timeout", type=float, default=60.0, help="HTTP timeout in seconds")
    verify_cross.add_argument("--secondary-timeout", type=float, help="secondary provider HTTP timeout; defaults to OPENAI_SECONDARY_TIMEOUT or --timeout")
    verify_cross.add_argument("--backup-timeout", type=float, help="backup provider HTTP timeout; defaults to OPENAI_BACKUP_TIMEOUT or --timeout")
    verify_cross.add_argument("--semantic-timeout", type=float, help="semantic provider HTTP timeout; defaults to OPENAI_SEMANTIC_TIMEOUT or --timeout")
    verify_cross.add_argument("--fallback-timeout", type=float, help="fallback provider HTTP timeout; defaults to OPENAI_FALLBACK_TIMEOUT or --timeout")
    verify_cross.add_argument("--retries", type=int, default=2, help="retry count for retryable OpenAI-compatible API errors")
    verify_cross.add_argument("--max-output-tokens", type=int, default=4000, help="maximum model output tokens")
    verify_cross.add_argument("--reasoning-effort", default="medium", help="OpenAI-compatible reasoning effort")
    verify_cross.add_argument("--verbosity", help="optional Responses API text verbosity")

    scan_cross = subparsers.add_parser(
        "scan-cross-platform-once",
        help="refresh verified Polymarket/Kalshi pairs once and scan cross-venue same-binary arbs",
    )
    scan_cross.add_argument("--matches", required=True, help="cross_platform_match_report JSON path")
    scan_cross.add_argument("--gamma", required=True, help="raw Polymarket Gamma NDJSON path")
    scan_cross.add_argument("--snapshots-out", required=True, help="append refreshed Polymarket/Kalshi binary snapshots here")
    scan_cross.add_argument("--kalshi-orderbooks-out", required=True, help="append raw Kalshi orderbooks here")
    scan_cross.add_argument("--out", help="output JSON scan report path; prints JSON when omitted")
    scan_cross.add_argument("--timeout", type=float, default=10.0, help="HTTP timeout in seconds")
    scan_cross.add_argument("--proxy", help="HTTP proxy, for example 127.0.0.1:10808")
    scan_cross.add_argument("--book-workers", type=int, default=1, help="parallel Polymarket CLOB book fetch workers")
    scan_cross.add_argument("--min-net-edge", type=float, default=0.0, help="minimum cross-platform edge per share")
    scan_cross.add_argument("--max-capital-per-trade", type=float, help="capital cap used for small-bankroll edge estimates")
    scan_cross.add_argument("--include-unverified", action="store_true", help="also scan unverified match candidates")

    filter_cross = subparsers.add_parser(
        "filter-cross-platform-opportunities",
        help="turn cross-platform scan opportunities back into LLM verification candidates",
    )
    filter_cross.add_argument("--scan", required=True, help="cross_platform_scan_report JSON path")
    filter_cross.add_argument("--matches", required=True, help="source cross_platform_match_report JSON path")
    filter_cross.add_argument("--out", help="output filtered match report path")
    filter_cross.add_argument("--top", type=int, default=60, help="maximum opportunity candidates to keep")
    filter_cross.add_argument("--min-net-edge", type=float, default=0.0, help="minimum scanned edge per share")
    filter_cross.add_argument("--no-option-match", action="store_true", help="do not require option text to match")

    watchlist = subparsers.add_parser("build-watchlist", help="write a standardized Polymarket token watchlist")
    watchlist.add_argument("--gamma", required=True, help="raw Polymarket Gamma NDJSON path")
    watchlist.add_argument("--rules", required=True, help="rule JSON path")
    watchlist.add_argument("--out", required=True, help="output watchlist JSON path")
    watchlist.add_argument(
        "--no-expand-neg-risk-groups",
        action="store_true",
        help="do not include known markets sharing a referenced negRiskMarketID",
    )
    watchlist.add_argument("--include-top-markets", type=int, default=0, help="also include this many top liquid markets")
    watchlist.add_argument(
        "--include-top-neg-risk-groups",
        type=int,
        default=0,
        help="also include every market from this many top neg-risk groups",
    )
    watchlist.add_argument("--min-liquidity", type=float, default=0.0, help="minimum liquidity for ranked additions")
    watchlist.add_argument("--min-volume-24h", type=float, default=0.0, help="minimum 24h volume for ranked additions")
    watchlist.add_argument("--max-markets", type=int, help="cap the final watchlist by priority score")
    watchlist.add_argument("--external-signals", help="external_signal NDJSON path used as a priority boost")

    stream_watchlist = subparsers.add_parser(
        "stream-polymarket-watchlist",
        help="stream Polymarket WebSocket orderbook updates for a standardized watchlist",
    )
    stream_watchlist.add_argument("--watchlist", required=True, help="watchlist JSON from build-watchlist")
    stream_watchlist.add_argument("--out", required=True, help="append realtime orderbook updates here")
    stream_watchlist.add_argument("--snapshots-out", help="append backtestable binary snapshots here")
    stream_watchlist.add_argument("--snapshot-interval", type=float, default=2.0, help="seconds between snapshot writes")
    stream_watchlist.add_argument("--max-messages", type=int, help="stop after this many raw WebSocket messages")
    stream_watchlist.add_argument("--ws-max-size", type=int, default=DEFAULT_WS_MAX_SIZE, help="maximum WebSocket message bytes")
    stream_watchlist.add_argument("--url", default=POLYMARKET_MARKET_WS_URL, help="Polymarket market WebSocket URL")

    realtime_monitor = subparsers.add_parser(
        "realtime-monitor-watchlist",
        help="stream a watchlist and scan opportunities from live WebSocket snapshots",
    )
    realtime_monitor.add_argument("--watchlist", required=True, help="watchlist JSON from build-watchlist")
    realtime_monitor.add_argument("--rules", required=True, help="rule JSON path")
    realtime_monitor.add_argument("--gamma", required=True, help="raw Polymarket Gamma NDJSON path for neg-risk groups")
    realtime_monitor.add_argument("--report-out", required=True, help="append realtime monitor JSONL report here")
    realtime_monitor.add_argument("--updates-out", help="append normalized realtime orderbook updates here")
    realtime_monitor.add_argument("--snapshots-out", help="append backtestable binary snapshots here")
    realtime_monitor.add_argument("--latest-snapshots-out", help="overwrite this NDJSON with the latest snapshot batch")
    realtime_monitor.add_argument("--snapshot-interval", type=float, default=2.0, help="seconds between scan iterations")
    realtime_monitor.add_argument("--stale-timeout", type=float, default=30.0, help="reconnect if no WS messages arrive for this many seconds")
    realtime_monitor.add_argument("--reconnect-delay", type=float, default=2.0, help="seconds to wait before reconnecting after a WS error")
    realtime_monitor.add_argument("--max-reconnects", type=int, help="maximum reconnect attempts before failing; default is unlimited")
    realtime_monitor.add_argument("--ws-max-size", type=int, default=DEFAULT_WS_MAX_SIZE, help="maximum WebSocket message bytes")
    realtime_monitor.add_argument("--max-messages", type=int, help="stop after this many raw WebSocket messages")
    realtime_monitor.add_argument("--max-iterations", type=int, help="stop after this many scan iterations")
    realtime_monitor.add_argument("--url", default=POLYMARKET_MARKET_WS_URL, help="Polymarket market WebSocket URL")
    realtime_monitor.add_argument("--min-net-edge", type=float, default=0.0, help="minimum edge per share")
    realtime_monitor.add_argument("--max-capital-per-trade", type=float, help="cap simulated capital per opportunity")
    realtime_monitor.add_argument("--bankroll", type=float, help="cap simulated bankroll per scan iteration")
    _add_paper_filter_args(realtime_monitor)
    realtime_monitor.add_argument("--min-run-observations", type=int, default=1, help="stable opportunity observations to report")
    realtime_monitor.add_argument("--min-run-seconds", type=float, default=0.0, help="stable opportunity duration to report")
    realtime_monitor.add_argument(
        "--max-opportunities-per-iteration",
        type=int,
        default=10,
        help="maximum current/stable opportunities to include in each report row",
    )
    realtime_monitor.add_argument("--seed-orderbooks", action="store_true", help="seed token books via HTTP before streaming WebSocket deltas")
    realtime_monitor.add_argument("--seed-timeout", type=float, default=10.0, help="HTTP timeout for seed orderbook requests")
    realtime_monitor.add_argument("--seed-proxy", help="HTTP proxy for seed orderbook requests, for example 127.0.0.1:10808")
    realtime_monitor.add_argument("--seed-workers", type=int, default=8, help="parallel seed orderbook HTTP workers")

    monitor_alerts = subparsers.add_parser(
        "monitor-alerts",
        help="extract standardized opportunity alerts from the latest monitor report iteration",
    )
    monitor_alerts.add_argument("path", help="paper-monitor or realtime-monitor JSONL report path")
    monitor_alerts.add_argument("--out", help="append opportunity_alert rows here; prints JSONL when omitted")
    monitor_alerts.add_argument("--min-paper-roi", type=float, help="minimum stable paper trade ROI")
    monitor_alerts.add_argument("--min-paper-edge", type=float, help="minimum stable paper trade edge")
    monitor_alerts.add_argument("--include-current", action="store_true", help="also alert on latest current/stable opportunities")
    monitor_alerts.add_argument("--max-alerts", type=int, default=20, help="maximum alert rows to emit")
    monitor_alerts.add_argument("--state", help="optional alert cooldown state JSON path")
    monitor_alerts.add_argument("--cooldown-seconds", type=float, default=0.0, help="suppress duplicate alerts for this many seconds when --state is set")

    notify = subparsers.add_parser("notify-alerts", help="send latest opportunity alerts to webhook/chat/local sinks")
    notify.add_argument("path", help="opportunity_alert NDJSON path")
    notify.add_argument("--out", help="output notification_result NDJSON path; prints JSONL when omitted")
    notify.add_argument("--max-alerts", type=int, default=20, help="latest alerts to notify")
    notify.add_argument("--webhook-url", help="generic JSON webhook URL; defaults to ALERT_WEBHOOK_URL")
    notify.add_argument("--telegram-bot-token", help="Telegram bot token; defaults to TELEGRAM_BOT_TOKEN")
    notify.add_argument("--telegram-chat-id", help="Telegram chat id; defaults to TELEGRAM_CHAT_ID")
    notify.add_argument("--discord-webhook-url", help="Discord webhook URL; defaults to DISCORD_WEBHOOK_URL")
    notify.add_argument("--desktop", action="store_true", help="also send a local macOS desktop notification")
    notify.add_argument("--dry-run", action="store_true", help="format notification_result rows without network or desktop sends")
    notify.add_argument("--timeout", type=float, default=10.0, help="HTTP timeout in seconds")
    notify.add_argument("--proxy", help="HTTP proxy, for example 127.0.0.1:10808")

    return parser


def _add_paper_filter_args(parser) -> None:
    parser.add_argument("--min-paper-roi", type=float, help="minimum ROI for selected paper trades")
    parser.add_argument("--min-paper-edge", type=float, help="minimum total edge for selected paper trades")
    parser.add_argument(
        "--min-paper-quantity",
        type=float,
        default=1e-9,
        help="minimum selected paper trade quantity",
    )


def _add_pretrade_check_args(parser) -> None:
    parser.add_argument("--max-leg-count", type=int, help="fail pretrade check if a plan has more legs")
    parser.add_argument("--max-worst-price", type=float, help="fail pretrade check if any buy reference price exceeds this value")
    parser.add_argument("--require-single-level", action="store_true", help="fail pretrade check if a leg crosses multiple price levels")
    parser.add_argument("--min-limit-edge-per-share", type=float, help="fail pretrade check unless order limit prices keep this edge")
    parser.add_argument("--min-limit-roi", type=float, help="fail pretrade check unless order limit prices keep this ROI")
    parser.add_argument("--require-pretrade-pass", action="store_true", help="skip execution plans that fail pretrade checks")


def _add_risk_args(parser) -> None:
    parser.add_argument("--risk-state", help="optional JSON risk state with daily orders/loss/pause_until")
    parser.add_argument("--kill-switch", help="file path that blocks plans while present")
    parser.add_argument("--max-trade-notional", type=float, help="maximum plan notional")
    parser.add_argument("--max-daily-loss", type=float, help="maximum daily worst-case notional/loss budget")
    parser.add_argument("--max-daily-orders", type=int, help="maximum daily order count including this plan")
    parser.add_argument("--max-order-count", type=int, help="maximum order count in a single plan")
    parser.add_argument("--require-risk-pass", action="store_true", help="skip execution plans that fail risk checks")


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
    gamma_path = Path(args.gamma)
    rule_set = load_rule_set(Path(args.rules), gamma_path=gamma_path if gamma_path.exists() else None)
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
                expand_neg_risk_groups=not args.no_expand_neg_risk_groups,
                max_markets=args.max_markets,
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
                min_paper_roi=args.min_paper_roi,
                min_paper_edge=args.min_paper_edge,
                min_paper_quantity=args.min_paper_quantity,
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
                min_quantity=args.min_paper_quantity,
                min_roi=args.min_paper_roi,
                min_edge=args.min_paper_edge,
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


def _scan_cross_platform_once(args) -> dict:
    match_report = json.loads(Path(args.matches).read_text())
    pairs = cross_platform_pairs(match_report, verified_only=not args.include_unverified)
    snapshots_path = Path(args.snapshots_out)
    kalshi_orderbooks_path = Path(args.kalshi_orderbooks_out)
    snapshot_offset = _file_size(snapshots_path)
    kalshi_orderbook_offset = _file_size(kalshi_orderbooks_path)
    poly_market_ids = [pair["polymarket_market_id"] for pair in pairs]
    kalshi_tickers = [pair["kalshi_ticker"] for pair in pairs]

    poly_count = collect_polymarket_binary_snapshots_for_market_ids(
        snapshots_path,
        Path(args.gamma),
        poly_market_ids,
        args.timeout,
        args.proxy,
        args.book_workers,
        skip_book_errors=True,
        expand_neg_risk_groups=False,
        refresh_missing_gamma=True,
    )
    kalshi_orderbook_count = collect_kalshi_orderbooks(kalshi_orderbooks_path, kalshi_tickers, args.timeout, args.proxy)
    orderbook_text, _ = _read_appended_text(kalshi_orderbooks_path, kalshi_orderbook_offset)
    kalshi_snapshot_rows = list(kalshi_binary_snapshot_rows_from_orderbook_lines(orderbook_text.splitlines()))
    snapshots_path.parent.mkdir(parents=True, exist_ok=True)
    with snapshots_path.open("a") as handle:
        for row in kalshi_snapshot_rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    kalshi_snapshot_count = len(kalshi_snapshot_rows)
    appended_text, _ = _read_appended_text(snapshots_path, snapshot_offset)
    snapshots = list(snapshots_from_ndjson_lines(appended_text.splitlines()))
    by_venue_market = {(snapshot.venue, snapshot.market_id): snapshot for snapshot in snapshots}
    opportunities = []
    skipped_pairs = []
    for pair in pairs:
        polymarket_snapshot = by_venue_market.get(("polymarket", pair["polymarket_market_id"]))
        kalshi_snapshot = by_venue_market.get(("kalshi", pair["kalshi_ticker"]))
        if polymarket_snapshot is None or kalshi_snapshot is None:
            skipped_pairs.append(
                {
                    "pair": pair,
                    "reason": "missing_snapshot",
                    "polymarket_snapshot": polymarket_snapshot is not None,
                    "kalshi_snapshot": kalshi_snapshot is not None,
                }
            )
            continue
        for opportunity in find_cross_venue_same_binary(polymarket_snapshot, kalshi_snapshot, min_net_edge=args.min_net_edge):
            opportunity_row = opportunity_to_row(opportunity)
            opportunity_row["pair"] = pair
            if args.max_capital_per_trade is not None:
                opportunity_row["capital_capped"] = _capital_capped_opportunity(opportunity, args.max_capital_per_trade)
            opportunities.append(opportunity_row)

    opportunities.sort(key=lambda row: (-float(row.get("net_edge_per_share") or 0.0), row.get("key") or ""))
    return {
        "type": "cross_platform_scan_report",
        "matches_path": args.matches,
        "gamma_path": args.gamma,
        "snapshots_path": args.snapshots_out,
        "kalshi_orderbooks_path": args.kalshi_orderbooks_out,
        "pair_count": len(pairs),
        "snapshot_count": len(snapshots),
        "polymarket_snapshot_count": poly_count,
        "kalshi_orderbook_count": kalshi_orderbook_count,
        "kalshi_snapshot_count": kalshi_snapshot_count,
        "opportunity_count": len(opportunities),
        "skipped_pair_count": len(skipped_pairs),
        "opportunities": opportunities,
        "skipped_pairs": skipped_pairs,
    }


def _cross_platform_verifier_clients(args) -> list:
    specs = [
        (
            "primary",
            args.model or os.environ.get("OPENAI_MODEL"),
            os.environ.get("OPENAI_API_KEY"),
            args.base_url or os.environ.get("OPENAI_BASE_URL"),
            args.api_mode or os.environ.get("OPENAI_API_MODE"),
            args.timeout,
        ),
        (
            "secondary",
            args.secondary_model or os.environ.get("OPENAI_SECONDARY_MODEL"),
            os.environ.get("OPENAI_SECONDARY_API_KEY") or os.environ.get("OPENAI_API_KEY"),
            args.secondary_base_url or os.environ.get("OPENAI_SECONDARY_BASE_URL"),
            args.secondary_api_mode or os.environ.get("OPENAI_SECONDARY_API_MODE"),
            _optional_float(args.secondary_timeout, os.environ.get("OPENAI_SECONDARY_TIMEOUT"), args.timeout),
        ),
        (
            "backup",
            args.backup_model or os.environ.get("OPENAI_BACKUP_MODEL"),
            os.environ.get("OPENAI_BACKUP_API_KEY") or os.environ.get("OPENAI_API_KEY"),
            args.backup_base_url or os.environ.get("OPENAI_BACKUP_BASE_URL"),
            args.backup_api_mode or os.environ.get("OPENAI_BACKUP_API_MODE"),
            _optional_float(args.backup_timeout, os.environ.get("OPENAI_BACKUP_TIMEOUT"), args.timeout),
        ),
        (
            "semantic",
            args.semantic_model or os.environ.get("OPENAI_SEMANTIC_MODEL"),
            os.environ.get("OPENAI_SEMANTIC_API_KEY") or os.environ.get("OPENAI_API_KEY"),
            args.semantic_base_url or os.environ.get("OPENAI_SEMANTIC_BASE_URL"),
            args.semantic_api_mode or os.environ.get("OPENAI_SEMANTIC_API_MODE"),
            _optional_float(args.semantic_timeout, os.environ.get("OPENAI_SEMANTIC_TIMEOUT"), args.timeout),
        ),
        (
            "fallback",
            args.fallback_model or os.environ.get("OPENAI_FALLBACK_MODEL"),
            os.environ.get("OPENAI_FALLBACK_API_KEY") or os.environ.get("OPENAI_API_KEY"),
            args.fallback_base_url or os.environ.get("OPENAI_FALLBACK_BASE_URL"),
            args.fallback_api_mode or os.environ.get("OPENAI_FALLBACK_API_MODE"),
            _optional_float(args.fallback_timeout, os.environ.get("OPENAI_FALLBACK_TIMEOUT"), args.timeout),
        ),
    ]
    clients = []
    seen = set()
    for label, model, api_key, base_url, api_mode, timeout in specs:
        if not model:
            continue
        identity = (model, api_key, base_url, api_mode)
        if identity in seen:
            continue
        seen.add(identity)
        clients.append(
            (
                label,
                OpenAICrossPlatformVerifierClient(
                    model=model,
                    api_key=api_key,
                    timeout=timeout,
                    base_url=base_url,
                    retries=args.retries,
                    max_output_tokens=args.max_output_tokens,
                    reasoning_effort=args.reasoning_effort,
                    verbosity=args.verbosity,
                    api_mode=api_mode,
                ),
            )
        )
    return clients


def _verify_cross_platform_batch(batch_index: int, batch: list, clients: list) -> dict:
    verifications = []
    errors = []
    provider_attempts = []
    batch_verified = False
    last_rows = []
    for provider_index, (provider_label, client) in enumerate(clients):
        try:
            rows = client.verify_matches(batch)
            if batch and not rows:
                raise OpenAIResponseError("parsed zero cross-platform verifications")
            last_rows = rows
            should_escalate = _should_semantic_escalate_cross_platform(provider_label, rows, batch, clients[provider_index + 1 :])
            provider_attempts.append(
                {
                    "batch_index": batch_index,
                    "provider": provider_label,
                    "status": "ok_escalated" if should_escalate else "ok",
                    "batch_size": len(batch),
                    "parsed_rows": len(rows),
                }
            )
            if should_escalate:
                continue
            verifications.extend(rows)
            batch_verified = True
            break
        except (OpenAIResponseError, OSError, TimeoutError, RuntimeError) as exc:
            errors.append(
                {
                    "error_type": exc.__class__.__name__,
                    "message": str(exc),
                    "batch_size": len(batch),
                    "batch_index": batch_index,
                    "provider": provider_label,
                }
            )
            provider_attempts.append(
                {
                    "batch_index": batch_index,
                    "provider": provider_label,
                    "status": "error",
                    "batch_size": len(batch),
                    "error_type": exc.__class__.__name__,
                }
            )
    if not batch_verified:
        if last_rows:
            verifications.extend(last_rows)
            batch_verified = True
        else:
            errors.append(
                {
                    "batch_size": len(batch),
                    "batch_index": batch_index,
                    "error_type": "all_providers_failed",
                    "message": "all configured cross-platform verifier providers failed",
                }
            )
    return {
        "batch_index": batch_index,
        "verifications": verifications,
        "errors": errors,
        "provider_attempts": provider_attempts,
        "failed": not batch_verified,
    }


def _should_semantic_escalate_cross_platform(provider_label: str, rows: list, batch: list, remaining_clients: list) -> bool:
    if provider_label == "semantic" or not any(label == "semantic" for label, _ in remaining_clients):
        return False
    tradeable_pairs = {
        (str(row.get("polymarket_market_id") or ""), str(row.get("kalshi_ticker") or ""))
        for row in rows
        if row.get("trade_allowed") and row.get("verified_same_binary_event", True)
    }
    batch_pairs = {
        (str(match.get("polymarket_market_id") or ""), str(match.get("kalshi_ticker") or ""))
        for match in batch
    }
    return not batch_pairs.issubset(tradeable_pairs)


def _capital_capped_opportunity(opportunity, max_capital: float) -> dict:
    if max_capital <= 0:
        raise ValueError("--max-capital-per-trade must be positive")
    selection = select_paper_trades(
        [opportunity],
        max_capital_per_trade=max_capital,
        min_quantity=0.0,
    )
    if selection.trades:
        trade = selection.trades[0]
        return {
            "max_capital": max_capital,
            "quantity": trade.quantity,
            "capital_used": trade.capital_used,
            "edge": trade.edge,
            "roi": trade.roi,
            "cost_per_share": trade.opportunity.cost_per_share,
            "net_edge_per_share": trade.opportunity.net_edge_per_share,
            "quality": trade_to_row(trade).get("quality"),
        }
    return {
        "max_capital": max_capital,
        "quantity": 0.0,
        "capital_used": 0.0,
        "edge": 0.0,
        "roi": 0.0,
        "rejected": True,
        "rejections": [rejection_to_row(rejection) for rejection in selection.rejections],
    }


def _optional_float(primary, env_value, default: float) -> float:
    if primary is not None:
        return float(primary)
    if env_value not in (None, ""):
        return float(env_value)
    return float(default)


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


def _print_realtime_monitor_progress(row: dict) -> None:
    print(
        f"iteration={row['iteration']} messages={row['messages_seen']} "
        f"snapshots={row['snapshots_collected']} "
        f"current_opportunities={row['current_opportunity_count']} "
        f"stable_opportunities={row['stable_opportunity_count']} "
        f"stable_paper_edge={row['stable_paper_edge']:.6f}"
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
    top_stable_rejections = [
        rejection_to_row(rejection)
        for rejection in stable_selection.rejections[: args.max_opportunities_per_iteration]
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
        "stable_paper_rejections": top_stable_rejections,
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
        min_quantity=args.min_paper_quantity,
        min_roi=args.min_paper_roi,
        min_edge=args.min_paper_edge,
    )
    runs_by_key = {run.key: run for run in getattr(result, "runs", [])}
    rows = []
    plans = []
    for trade in selection.trades[: args.max_trades]:
        plan = build_execution_plan(
            trade,
            slippage_bps=args.slippage_bps,
            tick_size=args.tick_size,
            neg_risk=args.neg_risk,
            order_type=args.order_type,
            dry_run=not args.live,
        )
        check = pretrade_check_row(
            trade,
            run=runs_by_key.get(opportunity_key(trade.opportunity)),
            max_leg_count=args.max_leg_count,
            max_worst_price=args.max_worst_price,
            require_single_level=args.require_single_level,
            plan=plan,
            min_limit_edge_per_share=args.min_limit_edge_per_share,
            min_limit_roi=args.min_limit_roi,
        )
        if args.require_pretrade_pass and not check["passed"]:
            continue
        row = plan_to_row(plan)
        row["pretrade_check"] = check
        risk_check = _risk_check_row(row, args)
        row["risk_check"] = risk_check
        if getattr(args, "require_risk_pass", False) and not risk_check["passed"]:
            continue
        row["reconciliation"] = reconcile_execution_responses(row, [])
        rows.append(row)
        plans.append(plan)
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
            row["reconciliation"] = reconcile_execution_responses(row, row["responses"])
            if getattr(args, "risk_state", None):
                row["risk_state_update"] = update_risk_state_from_execution_result(
                    row,
                    row["responses"],
                    Path(args.risk_state),
                    reconciliation=row["reconciliation"],
                )
    return rows


def _risk_check_row(plan_row: dict, args) -> dict:
    return risk_check_execution_plan(
        plan_row,
        state_path=Path(args.risk_state) if getattr(args, "risk_state", None) else None,
        kill_switch_path=Path(args.kill_switch) if getattr(args, "kill_switch", None) else None,
        max_trade_notional=getattr(args, "max_trade_notional", None),
        max_daily_loss=getattr(args, "max_daily_loss", None),
        max_daily_orders=getattr(args, "max_daily_orders", None),
        max_order_count=getattr(args, "max_order_count", None),
        live=getattr(args, "live", False),
    )


def _write_jsonl_or_stdout(rows: list, out: str) -> None:
    if out:
        path = Path(out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + ("\n" if rows else ""))
    else:
        for row in rows:
            print(json.dumps(row, sort_keys=True))


def _parse_int_csv(value: str) -> list:
    rows = []
    for raw_item in str(value or "").split(","):
        item = raw_item.strip()
        if not item:
            continue
        try:
            rows.append(int(item))
        except ValueError as exc:
            raise ValueError(f"expected comma-separated integers, got {value!r}") from exc
    if not rows:
        raise ValueError("expected at least one integer")
    return rows


def _headers_from_args(values: list) -> dict:
    headers = {}
    for value in values or []:
        if "=" not in value:
            raise ValueError("--header must be formatted as Name=Value")
        name, header_value = value.split("=", 1)
        name = name.strip()
        if not name:
            raise ValueError("--header name cannot be empty")
        headers[name] = header_value
    return headers


def _read_lines(path: Path) -> list:
    return [line.strip() for line in path.read_text().splitlines() if line.strip()]


def _market_ids_from_hybrid_scan(path: Path, top_n: int) -> list:
    if top_n < 1:
        raise ValueError("--top-markets must be at least 1")
    row = json.loads(path.read_text())
    market_ids = []
    seen = set()
    for candidate in list(row.get("top") or [])[:top_n]:
        for market_id in candidate.get("market_ids") or []:
            normalized = str(market_id).strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            market_ids.append(normalized)
    return market_ids


def _chunks(rows: list, size: int) -> list:
    if size < 1:
        raise ValueError("batch size must be at least 1")
    return [rows[index : index + size] for index in range(0, len(rows), size)]


def _read_jsonl_rows(path: Path) -> list:
    rows = []
    with path.open() as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


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
