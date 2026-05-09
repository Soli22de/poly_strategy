import json
import tempfile
import unittest
from pathlib import Path

from poly_strategy.alerts import latest_monitor_alerts, write_alerts


class AlertTests(unittest.TestCase):
    def test_latest_monitor_alerts_extracts_stable_paper_trades(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "report.jsonl"
            out = Path(tmp) / "alerts.ndjson"
            report.write_text(
                json.dumps({"type": "paper_monitor_summary"}) + "\n"
                + json.dumps(
                    {
                        "type": "realtime_monitor_iteration",
                        "ts": "2026-05-09T00:00:00Z",
                        "iteration": 3,
                        "last_snapshot_ts": "2026-05-09T00:00:00Z",
                        "stable_paper_trades": [
                            _trade("high", paper_roi=0.05, paper_edge=0.2),
                            _trade("low", paper_roi=0.005, paper_edge=0.1),
                        ],
                    }
                )
                + "\n"
            )

            alerts = latest_monitor_alerts(report, min_paper_roi=0.01)
            count = write_alerts(alerts, out)
            written = [json.loads(line) for line in out.read_text().splitlines()]

        self.assertEqual(count, 1)
        self.assertEqual(alerts[0]["type"], "opportunity_alert")
        self.assertEqual(alerts[0]["key"], "high")
        self.assertEqual(alerts[0]["market_ids"], ["m1", "m2"])
        self.assertEqual(written[0]["alert_kind"], "stable_paper_trade")

    def test_latest_monitor_alerts_can_include_current_opportunities(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "report.jsonl"
            report.write_text(
                json.dumps(
                    {
                        "type": "paper_monitor_iteration",
                        "iteration": 1,
                        "stable_paper_trades": [],
                        "stable_opportunities": [_opportunity("stable")],
                        "current_opportunities": [_opportunity("current")],
                    }
                )
                + "\n"
            )

            alerts = latest_monitor_alerts(report, include_current=True)

        self.assertEqual([alert["alert_kind"] for alert in alerts], ["stable_opportunity", "current_opportunity"])


def _trade(key: str, paper_roi: float, paper_edge: float) -> dict:
    row = _opportunity(key)
    row.update({"paper_roi": paper_roi, "paper_edge": paper_edge})
    return row


def _opportunity(key: str) -> dict:
    return {
        "key": key,
        "kind": "yes_no_bundle",
        "net_edge_per_share": 0.02,
        "total_edge": 0.1,
        "legs": [{"market_id": "m1"}, {"market_id": "m2"}],
    }


if __name__ == "__main__":
    unittest.main()
