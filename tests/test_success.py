import json
import tempfile
import unittest
from pathlib import Path

from poly_strategy.success import success_status_report, write_success_status


class SuccessStatusTests(unittest.TestCase):
    def test_success_status_prefers_dry_run_execution_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            monitor = Path(tmp) / "monitor.jsonl"
            plans = Path(tmp) / "plans.ndjson"
            maker = Path(tmp) / "maker.json"
            monitor.write_text(
                json.dumps(
                    {
                        "type": "realtime_monitor_iteration",
                        "stable_paper_trade_count": 1,
                        "stable_paper_edge": 0.1,
                    }
                )
                + "\n"
            )
            plans.write_text(
                json.dumps(
                    {
                        "type": "execution_plan",
                        "dry_run": True,
                        "orders": [{"token_id": "yes"}],
                        "pretrade_check": {"passed": True},
                        "risk_check": {"passed": True},
                    }
                )
                + "\n"
            )
            maker.write_text(json.dumps({"status": "positive_ev_config_found", "ranked_configs": []}) + "\n")

            report = success_status_report(monitor, plans, maker, generated_at="2026-05-10T00:00:00Z")

        self.assertEqual(report["status"], "dry_run_executable")
        self.assertTrue(report["dry_run_executable"])
        self.assertEqual(report["execution_plans"]["dry_run_passed_count"], 1)

    def test_success_status_reports_no_success_for_negative_maker(self):
        with tempfile.TemporaryDirectory() as tmp:
            maker = Path(tmp) / "maker.json"
            maker.write_text(json.dumps({"status": "no_positive_ev_config", "ranked_configs": []}) + "\n")

            report = success_status_report(maker_adaptive_path=maker)

        self.assertEqual(report["status"], "no_success")
        self.assertFalse(report["paper_success_candidate"])

    def test_success_status_reports_maker_hedge_positive_ev(self):
        with tempfile.TemporaryDirectory() as tmp:
            hedge = Path(tmp) / "maker-hedge.json"
            hedge.write_text(
                json.dumps(
                    {
                        "status": "positive_ev_hedge_found",
                        "batch_count": 10,
                        "candidate_observation_count": 5,
                        "completed_count": 1,
                        "unsafe_fill_count": 0,
                        "completed_realized_edge_at_cap": 0.25,
                        "max_completed_realized_edge_at_cap": 0.25,
                        "top_completed": [{"realized_edge_at_cap": 0.25}],
                    }
                )
                + "\n"
            )

            report = success_status_report(maker_hedge_path=hedge)

        self.assertEqual(report["status"], "maker_hedge_positive_ev")
        self.assertTrue(report["paper_success_candidate"])
        self.assertEqual(report["maker_hedge"]["completed_count"], 1)

    def test_success_status_reports_maker_hybrid_positive_ev(self):
        with tempfile.TemporaryDirectory() as tmp:
            hybrid = Path(tmp) / "maker-hybrid.json"
            hybrid.write_text(
                json.dumps(
                    {
                        "status": "positive_ev_hybrid_found",
                        "batch_count": 10,
                        "candidate_observation_count": 5,
                        "completed_count": 1,
                        "unsafe_fill_count": 0,
                        "partial_maker_fill_count": 0,
                        "completed_realized_edge_at_cap": 0.35,
                        "max_completed_realized_edge_at_cap": 0.35,
                        "top_completed": [{"realized_edge_at_cap": 0.35}],
                    }
                )
                + "\n"
            )

            report = success_status_report(maker_hybrid_path=hybrid)

        self.assertEqual(report["status"], "maker_hybrid_positive_ev")
        self.assertTrue(report["paper_success_candidate"])
        self.assertEqual(report["maker_hybrid"]["completed_count"], 1)

    def test_success_status_ignores_diagnostic_touch_bid_hybrid(self):
        with tempfile.TemporaryDirectory() as tmp:
            hybrid = Path(tmp) / "maker-hybrid-touch.json"
            hybrid.write_text(
                json.dumps(
                    {
                        "status": "positive_ev_hybrid_found",
                        "fill_model": "touch_bid",
                        "completed_count": 1,
                        "completed_realized_edge_at_cap": 0.35,
                        "top_completed": [{"realized_edge_at_cap": 0.35}],
                    }
                )
                + "\n"
            )

            report = success_status_report(maker_hybrid_path=hybrid)

        self.assertEqual(report["status"], "no_success")
        self.assertFalse(report["paper_success_candidate"])
        self.assertEqual(report["maker_hybrid"]["fill_model"], "touch_bid")

    def test_success_status_reports_maker_hybrid_tape_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            tape = Path(tmp) / "maker-hybrid-tape.json"
            tape.write_text(
                json.dumps(
                    {
                        "status": "tape_positive_ev_candidate_found",
                        "fill_model": "trade_tape_sell_through",
                        "diagnostic_only": True,
                        "batch_count": 10,
                        "trade_count": 100,
                        "candidate_observation_count": 5,
                        "completed_count": 3,
                        "unique_completed_count": 1,
                        "unique_completed_realized_edge_at_cap": 0.21,
                        "top_unique_completed": [{"realized_edge_at_cap": 0.21}],
                    }
                )
                + "\n"
            )

            report = success_status_report(maker_hybrid_tape_path=tape)

        self.assertEqual(report["status"], "maker_hybrid_tape_positive_ev_candidate")
        self.assertTrue(report["paper_success_candidate"])
        self.assertTrue(report["maker_hybrid_tape"]["diagnostic_only"])
        self.assertEqual(report["maker_hybrid_tape"]["unique_completed_count"], 1)

    def test_success_status_requires_min_tape_edge_for_actionable_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            tape = Path(tmp) / "maker-hybrid-tape.json"
            tape.write_text(
                json.dumps(
                    {
                        "status": "tape_positive_ev_candidate_found",
                        "unique_completed_count": 1,
                        "unique_completed_realized_edge_at_cap": 0.02,
                        "top_unique_completed": [{"realized_edge_at_cap": 0.02}],
                    }
                )
                + "\n"
            )

            report = success_status_report(
                maker_hybrid_tape_path=tape,
                min_maker_hybrid_tape_edge_at_cap=0.25,
            )

        self.assertEqual(report["status"], "no_success")
        self.assertFalse(report["paper_success_candidate"])
        self.assertEqual(report["maker_hybrid_tape"]["actionable_unique_completed_count"], 0)

    def test_success_status_reports_cross_platform_paper_opportunity(self):
        with tempfile.TemporaryDirectory() as tmp:
            scan = Path(tmp) / "cross.json"
            scan.write_text(
                json.dumps(
                    {
                        "type": "cross_platform_scan_report",
                        "pair_count": 1,
                        "opportunity_count": 1,
                        "opportunities": [
                            {
                                "net_edge_per_share": 0.001,
                                "total_edge": 6.0,
                                "capital_capped": {"edge": 0.1},
                                "pair": {
                                    "trade_allowed": True,
                                    "status": "verified_same_binary_event",
                                    "llm_verification": {"trade_allowed": True, "risk_flags": []},
                                },
                            }
                        ],
                    }
                )
                + "\n"
            )

            report = success_status_report(cross_platform_scan_path=scan)

        self.assertEqual(report["status"], "cross_platform_paper_opportunity")
        self.assertTrue(report["paper_success_candidate"])
        self.assertEqual(report["cross_platform"]["verified_positive_count"], 1)
        self.assertEqual(report["cross_platform"]["actionable_verified_positive_count"], 1)
        self.assertEqual(report["cross_platform"]["top_capital_capped_edge"], 0.1)

    def test_success_status_ignores_cross_platform_below_actionable_edge(self):
        with tempfile.TemporaryDirectory() as tmp:
            scan = Path(tmp) / "cross.json"
            scan.write_text(
                json.dumps(
                    {
                        "type": "cross_platform_scan_report",
                        "pair_count": 1,
                        "opportunity_count": 1,
                        "opportunities": [
                            {
                                "net_edge_per_share": 0.001,
                                "total_edge": 6.0,
                                "capital_capped": {"edge": 0.1},
                                "pair": {
                                    "trade_allowed": True,
                                    "status": "verified_same_binary_event",
                                    "llm_verification": {"trade_allowed": True, "risk_flags": []},
                                },
                            }
                        ],
                    }
                )
                + "\n"
            )

            report = success_status_report(cross_platform_scan_path=scan, min_cross_platform_capital_edge=0.5)

        self.assertEqual(report["status"], "no_success")
        self.assertEqual(report["cross_platform"]["verified_positive_count"], 1)
        self.assertEqual(report["cross_platform"]["actionable_verified_positive_count"], 0)

    def test_success_status_ignores_unverified_cross_platform_positive(self):
        with tempfile.TemporaryDirectory() as tmp:
            scan = Path(tmp) / "cross.json"
            scan.write_text(
                json.dumps(
                    {
                        "type": "cross_platform_scan_report",
                        "pair_count": 1,
                        "opportunity_count": 1,
                        "opportunities": [
                            {
                                "net_edge_per_share": 0.001,
                                "total_edge": 6.0,
                                "capital_capped": {"edge": 0.1},
                                "pair": {"trade_allowed": True},
                            }
                        ],
                    }
                )
                + "\n"
            )

            report = success_status_report(cross_platform_scan_path=scan)

        self.assertEqual(report["status"], "no_success")
        self.assertEqual(report["cross_platform"]["verified_positive_count"], 0)

    def test_write_success_status_only_appends_non_empty_statuses(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "status.json"
            log = Path(tmp) / "events.ndjson"

            write_success_status(out, {"status": "no_success"}, success_log_path=log)
            write_success_status(out, {"status": "maker_positive_ev"}, success_log_path=log)

            rows = [json.loads(line) for line in log.read_text().splitlines()]

        self.assertEqual(rows, [{"status": "maker_positive_ev"}])


if __name__ == "__main__":
    unittest.main()
