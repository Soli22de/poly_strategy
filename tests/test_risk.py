import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from poly_strategy.risk import risk_check_execution_plan


class RiskTests(unittest.TestCase):
    def test_risk_check_passes_dry_run_under_limits(self):
        row = _plan(price=0.45, size=10)

        check = risk_check_execution_plan(row, max_trade_notional=5, max_daily_orders=2)

        self.assertTrue(check["passed"])
        self.assertAlmostEqual(check["planned_notional"], 4.5)

    def test_risk_check_blocks_kill_switch_and_notional(self):
        with tempfile.TemporaryDirectory() as tmp:
            kill = Path(tmp) / "KILL_SWITCH"
            kill.write_text("stop")

            check = risk_check_execution_plan(_plan(price=0.9, size=10), kill_switch_path=kill, max_trade_notional=5)

        self.assertFalse(check["passed"])
        failed = {row["name"] for row in check["checks"] if not row["passed"]}
        self.assertIn("kill_switch_absent", failed)
        self.assertIn("max_trade_notional", failed)

    def test_risk_check_blocks_paused_or_daily_order_exhausted_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "risk.json"
            state.write_text(json.dumps({"date": "2026-05-09", "orders": 2, "pause_until": "2026-05-09T01:00:00Z"}))

            check = risk_check_execution_plan(
                _plan(price=0.1, size=1),
                state_path=state,
                max_daily_orders=2,
                now=datetime(2026, 5, 9, 0, 0, tzinfo=timezone.utc),
            )

        self.assertFalse(check["passed"])
        failed = {row["name"] for row in check["checks"] if not row["passed"]}
        self.assertIn("not_paused", failed)
        self.assertIn("max_daily_orders", failed)


def _plan(price: float, size: float) -> dict:
    return {
        "type": "execution_plan",
        "dry_run": True,
        "orders": [{"price": price, "size": size, "token_id": "yes-token"}],
    }


if __name__ == "__main__":
    unittest.main()
