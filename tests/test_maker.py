import json
import tempfile
import unittest
from pathlib import Path

from poly_strategy.maker import maker_scan_report


class MakerTests(unittest.TestCase):
    def test_maker_scan_finds_neg_risk_no_basket_candidate(self):
        snapshots = [
            _snapshot("a", no_bid=0.60, no_ask=0.64),
            _snapshot("b", no_bid=0.63, no_ask=0.68),
            _snapshot("c", no_bid=0.66, no_ask=0.70),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            snapshot_path = Path(tmp) / "snapshots.ndjson"
            gamma_path = Path(tmp) / "gamma.ndjson"
            snapshot_path.write_text("\n".join(json.dumps(row) for row in snapshots) + "\n")
            gamma_path.write_text(
                "\n".join(json.dumps(_gamma_row(market_id, index)) for index, market_id in enumerate(["a", "b", "c"]))
                + "\n"
            )

            report = maker_scan_report(
                snapshot_path,
                gamma_path=gamma_path,
                tick_size=0.01,
                min_edge=0.005,
                min_roi=0.001,
                max_capital=100,
            )

        self.assertEqual(report["candidate_count"], 1)
        row = report["top"][0]
        self.assertEqual(row["kind"], "maker_neg_risk_no_basket")
        self.assertAlmostEqual(row["passive_cost_per_share"], 1.99)
        self.assertAlmostEqual(row["maker_edge_per_share"], 0.01)
        self.assertGreater(row["expected_edge_at_cap"], 0.4)
        self.assertIn("partial_fill_directional_exposure", row["risk_flags"])

    def test_maker_scan_filters_large_baskets(self):
        snapshots = [_snapshot("a", 0.60, 0.64), _snapshot("b", 0.63, 0.68), _snapshot("c", 0.66, 0.70)]
        with tempfile.TemporaryDirectory() as tmp:
            snapshot_path = Path(tmp) / "snapshots.ndjson"
            gamma_path = Path(tmp) / "gamma.ndjson"
            snapshot_path.write_text("\n".join(json.dumps(row) for row in snapshots) + "\n")
            gamma_path.write_text(
                "\n".join(json.dumps(_gamma_row(market_id, index)) for index, market_id in enumerate(["a", "b", "c"]))
                + "\n"
            )

            report = maker_scan_report(snapshot_path, gamma_path=gamma_path, tick_size=0.01, max_leg_count=2)

        self.assertEqual(report["candidate_count"], 0)


def _snapshot(market_id: str, no_bid: float, no_ask: float):
    yes_bid = max(0.0, 1.0 - no_ask - 0.02)
    yes_ask = min(1.0, 1.0 - no_bid + 0.02)
    return {
        "type": "binary_snapshot",
        "ts": "2026-05-10T00:00:00Z",
        "venue": "polymarket",
        "market_id": market_id,
        "fee_rate": 0.05,
        "yes": {"token_id": f"{market_id}-yes", "asks": [[yes_ask, 100]], "bids": [[yes_bid, 100]]},
        "no": {"token_id": f"{market_id}-no", "asks": [[no_ask, 100]], "bids": [[no_bid, 100]]},
    }


def _gamma_row(market_id: str, threshold: int):
    return {
        "type": "raw_polymarket_gamma_market",
        "market_id": market_id,
        "raw": {
            "id": market_id,
            "question": f"Will {market_id} happen?",
            "description": "Same neg-risk group.",
            "closed": False,
            "enableOrderBook": True,
            "acceptingOrders": True,
            "outcomes": json.dumps(["Yes", "No"]),
            "clobTokenIds": json.dumps([f"{market_id}-yes", f"{market_id}-no"]),
            "negRisk": True,
            "negRiskMarketID": "group-1",
            "groupItemThreshold": str(threshold),
            "groupItemTitle": market_id,
        },
    }


if __name__ == "__main__":
    unittest.main()
