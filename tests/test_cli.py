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
        self.assertEqual(row["type"], "paper_monitor_analysis")
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
        self.assertEqual([order["token_id"] for order in rows[0]["orders"]], ["yes-token", "no-token"])
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
