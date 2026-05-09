import io
import json
from types import SimpleNamespace
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from poly_strategy.cli import main


class CliTests(unittest.TestCase):
    def test_sample_command_writes_backtestable_ndjson(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.ndjson"
            code = main(["sample", "--out", str(path)])

            self.assertEqual(code, 0)
            row = json.loads(path.read_text().splitlines()[0])
            self.assertEqual(row["type"], "binary_snapshot")

    def test_backtest_command_prints_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.ndjson"
            path.write_text(
                json.dumps(
                    {
                        "ts": "2026-05-08T00:00:00Z",
                        "type": "binary_snapshot",
                        "venue": "polymarket",
                        "market_id": "sample",
                        "fee_rate": 0.0,
                        "yes": {"asks": [[0.45, 10]], "bids": []},
                        "no": {"asks": [[0.53, 7]], "bids": []},
                    }
                )
                + "\n"
            )

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = main(["backtest", str(path)])

            self.assertEqual(code, 0)
            self.assertIn("snapshots=1", stdout.getvalue())
            self.assertIn("opportunities=1", stdout.getvalue())

    def test_backtest_command_accepts_capital_cap_and_prints_paper_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.ndjson"
            path.write_text(
                json.dumps(
                    {
                        "ts": "2026-05-08T00:00:00Z",
                        "type": "binary_snapshot",
                        "venue": "polymarket",
                        "market_id": "sample",
                        "fee_rate": 0.0,
                        "yes": {"asks": [[0.45, 100]], "bids": []},
                        "no": {"asks": [[0.53, 100]], "bids": []},
                    }
                )
                + "\n"
            )

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = main(["backtest", str(path), "--max-capital-per-trade", "9.80"])

        self.assertEqual(code, 0)
        self.assertIn("paper_trades=1", stdout.getvalue())
        self.assertIn("paper_capital=9.800000", stdout.getvalue())
        self.assertIn("paper_edge=0.200000", stdout.getvalue())

    def test_backtest_command_applies_min_paper_roi_filter(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.ndjson"
            path.write_text(
                json.dumps(
                    {
                        "ts": "2026-05-08T00:00:00Z",
                        "type": "binary_snapshot",
                        "venue": "polymarket",
                        "market_id": "sample",
                        "fee_rate": 0.0,
                        "yes": {"asks": [[0.45, 100]], "bids": []},
                        "no": {"asks": [[0.53, 100]], "bids": []},
                    }
                )
                + "\n"
            )

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = main(
                    [
                        "backtest",
                        str(path),
                        "--max-capital-per-trade",
                        "9.80",
                        "--min-paper-roi",
                        "0.03",
                    ]
                )

        self.assertEqual(code, 0)
        self.assertIn("opportunities=1", stdout.getvalue())
        self.assertIn("paper_trades=0", stdout.getvalue())

    def test_backtest_command_accepts_rules_path(self):
        with patch("poly_strategy.cli.replay_ndjson") as replay:
            replay.return_value.snapshot_count = 0
            replay.return_value.opportunity_count = 0
            replay.return_value.total_edge = 0
            replay.return_value.paper_trade_count = 0
            replay.return_value.paper_capital_used = 0
            replay.return_value.paper_edge = 0
            replay.return_value.runs = []
            replay.return_value.opportunities = []

            code = main(["backtest", "data/live.ndjson", "--rules", "rules/implications.json"])

        self.assertEqual(code, 0)
        self.assertEqual(str(replay.call_args.kwargs["rules_path"]), "rules/implications.json")

    def test_collect_polymarket_binaries_passes_proxy_to_collector(self):
        with patch("poly_strategy.cli.collect_polymarket_binary_snapshots_loop", return_value=3) as collect:
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = main(
                    [
                        "collect-polymarket-binaries",
                        "--out",
                        "data/live.ndjson",
                        "--limit",
                        "3",
                        "--timeout",
                        "4",
                        "--proxy",
                        "http://127.0.0.1:10808",
                        "--iterations",
                        "2",
                        "--interval",
                        "0.5",
                        "--book-workers",
                        "4",
                    ]
                )

        self.assertEqual(code, 0)
        collect.assert_called_once()
        args = collect.call_args.args
        self.assertEqual(str(args[0]), "data/live.ndjson")
        self.assertEqual(args[1], 3)
        self.assertEqual(args[2], 4.0)
        self.assertEqual(args[3], "http://127.0.0.1:10808")
        self.assertEqual(args[4], 0.5)
        self.assertEqual(args[5], 2)
        self.assertEqual(collect.call_args.kwargs["max_workers"], 4)
        self.assertIn("wrote=3", stdout.getvalue())

    def test_collect_polymarket_can_fetch_gamma_markets_by_id(self):
        with patch("poly_strategy.cli.collect_polymarket_gamma_markets_by_id", return_value=2) as collect:
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = main(
                    [
                        "collect-polymarket",
                        "--out",
                        "data/gamma.ndjson",
                        "--market-id",
                        "544094",
                        "--market-id",
                        "544095",
                        "--timeout",
                        "7",
                        "--proxy",
                        "127.0.0.1:10808",
                    ]
                )

        self.assertEqual(code, 0)
        collect.assert_called_once()
        self.assertEqual(str(collect.call_args.args[0]), "data/gamma.ndjson")
        self.assertEqual(collect.call_args.args[1], ["544094", "544095"])
        self.assertEqual(collect.call_args.args[2], 7.0)
        self.assertEqual(collect.call_args.args[3], "127.0.0.1:10808")
        self.assertIn("wrote=2", stdout.getvalue())

    def test_collect_polymarket_can_fetch_gamma_market_pages(self):
        with patch("poly_strategy.cli.collect_polymarket_gamma_pages", return_value=200) as collect:
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = main(
                    [
                        "collect-polymarket",
                        "--out",
                        "data/gamma.ndjson",
                        "--limit",
                        "100",
                        "--pages",
                        "2",
                        "--offset",
                        "50",
                        "--timeout",
                        "7",
                        "--proxy",
                        "127.0.0.1:10808",
                    ]
                )

        self.assertEqual(code, 0)
        collect.assert_called_once()
        args = collect.call_args.args
        self.assertEqual(str(args[0]), "data/gamma.ndjson")
        self.assertEqual(args[1], 100)
        self.assertEqual(args[2], 2)
        self.assertEqual(args[3], 7.0)
        self.assertEqual(args[4], "127.0.0.1:10808")
        self.assertEqual(args[5], 50)
        self.assertIn("wrote=200", stdout.getvalue())

    def test_collect_kalshi_command_invokes_collector(self):
        with patch("poly_strategy.cli.collect_kalshi_markets", return_value=3) as collect:
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = main(
                    [
                        "collect-kalshi",
                        "--out",
                        "data/kalshi.ndjson",
                        "--limit",
                        "3",
                        "--status",
                        "open",
                        "--ticker",
                        "KXTEST",
                        "--timeout",
                        "7",
                        "--proxy",
                        "127.0.0.1:10808",
                    ]
                )

        self.assertEqual(code, 0)
        self.assertEqual(str(collect.call_args.args[0]), "data/kalshi.ndjson")
        self.assertEqual(collect.call_args.args[1], 3)
        self.assertEqual(collect.call_args.kwargs["tickers"], ["KXTEST"])
        self.assertIn("wrote=3", stdout.getvalue())

    def test_collect_rule_markets_passes_gamma_and_rules_to_targeted_collector(self):
        with patch("poly_strategy.cli.collect_polymarket_binary_snapshots_for_rules_loop", return_value=4) as collect:
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = main(
                    [
                        "collect-rule-markets",
                        "--out",
                        "data/targeted.ndjson",
                        "--gamma",
                        "data/gamma.ndjson",
                        "--rules",
                        "rules/generated.json",
                        "--timeout",
                        "8",
                        "--proxy",
                        "127.0.0.1:10808",
                        "--iterations",
                        "2",
                        "--interval",
                        "3",
                        "--book-workers",
                        "5",
                    ]
                )

        self.assertEqual(code, 0)
        args = collect.call_args.args
        self.assertEqual(str(args[0]), "data/targeted.ndjson")
        self.assertEqual(str(args[1]), "data/gamma.ndjson")
        self.assertEqual(str(args[2]), "rules/generated.json")
        self.assertEqual(args[3], 8.0)
        self.assertEqual(args[4], "127.0.0.1:10808")
        self.assertEqual(args[5], 3.0)
        self.assertEqual(args[6], 2)
        self.assertEqual(collect.call_args.kwargs["max_workers"], 5)
        self.assertTrue(collect.call_args.kwargs["expand_neg_risk_groups"])
        self.assertIn("wrote=4", stdout.getvalue())

    def test_monitor_rules_collects_targeted_snapshots_and_replays(self):
        with patch("poly_strategy.cli.collect_polymarket_binary_snapshots_for_rules", return_value=2) as collect:
            with patch("poly_strategy.cli.replay_ndjson") as replay:
                replay.return_value.snapshot_count = 2
                replay.return_value.opportunity_count = 1
                replay.return_value.paper_edge = 0.25

                stdout = io.StringIO()
                with redirect_stdout(stdout):
                    code = main(
                        [
                            "monitor-rules",
                            "--out",
                            "data/monitor.ndjson",
                            "--gamma",
                            "data/gamma.ndjson",
                            "--rules",
                            "rules/generated.json",
                            "--iterations",
                            "1",
                            "--min-net-edge",
                            "0.002",
                            "--max-capital-per-trade",
                            "20",
                            "--book-workers",
                            "3",
                        ]
                    )

        self.assertEqual(code, 0)
        collect.assert_called_once()
        self.assertEqual(collect.call_args.args[5], 3)
        self.assertTrue(collect.call_args.kwargs["expand_neg_risk_groups"])
        replay.assert_called_once()
        self.assertEqual(replay.call_args.kwargs["min_net_edge"], 0.002)
        self.assertEqual(replay.call_args.kwargs["max_capital_per_trade"], 20.0)
        self.assertIn("opportunities=1", stdout.getvalue())

    def test_paper_monitor_writes_iteration_and_summary_report(self):
        def collect_once(path, gamma, rules, timeout, proxy, max_workers, **kwargs):
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a") as handle:
                handle.write(
                    json.dumps(
                        {
                            "ts": "2026-05-09T00:00:00Z",
                            "type": "binary_snapshot",
                            "venue": "polymarket",
                            "market_id": "sample",
                            "fee_rate": 0.0,
                            "yes": {"token_id": "yes-token", "asks": [[0.51, 100]], "bids": []},
                            "no": {"token_id": "no-token", "asks": [[0.51, 100]], "bids": []},
                        }
                    )
                    + "\n"
                )
            return 1

        with tempfile.TemporaryDirectory() as tmp:
            snapshots = Path(tmp) / "snapshots.ndjson"
            report = Path(tmp) / "paper-monitor.jsonl"
            rules = Path(tmp) / "rules.json"
            rules.write_text("{}")
            with patch("poly_strategy.cli.collect_polymarket_binary_snapshots_for_rules", side_effect=collect_once) as collect:
                stdout = io.StringIO()
                with redirect_stdout(stdout):
                    code = main(
                        [
                            "paper-monitor",
                            "--gamma",
                            "data/gamma.ndjson",
                            "--rules",
                            str(rules),
                            "--snapshots-out",
                            str(snapshots),
                            "--report-out",
                            str(report),
                            "--iterations",
                            "1",
                            "--interval",
                            "0",
                            "--book-workers",
                            "4",
                            "--skip-book-errors",
                        ]
                    )
            rows = [json.loads(line) for line in report.read_text().splitlines()]

        self.assertEqual(code, 0)
        collect.assert_called_once()
        self.assertEqual(collect.call_args.args[5], 4)
        self.assertTrue(collect.call_args.kwargs["expand_neg_risk_groups"])
        self.assertTrue(collect.call_args.kwargs["skip_book_errors"])
        self.assertEqual(rows[0]["type"], "paper_monitor_iteration")
        self.assertEqual(rows[0]["snapshots_collected"], 1)
        self.assertEqual(rows[0]["snapshot_count"], 1)
        self.assertEqual(rows[1]["type"], "paper_monitor_summary")
        self.assertIn("completed_iterations=1", stdout.getvalue())

    def test_paper_monitor_can_continue_after_iteration_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            snapshots = Path(tmp) / "snapshots.ndjson"
            report = Path(tmp) / "paper-monitor.jsonl"
            rules = Path(tmp) / "rules.json"
            rules.write_text("{}")
            with patch(
                "poly_strategy.cli.collect_polymarket_binary_snapshots_for_rules",
                side_effect=RuntimeError("temporary failure"),
            ):
                with patch("poly_strategy.cli.replay_ndjson") as replay:
                    stdout = io.StringIO()
                    stderr = io.StringIO()
                    with redirect_stdout(stdout), redirect_stderr(stderr):
                        code = main(
                            [
                                "paper-monitor",
                                "--gamma",
                                "data/gamma.ndjson",
                                "--rules",
                                str(rules),
                                "--snapshots-out",
                                str(snapshots),
                                "--report-out",
                                str(report),
                                "--iterations",
                                "1",
                                "--interval",
                                "0",
                                "--continue-on-error",
                            ]
                        )
            rows = [json.loads(line) for line in report.read_text().splitlines()]

        self.assertEqual(code, 0)
        replay.assert_not_called()
        self.assertEqual(rows[0]["type"], "paper_monitor_iteration_error")
        self.assertEqual(rows[0]["phase"], "collect")
        self.assertEqual(rows[0]["error_type"], "RuntimeError")
        self.assertEqual(rows[0]["snapshots_collected"], 0)
        self.assertEqual(rows[1]["type"], "paper_monitor_summary")
        self.assertEqual(rows[1]["error_iterations"], 1)

    def test_paper_analyze_command_writes_monitor_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "paper-monitor.jsonl"
            out = Path(tmp) / "analysis.json"
            snapshots = Path(tmp) / "snapshots.ndjson"
            rules = Path(tmp) / "rules.json"
            gamma = Path(tmp) / "gamma.ndjson"
            report.write_text(
                "\n".join(
                    json.dumps(row)
                    for row in [
                        {
                            "type": "paper_monitor_iteration",
                            "ts": "2026-05-09T00:00:00Z",
                            "iteration": 1,
                            "snapshots_collected": 2,
                            "snapshot_count": 2,
                            "current_opportunity_count": 1,
                            "stable_opportunity_count": 1,
                            "stable_paper_trade_count": 1,
                            "stable_paper_capital_used": 10,
                            "stable_paper_edge": 0.2,
                            "current_opportunities": [
                                {
                                    "key": "arb:a",
                                    "kind": "yes_no_bundle",
                                    "net_edge_per_share": 0.02,
                                    "total_edge": 0.2,
                                    "legs": [{"market_id": "m1"}],
                                }
                            ],
                            "stable_opportunities": [
                                {
                                    "key": "arb:a",
                                    "kind": "yes_no_bundle",
                                    "net_edge_per_share": 0.02,
                                    "total_edge": 0.2,
                                    "legs": [{"market_id": "m1"}],
                                }
                            ],
                            "stable_paper_trades": [{"paper_roi": 0.02}],
                            "errors": [],
                            "error_count": 0,
                        },
                        {
                            "type": "paper_monitor_iteration_error",
                            "ts": "2026-05-09T00:00:05Z",
                            "iteration": 2,
                            "phase": "collect",
                            "snapshots_collected": 0,
                            "error_type": "RuntimeError",
                            "message": "temporary failure",
                            "errors": [{"kind": "book_fetch_error"}],
                            "error_count": 1,
                        },
                        {
                            "type": "paper_monitor_summary",
                            "ts": "2026-05-09T00:00:06Z",
                            "snapshot_count": 2,
                            "opportunity_count": 1,
                        },
                    ]
                )
                + "\n"
            )
            snapshots.write_text(
                json.dumps(
                    {
                        "ts": "2026-05-09T00:00:00Z",
                        "type": "binary_snapshot",
                        "venue": "polymarket",
                        "market_id": "m1",
                        "fee_rate": 0.03,
                        "yes": {"token_id": "yes-token", "asks": [[0.004, 100]], "bids": []},
                        "no": {"token_id": "no-token", "asks": [[0.997, 100]], "bids": []},
                    }
                )
                + "\n"
            )
            rules.write_text("{}")
            gamma.write_text("")

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = main(
                    [
                        "paper-analyze",
                        str(report),
                        "--out",
                        str(out),
                        "--top",
                        "1",
                        "--snapshots",
                        str(snapshots),
                        "--rules",
                        str(rules),
                        "--gamma",
                        str(gamma),
                        "--near-miss-top",
                        "1",
                        "--near-miss-min-net-edge",
                        "0.002",
                    ]
                )
            row = json.loads(out.read_text())

        self.assertEqual(code, 0)
        self.assertEqual(row["type"], "monitor_analysis")
        self.assertEqual(row["monitor_kind"], "paper")
        self.assertEqual(row["iteration_count"], 1)
        self.assertEqual(row["error_iteration_count"], 1)
        self.assertEqual(row["current_opportunity_observations"], 1)
        self.assertAlmostEqual(row["stable_paper_roi"], 0.02)
        self.assertEqual(row["top_stable_markets"][0]["market_id"], "m1")
        self.assertEqual(row["error_summary"]["by_phase"][0]["phase"], "collect")
        self.assertEqual(row["zero_current_opportunity_iterations"], 0)
        self.assertEqual(row["latest_zero_stable_opportunity_streak"], 0)
        self.assertEqual(row["current_opportunity_by_kind"][0]["kind"], "yes_no_bundle")
        self.assertEqual(row["near_miss"]["top"][0]["kind"], "yes_no_bundle")
        self.assertEqual(row["near_miss"]["gamma_path"], str(gamma))
        self.assertEqual(row["near_miss_rejection_summary"]["neg_risk_group_count"], 0)
        self.assertGreater(row["near_miss"]["top"][0]["distance_to_min_net_edge"], 0)
        self.assertIn("wrote=1", stdout.getvalue())

    def test_monitor_analyze_command_summarizes_realtime_health(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "realtime.jsonl"
            out = Path(tmp) / "analysis.json"
            report.write_text(
                "\n".join(
                    json.dumps(row)
                    for row in [
                        {
                            "type": "realtime_monitor_connection_event",
                            "ts": "2026-05-09T00:00:00Z",
                            "event": "connected",
                            "connection_count": 1,
                            "reconnect_count": 0,
                        },
                        {
                            "type": "realtime_monitor_iteration",
                            "ts": "2026-05-09T00:00:01Z",
                            "messages_seen": 10,
                            "known_token_count": 50,
                            "last_message_age_seconds": 0.5,
                            "snapshots_collected": 25,
                            "snapshot_count": 25,
                            "current_opportunity_count": 0,
                            "stable_opportunity_count": 0,
                            "stable_paper_trade_count": 0,
                        },
                        {
                            "type": "realtime_monitor_iteration",
                            "ts": "2026-05-09T00:00:03Z",
                            "messages_seen": 15,
                            "known_token_count": 50,
                            "last_message_age_seconds": 1.5,
                            "snapshots_collected": 25,
                            "snapshot_count": 50,
                            "current_opportunity_count": 0,
                            "stable_opportunity_count": 0,
                            "stable_paper_trade_count": 0,
                        },
                    ]
                )
                + "\n"
            )

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = main(["monitor-analyze", str(report), "--out", str(out)])
            row = json.loads(out.read_text())

        self.assertEqual(code, 0)
        self.assertEqual(row["monitor_kind"], "realtime")
        self.assertEqual(row["iteration_count"], 2)
        self.assertEqual(row["final_known_token_count"], 50)
        self.assertEqual(row["messages_per_iteration"]["max"], 5)
        self.assertEqual(row["connection_events"]["by_event"][0]["event"], "connected")
        self.assertIn("wrote=1", stdout.getvalue())

    def test_paper_report_command_writes_json_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.ndjson"
            out = Path(tmp) / "report.json"
            path.write_text(
                json.dumps(
                    {
                        "ts": "2026-05-09T00:00:00Z",
                        "type": "binary_snapshot",
                        "venue": "polymarket",
                        "market_id": "sample",
                        "fee_rate": 0.0,
                        "yes": {"token_id": "yes-token", "asks": [[0.45, 100]], "bids": []},
                        "no": {"token_id": "no-token", "asks": [[0.53, 100]], "bids": []},
                    }
                )
                + "\n"
            )

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = main(["paper-report", str(path), "--out", str(out), "--max-capital-per-trade", "9.80"])
            row = json.loads(out.read_text())

        self.assertEqual(code, 0)
        self.assertEqual(row["type"], "paper_report")
        self.assertEqual(row["paper_trade_count"], 1)
        self.assertEqual(row["by_kind"][0]["kind"], "yes_no_bundle")
        self.assertAlmostEqual(row["paper_capital_used"], 9.8)
        self.assertIn("wrote=1", stdout.getvalue())

    def test_execute_latest_command_writes_dry_run_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.ndjson"
            out = Path(tmp) / "plans.ndjson"
            path.write_text(
                json.dumps(
                    {
                        "ts": "2026-05-09T00:00:00Z",
                        "type": "binary_snapshot",
                        "venue": "polymarket",
                        "market_id": "sample",
                        "fee_rate": 0.0,
                        "yes": {"token_id": "yes-token", "asks": [[0.45, 100]], "bids": []},
                        "no": {"token_id": "no-token", "asks": [[0.53, 100]], "bids": []},
                    }
                )
                + "\n"
            )

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = main(
                    [
                        "execute-latest",
                        str(path),
                        "--out",
                        str(out),
                        "--max-capital-per-trade",
                        "9.80",
                        "--slippage-bps",
                        "50",
                    ]
                )
            rows = [json.loads(line) for line in out.read_text().splitlines()]

        self.assertEqual(code, 0)
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]["dry_run"])
        self.assertTrue(rows[0]["pretrade_check"]["passed"])
        self.assertEqual([order["token_id"] for order in rows[0]["orders"]], ["yes-token", "no-token"])
        self.assertIn("wrote=1", stdout.getvalue())

    def test_execute_latest_can_require_pretrade_check_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.ndjson"
            out = Path(tmp) / "plans.ndjson"
            path.write_text(
                json.dumps(
                    {
                        "ts": "2026-05-09T00:00:00Z",
                        "type": "binary_snapshot",
                        "venue": "polymarket",
                        "market_id": "sample",
                        "fee_rate": 0.0,
                        "yes": {"token_id": "yes-token", "asks": [[0.45, 100]], "bids": []},
                        "no": {"token_id": "no-token", "asks": [[0.53, 100]], "bids": []},
                    }
                )
                + "\n"
            )

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = main(
                    [
                        "execute-latest",
                        str(path),
                        "--out",
                        str(out),
                        "--max-capital-per-trade",
                        "9.80",
                        "--max-leg-count",
                        "1",
                        "--require-pretrade-pass",
                    ]
                )
            plan_text = out.read_text()

        self.assertEqual(code, 0)
        self.assertEqual(plan_text, "")
        self.assertIn("wrote=0", stdout.getvalue())

    def test_execute_latest_can_plan_neg_risk_group_with_gamma(self):
        with tempfile.TemporaryDirectory() as tmp:
            snapshots = Path(tmp) / "snapshots.ndjson"
            gamma = Path(tmp) / "gamma.ndjson"
            out = Path(tmp) / "plans.ndjson"
            snapshots.write_text(
                "\n".join(
                    json.dumps(
                        {
                            "ts": "2026-05-09T00:00:00Z",
                            "type": "binary_snapshot",
                            "venue": "polymarket",
                            "market_id": market_id,
                            "fee_rate": 0.0,
                            "yes": {"token_id": f"{market_id}-yes", "asks": [[yes_price, 100]], "bids": []},
                            "no": {"token_id": f"{market_id}-no", "asks": [[0.70, 100]], "bids": []},
                        }
                    )
                    for market_id, yes_price in [("a", 0.40), ("b", 0.50)]
                )
                + "\n"
            )
            gamma.write_text(
                "\n".join(
                    json.dumps(
                        {
                            "type": "raw_polymarket_gamma_market",
                            "market_id": market_id,
                            "raw": {
                                "id": market_id,
                                "question": f"{market_id} wins?",
                                "closed": False,
                                "enableOrderBook": True,
                                "acceptingOrders": True,
                                "outcomes": json.dumps(["Yes", "No"]),
                                "clobTokenIds": json.dumps([f"{market_id}-yes", f"{market_id}-no"]),
                                "negRiskMarketID": "group-1",
                            },
                        }
                    )
                    for market_id in ["a", "b"]
                )
                + "\n"
            )

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = main(
                    [
                        "execute-latest",
                        str(snapshots),
                        "--gamma",
                        str(gamma),
                        "--out",
                        str(out),
                        "--max-capital-per-trade",
                        "9",
                    ]
                )
            row = json.loads(out.read_text().splitlines()[0])

        self.assertEqual(code, 0)
        self.assertEqual(row["opportunity_kind"], "neg_risk_group_yes_basket")
        self.assertTrue(row["pretrade_check"]["passed"])
        self.assertIn("wrote=1", stdout.getvalue())

    def test_execute_latest_can_require_stable_run_observations(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.ndjson"
            out = Path(tmp) / "plans.ndjson"
            path.write_text(
                json.dumps(
                    {
                        "ts": "2026-05-09T00:00:00Z",
                        "type": "binary_snapshot",
                        "venue": "polymarket",
                        "market_id": "sample",
                        "fee_rate": 0.0,
                        "yes": {"token_id": "yes-token", "asks": [[0.45, 100]], "bids": []},
                        "no": {"token_id": "no-token", "asks": [[0.53, 100]], "bids": []},
                    }
                )
                + "\n"
            )

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = main(
                    [
                        "execute-latest",
                        str(path),
                        "--out",
                        str(out),
                        "--max-capital-per-trade",
                        "9.80",
                        "--min-run-observations",
                        "2",
                    ]
                )
            plan_text = out.read_text()

        self.assertEqual(code, 0)
        self.assertEqual(plan_text, "")
        self.assertIn("wrote=0", stdout.getvalue())

    def test_execute_rules_once_refreshes_before_planning(self):
        def collect_once(path, gamma, rules, timeout, proxy, max_workers, **kwargs):
            path.write_text(
                json.dumps(
                    {
                        "ts": "2026-05-09T00:00:00Z",
                        "type": "binary_snapshot",
                        "venue": "polymarket",
                        "market_id": "sample",
                        "fee_rate": 0.0,
                        "yes": {"token_id": "yes-token", "asks": [[0.45, 100]], "bids": []},
                        "no": {"token_id": "no-token", "asks": [[0.53, 100]], "bids": []},
                    }
                )
                + "\n"
            )
            return 1

        with tempfile.TemporaryDirectory() as tmp:
            gamma = Path(tmp) / "gamma.ndjson"
            rules = Path(tmp) / "rules.json"
            snapshots = Path(tmp) / "fresh.ndjson"
            out = Path(tmp) / "plans.ndjson"
            gamma.write_text("")
            rules.write_text("{}")

            with patch("poly_strategy.cli.collect_polymarket_binary_snapshots_for_rules", side_effect=collect_once) as collect:
                stdout = io.StringIO()
                with redirect_stdout(stdout):
                    code = main(
                        [
                            "execute-rules-once",
                            "--gamma",
                            str(gamma),
                            "--rules",
                            str(rules),
                            "--snapshots-out",
                            str(snapshots),
                            "--out",
                            str(out),
                            "--max-capital-per-trade",
                            "9.80",
                            "--book-workers",
                            "4",
                        ]
                    )
            rows = [json.loads(line) for line in out.read_text().splitlines()]

        self.assertEqual(code, 0)
        collect.assert_called_once()
        self.assertEqual(collect.call_args.args[5], 4)
        self.assertTrue(collect.call_args.kwargs["expand_neg_risk_groups"])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["orders"][0]["token_id"], "yes-token")
        self.assertIn("snapshots=1 plans=1", stdout.getvalue())

    def test_execute_alerts_refreshes_alert_markets_before_planning(self):
        def collect_once(path, gamma, market_ids, timeout, proxy, max_workers, **kwargs):
            self.assertEqual(market_ids, ["sample"])
            path.write_text(
                json.dumps(
                    {
                        "ts": "2026-05-09T00:00:00Z",
                        "type": "binary_snapshot",
                        "venue": "polymarket",
                        "market_id": "sample",
                        "fee_rate": 0.0,
                        "yes": {"token_id": "yes-token", "asks": [[0.45, 100]], "bids": []},
                        "no": {"token_id": "no-token", "asks": [[0.53, 100]], "bids": []},
                    }
                )
                + "\n"
            )
            return 1

        with tempfile.TemporaryDirectory() as tmp:
            alerts = Path(tmp) / "alerts.ndjson"
            gamma = Path(tmp) / "gamma.ndjson"
            rules = Path(tmp) / "rules.json"
            snapshots = Path(tmp) / "fresh.ndjson"
            out = Path(tmp) / "plans.ndjson"
            alerts.write_text(json.dumps({"type": "opportunity_alert", "market_ids": ["sample"]}) + "\n")
            gamma.write_text("")
            rules.write_text("{}")

            with patch("poly_strategy.cli.collect_polymarket_binary_snapshots_for_market_ids", side_effect=collect_once) as collect:
                stdout = io.StringIO()
                with redirect_stdout(stdout):
                    code = main(
                        [
                            "execute-alerts",
                            str(alerts),
                            "--gamma",
                            str(gamma),
                            "--rules",
                            str(rules),
                            "--snapshots-out",
                            str(snapshots),
                            "--out",
                            str(out),
                            "--max-capital-per-trade",
                            "9.80",
                            "--require-pretrade-pass",
                        ]
                    )
            rows = [json.loads(line) for line in out.read_text().splitlines()]

        self.assertEqual(code, 0)
        collect.assert_called_once()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["source_alert_market_ids"], ["sample"])
        self.assertTrue(rows[0]["pretrade_check"]["passed"])
        self.assertIn("snapshots=1 plans=1", stdout.getvalue())

    def test_notify_alerts_command_writes_dry_run_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            alerts = Path(tmp) / "alerts.ndjson"
            out = Path(tmp) / "notify.ndjson"
            alerts.write_text(
                json.dumps(
                    {
                        "type": "opportunity_alert",
                        "alert_kind": "stable_paper_trade",
                        "key": "a",
                        "kind": "yes_no_bundle",
                        "market_ids": ["m1"],
                        "net_edge_per_share": 0.02,
                    }
                )
                + "\n"
            )

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = main(
                    [
                        "notify-alerts",
                        str(alerts),
                        "--webhook-url",
                        "https://example.test/hook",
                        "--dry-run",
                        "--out",
                        str(out),
                    ]
                )
            rows = [json.loads(line) for line in out.read_text().splitlines()]

        self.assertEqual(code, 0)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["channel"], "webhook")
        self.assertEqual(rows[0]["status"], "dry_run")
        self.assertIn("wrote=1", stdout.getvalue())

    def test_risk_check_plans_command_filters_failed_plans(self):
        with tempfile.TemporaryDirectory() as tmp:
            plans = Path(tmp) / "plans.ndjson"
            out = Path(tmp) / "checked.ndjson"
            plans.write_text(
                json.dumps(
                    {
                        "type": "execution_plan",
                        "dry_run": True,
                        "orders": [{"price": 0.9, "size": 10}],
                    }
                )
                + "\n"
            )

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = main(
                    [
                        "risk-check-plans",
                        str(plans),
                        "--out",
                        str(out),
                        "--max-trade-notional",
                        "5",
                        "--require-risk-pass",
                    ]
                )
            out_text = out.read_text()

        self.assertEqual(code, 0)
        self.assertEqual(out_text, "")
        self.assertIn("wrote=0", stdout.getvalue())

    def test_match_cross_platform_command_writes_report_and_signals(self):
        with tempfile.TemporaryDirectory() as tmp:
            poly = Path(tmp) / "poly.ndjson"
            kalshi = Path(tmp) / "kalshi.ndjson"
            out = Path(tmp) / "matches.json"
            signals = Path(tmp) / "signals.ndjson"
            poly.write_text(
                json.dumps(
                    {
                        "type": "raw_polymarket_gamma_market",
                        "market_id": "pm1",
                        "raw": {"id": "pm1", "question": "Will Bitcoin hit 100k in 2026?"},
                    }
                )
                + "\n"
            )
            kalshi.write_text(
                json.dumps(
                    {
                        "type": "raw_kalshi_market",
                        "market_id": "KXBTC100K",
                        "raw": {"ticker": "KXBTC100K", "title": "Will Bitcoin hit 100k in 2026?"},
                    }
                )
                + "\n"
            )

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = main(
                    [
                        "match-cross-platform",
                        "--polymarket-gamma",
                        str(poly),
                        "--kalshi-markets",
                        str(kalshi),
                        "--out",
                        str(out),
                        "--signals-out",
                        str(signals),
                        "--min-score",
                        "0.5",
                    ]
                )
            row = json.loads(out.read_text())
            signal_rows = [json.loads(line) for line in signals.read_text().splitlines()]

        self.assertEqual(code, 0)
        self.assertEqual(row["match_count"], 1)
        self.assertEqual(row["signals_written"], 1)
        self.assertEqual(signal_rows[0]["type"], "external_signal")
        self.assertIn("wrote=1", stdout.getvalue())

    def test_discover_rules_command_uses_openai_client_and_prints_summary(self):
        result = SimpleNamespace(
            markets_read=2,
            candidates_found=1,
            implications_written=1,
            mutual_exclusions_written=2,
            equivalents_written=3,
            collectively_exhaustive_written=4,
            complements_written=5,
        )
        with patch("poly_strategy.cli.OpenAIRuleDiscoveryClient") as client_cls:
            with patch("poly_strategy.cli.discover_rules", return_value=result) as discover:
                stdout = io.StringIO()
                with patch.dict("os.environ", {"OPENAI_MODEL": "test-model", "OPENAI_API_KEY": "test-key"}, clear=True):
                    with redirect_stdout(stdout):
                        code = main(
                            [
                                "discover-rules",
                                "--raw",
                                "data/gamma.ndjson",
                                "--out",
                                "rules/candidate-implications.json",
                            ]
                        )

        self.assertEqual(code, 0)
        client_cls.assert_called_once()
        self.assertEqual(client_cls.call_args.kwargs["model"], "test-model")
        self.assertEqual(client_cls.call_args.kwargs["retries"], 2)
        self.assertEqual(client_cls.call_args.kwargs["max_output_tokens"], 4000)
        discover.assert_called_once()
        self.assertEqual(discover.call_args.kwargs["context_market_limit"], 40)
        self.assertEqual(str(discover.call_args.args[0]), "data/gamma.ndjson")
        self.assertEqual(str(discover.call_args.args[1]), "rules/candidate-implications.json")
        self.assertIn("markets=2", stdout.getvalue())
        self.assertIn("implications=1", stdout.getvalue())
        self.assertIn("mutual_exclusions=2", stdout.getvalue())
        self.assertIn("equivalents=3", stdout.getvalue())
        self.assertIn("collectively_exhaustive=4", stdout.getvalue())
        self.assertIn("complements=5", stdout.getvalue())

    def test_external_signal_commands_ingest_and_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "signals.ndjson"
            out = Path(tmp) / "external.ndjson"
            report = Path(tmp) / "report.json"
            source.write_text(
                json.dumps(
                    {
                        "id": "sig-1",
                        "kind": "cross_platform",
                        "legs": [
                            {"venue": "polymarket", "market_id": "poly-1", "token": "YES"},
                            {"venue": "kalshi", "market_id": "kalshi-1", "token": "NO"},
                        ],
                    }
                )
                + "\n"
            )

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                ingest_code = main(
                    [
                        "ingest-external-signals",
                        "--source",
                        "oddpool",
                        "--input",
                        str(source),
                        "--out",
                        str(out),
                    ]
                )
                report_code = main(["external-signal-report", str(out), "--out", str(report)])
            row = json.loads(report.read_text())

        self.assertEqual(ingest_code, 0)
        self.assertEqual(report_code, 0)
        self.assertEqual(row["signal_count"], 1)
        self.assertEqual(row["by_source"][0]["source"], "oddpool")
        self.assertIn("wrote=1", stdout.getvalue())

    def test_build_watchlist_command_writes_token_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            gamma = Path(tmp) / "gamma.ndjson"
            rules = Path(tmp) / "rules.json"
            out = Path(tmp) / "watchlist.json"
            gamma.write_text(
                json.dumps(
                    {
                        "type": "raw_polymarket_gamma_market",
                        "market_id": "a",
                        "raw": {
                            "id": "a",
                            "question": "A?",
                            "clobTokenIds": json.dumps(["a-yes", "a-no"]),
                        },
                    }
                )
                + "\n"
            )
            rules.write_text(json.dumps({"mutually_exclusive": [{"first": "a", "second": "a"}]}))

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = main(["build-watchlist", "--gamma", str(gamma), "--rules", str(rules), "--out", str(out)])
            row = json.loads(out.read_text())

        self.assertEqual(code, 0)
        self.assertEqual(row["markets"][0]["yes_token_id"], "a-yes")
        self.assertIn("wrote=1", stdout.getvalue())

    def test_stream_polymarket_watchlist_command_invokes_streamer(self):
        with tempfile.TemporaryDirectory() as tmp:
            watchlist = Path(tmp) / "watchlist.json"
            updates = Path(tmp) / "updates.ndjson"
            snapshots = Path(tmp) / "snapshots.ndjson"
            watchlist.write_text(json.dumps({"type": "polymarket_watchlist", "markets": []}))

            stdout = io.StringIO()
            with patch("poly_strategy.cli.stream_polymarket_watchlist", return_value=2) as stream:
                with redirect_stdout(stdout):
                    code = main(
                        [
                            "stream-polymarket-watchlist",
                            "--watchlist",
                            str(watchlist),
                            "--out",
                            str(updates),
                            "--snapshots-out",
                            str(snapshots),
                            "--snapshot-interval",
                            "3",
                            "--max-messages",
                            "2",
                            "--url",
                            "wss://example.test/ws",
                        ]
                    )

        self.assertEqual(code, 0)
        stream.assert_called_once_with(
            watchlist,
            updates,
            snapshot_out_path=snapshots,
            max_messages=2,
            snapshot_interval_seconds=3.0,
            url="wss://example.test/ws",
        )
        self.assertIn("messages=2", stdout.getvalue())

    def test_realtime_monitor_watchlist_command_invokes_monitor(self):
        summary = {
            "messages_seen": 5,
            "iterations_completed": 2,
            "snapshots_collected": 4,
            "opportunity_count": 1,
            "paper_edge": 0.12,
        }
        with tempfile.TemporaryDirectory() as tmp:
            watchlist = Path(tmp) / "watchlist.json"
            rules = Path(tmp) / "rules.json"
            gamma = Path(tmp) / "gamma.ndjson"
            report = Path(tmp) / "report.jsonl"
            updates = Path(tmp) / "updates.ndjson"
            snapshots = Path(tmp) / "snapshots.ndjson"

            stdout = io.StringIO()
            with patch("poly_strategy.cli.monitor_polymarket_watchlist", return_value=summary) as monitor:
                with redirect_stdout(stdout):
                    code = main(
                        [
                            "realtime-monitor-watchlist",
                            "--watchlist",
                            str(watchlist),
                            "--rules",
                            str(rules),
                            "--gamma",
                            str(gamma),
                            "--report-out",
                            str(report),
                            "--updates-out",
                            str(updates),
                            "--snapshots-out",
                            str(snapshots),
                            "--snapshot-interval",
                            "2",
                            "--stale-timeout",
                            "30",
                            "--reconnect-delay",
                            "1",
                            "--max-reconnects",
                            "3",
                            "--max-messages",
                            "5",
                            "--max-iterations",
                            "2",
                            "--min-net-edge",
                            "0.002",
                            "--max-capital-per-trade",
                            "20",
                            "--bankroll",
                            "100",
                            "--min-paper-roi",
                            "0.01",
                            "--min-run-observations",
                            "2",
                            "--min-run-seconds",
                            "3",
                            "--max-opportunities-per-iteration",
                            "5",
                            "--url",
                            "wss://example.test/ws",
                        ]
                    )

        self.assertEqual(code, 0)
        monitor.assert_called_once()
        kwargs = monitor.call_args.kwargs
        self.assertEqual(monitor.call_args.args[0], watchlist)
        self.assertEqual(monitor.call_args.args[1], report)
        self.assertEqual(kwargs["rules_path"], rules)
        self.assertEqual(kwargs["gamma_path"], gamma)
        self.assertEqual(kwargs["updates_out_path"], updates)
        self.assertEqual(kwargs["snapshots_out_path"], snapshots)
        self.assertEqual(kwargs["max_messages"], 5)
        self.assertEqual(kwargs["max_iterations"], 2)
        self.assertEqual(kwargs["snapshot_interval_seconds"], 2.0)
        self.assertEqual(kwargs["stale_timeout_seconds"], 30.0)
        self.assertEqual(kwargs["reconnect_delay_seconds"], 1.0)
        self.assertEqual(kwargs["max_reconnects"], 3)
        self.assertEqual(kwargs["min_net_edge"], 0.002)
        self.assertEqual(kwargs["min_paper_roi"], 0.01)
        self.assertEqual(kwargs["min_run_observations"], 2)
        self.assertEqual(kwargs["min_run_seconds"], 3.0)
        self.assertEqual(kwargs["max_opportunities_per_iteration"], 5)
        self.assertIn("iterations=2", stdout.getvalue())

    def test_monitor_alerts_command_writes_latest_alerts(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "report.jsonl"
            out = Path(tmp) / "alerts.ndjson"
            state = Path(tmp) / "alerts-state.json"
            report.write_text(
                json.dumps(
                    {
                        "type": "realtime_monitor_iteration",
                        "iteration": 1,
                        "stable_paper_trades": [
                            {
                                "key": "arb-1",
                                "kind": "yes_no_bundle",
                                "paper_roi": 0.03,
                                "paper_edge": 0.2,
                                "net_edge_per_share": 0.02,
                                "total_edge": 0.2,
                                "legs": [{"market_id": "m1"}],
                            }
                        ],
                    }
                )
                + "\n"
            )

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = main(
                    [
                        "monitor-alerts",
                        str(report),
                        "--out",
                        str(out),
                        "--min-paper-roi",
                        "0.01",
                        "--state",
                        str(state),
                        "--cooldown-seconds",
                        "60",
                    ]
                )
            rows = [json.loads(line) for line in out.read_text().splitlines()]
            state_exists = state.exists()

        self.assertEqual(code, 0)
        self.assertEqual(rows[0]["type"], "opportunity_alert")
        self.assertEqual(rows[0]["key"], "arb-1")
        self.assertTrue(state_exists)
        self.assertIn("wrote=1", stdout.getvalue())

    def test_discover_rules_command_requires_model(self):
        stderr = io.StringIO()
        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}, clear=True):
            with patch("sys.stderr", stderr):
                code = main(
                    [
                        "discover-rules",
                        "--raw",
                        "data/gamma.ndjson",
                        "--out",
                        "rules/candidate-implications.json",
                    ]
                )

        self.assertEqual(code, 1)
        self.assertIn("model is required", stderr.getvalue())

    def test_discover_rules_command_allows_cache_only_without_model(self):
        result = SimpleNamespace(
            markets_read=2,
            candidates_found=1,
            implications_written=1,
            mutual_exclusions_written=0,
            equivalents_written=0,
            collectively_exhaustive_written=0,
            complements_written=0,
        )
        with patch("poly_strategy.cli.OpenAIRuleDiscoveryClient") as client_cls:
            with patch("poly_strategy.cli.discover_rules", return_value=result) as discover:
                stdout = io.StringIO()
                with patch.dict("os.environ", {}, clear=True):
                    with redirect_stdout(stdout):
                        code = main(
                            [
                                "discover-rules",
                                "--raw",
                                "data/gamma.ndjson",
                                "--out",
                                "rules/candidate-implications.json",
                                "--cache",
                                "rules/candidate-implications.json",
                            ]
                        )

        self.assertEqual(code, 0)
        client_cls.assert_not_called()
        self.assertIsNone(discover.call_args.args[2])
        self.assertIn("markets=2", stdout.getvalue())

    def test_verify_exhaustive_groups_command_uses_openai_client_and_writes_report(self):
        result = SimpleNamespace(
            candidates_found=2,
            verified_count=1,
            added_count=1,
            rejected_count=1,
            skipped_existing_count=0,
            out_path=Path("rules/out.json"),
            rows=[],
        )
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "verification.json"
            with patch("poly_strategy.cli.OpenAIExhaustiveGroupVerifierClient") as client_cls:
                with patch("poly_strategy.cli.promote_exhaustive_groups", return_value=result) as promote:
                    stdout = io.StringIO()
                    with patch.dict("os.environ", {"OPENAI_MODEL": "gpt-5.5", "OPENAI_API_KEY": "test-key"}, clear=True):
                        with redirect_stdout(stdout):
                            code = main(
                                [
                                    "verify-exhaustive-groups",
                                    "--gamma",
                                    "data/gamma.ndjson",
                                    "--rules-in",
                                    "rules/in.json",
                                    "--rules-out",
                                    "rules/out.json",
                                    "--snapshots",
                                    "data/snapshots.ndjson",
                                    "--report-out",
                                    str(report),
                                    "--top",
                                    "3",
                                    "--min-net-edge",
                                    "0.01",
                                ]
                            )

            report_row = json.loads(report.read_text())

        self.assertEqual(code, 0)
        client_cls.assert_called_once()
        self.assertEqual(client_cls.call_args.kwargs["model"], "gpt-5.5")
        promote.assert_called_once()
        self.assertEqual(str(promote.call_args.args[0]), "data/gamma.ndjson")
        self.assertEqual(str(promote.call_args.args[1]), "rules/in.json")
        self.assertEqual(str(promote.call_args.args[2]), "rules/out.json")
        self.assertEqual(str(promote.call_args.args[3]), "data/snapshots.ndjson")
        self.assertEqual(promote.call_args.kwargs["top_n"], 3)
        self.assertEqual(promote.call_args.kwargs["min_net_edge"], 0.01)
        self.assertEqual(report_row["type"], "exhaustive_group_promotion")
        self.assertIn("added=1", stdout.getvalue())

    def test_verify_exhaustive_groups_command_requires_model(self):
        stderr = io.StringIO()
        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}, clear=True):
            with patch("sys.stderr", stderr):
                code = main(
                    [
                        "verify-exhaustive-groups",
                        "--gamma",
                        "data/gamma.ndjson",
                        "--rules-in",
                        "rules/in.json",
                        "--rules-out",
                        "rules/out.json",
                        "--snapshots",
                        "data/snapshots.ndjson",
                    ]
                )

        self.assertEqual(code, 1)
        self.assertIn("model is required", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
