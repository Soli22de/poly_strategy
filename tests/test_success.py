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
