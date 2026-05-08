import json
import tempfile
import unittest
from pathlib import Path

from poly_strategy.collectors import binary_snapshot_rows_from_gamma_markets, collect_polymarket_binary_snapshots_loop


class CollectorTests(unittest.TestCase):
    def test_binary_snapshot_rows_from_gamma_markets_fetches_yes_and_no_books(self):
        market = {
            "id": "123",
            "closed": False,
            "enableOrderBook": True,
            "acceptingOrders": True,
            "outcomes": json.dumps(["Yes", "No"]),
            "clobTokenIds": json.dumps(["yes-token", "no-token"]),
            "feesEnabled": True,
            "feeSchedule": {"rate": 0.05},
            "question": "Sample?",
        }
        books = {
            "yes-token": {
                "asks": [{"price": "0.99", "size": "100"}, {"price": "0.45", "size": "10"}],
                "bids": [{"price": "0.01", "size": "100"}, {"price": "0.44", "size": "10"}],
            },
            "no-token": {
                "asks": [{"price": "0.98", "size": "100"}, {"price": "0.53", "size": "7"}],
                "bids": [{"price": "0.02", "size": "100"}, {"price": "0.52", "size": "7"}],
            },
        }

        rows = binary_snapshot_rows_from_gamma_markets([market], lambda token_id: books[token_id])

        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["type"], "binary_snapshot")
        self.assertEqual(row["market_id"], "123")
        self.assertEqual(row["fee_rate"], 0.05)
        self.assertEqual(row["yes"]["token_id"], "yes-token")
        self.assertEqual(row["yes"]["asks"][0], [0.45, 10.0])
        self.assertEqual(row["yes"]["bids"][0], [0.44, 10.0])
        self.assertEqual(row["no"]["asks"][0], [0.53, 7.0])

    def test_collect_polymarket_binary_snapshots_loop_runs_requested_iterations(self):
        calls = []

        def collect_once(path, limit, timeout, proxy):
            calls.append((path, limit, timeout, proxy))
            with path.open("a") as handle:
                handle.write(json.dumps({"type": "binary_snapshot", "market_id": f"m{len(calls)}"}) + "\n")
            return 1

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "loop.ndjson"
            count = collect_polymarket_binary_snapshots_loop(
                path=path,
                limit=2,
                timeout=3.0,
                proxy="http://127.0.0.1:10808",
                interval_seconds=0.0,
                iterations=3,
                collect_once=collect_once,
                sleep=lambda seconds: None,
            )

            lines = path.read_text().splitlines()

        self.assertEqual(count, 3)
        self.assertEqual(len(calls), 3)
        self.assertEqual(len(lines), 3)
        self.assertEqual(calls[0][1:], (2, 3.0, "http://127.0.0.1:10808"))


if __name__ == "__main__":
    unittest.main()
