import io
import json
from types import SimpleNamespace
import tempfile
import unittest
from contextlib import redirect_stdout
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
                        ]
                    )

        self.assertEqual(code, 0)
        collect.assert_called_once()
        replay.assert_called_once()
        self.assertEqual(replay.call_args.kwargs["min_net_edge"], 0.002)
        self.assertEqual(replay.call_args.kwargs["max_capital_per_trade"], 20.0)
        self.assertIn("opportunities=1", stdout.getvalue())

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


if __name__ == "__main__":
    unittest.main()
