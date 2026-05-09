import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from poly_strategy.realtime import (
    RealtimeOrderBookStore,
    kalshi_orderbook_subscription_payload,
    load_watchlist_markets,
    monitor_polymarket_watchlist,
    polymarket_subscription_payload,
    token_ids_from_watchlist,
)


class RealtimeTests(unittest.TestCase):
    def test_polymarket_subscription_payload_dedupes_asset_ids(self):
        payload = polymarket_subscription_payload(["yes-token", "no-token", "yes-token"])

        self.assertEqual(payload["assets_ids"], ["yes-token", "no-token"])
        self.assertEqual(payload["type"], "market")
        self.assertTrue(payload["custom_feature_enabled"])

    def test_kalshi_orderbook_subscription_payload_uses_yes_price(self):
        payload = kalshi_orderbook_subscription_payload(["KXTEST-YES", "KXTEST-NO"], command_id=7)

        self.assertEqual(payload["id"], 7)
        self.assertEqual(payload["cmd"], "subscribe")
        self.assertEqual(payload["params"]["channels"], ["orderbook_delta"])
        self.assertEqual(payload["params"]["market_tickers"], ["KXTEST-YES", "KXTEST-NO"])
        self.assertTrue(payload["params"]["use_yes_price"])

    def test_store_applies_polymarket_book_and_price_change(self):
        store = RealtimeOrderBookStore()

        rows = store.apply_polymarket_message(
            {
                "event_type": "book",
                "asset_id": "yes-token",
                "market": "market-1",
                "timestamp": "1710000000000",
                "bids": [{"price": "0.40", "size": "5"}],
                "asks": [{"price": "0.50", "size": "7"}],
            }
        )
        change_rows = store.apply_polymarket_message(
            {
                "event_type": "price_change",
                "market": "market-1",
                "timestamp": "1710000001",
                "price_changes": [
                    {"asset_id": "yes-token", "side": "SELL", "price": "0.49", "size": "3"},
                    {"asset_id": "yes-token", "side": "BUY", "price": "0.41", "size": "2"},
                    {"asset_id": "yes-token", "side": "SELL", "price": "0.50", "size": "0"},
                ],
            }
        )

        book = store.book("yes-token")
        self.assertEqual(rows[0]["best_ask"], 0.5)
        self.assertEqual(change_rows[-1]["best_ask"], 0.49)
        self.assertEqual(book["asks"][0].price, 0.49)
        self.assertEqual(book["bids"][0].price, 0.41)
        self.assertEqual(store.last_update_ts, "2024-03-09T16:00:01Z")

    def test_binary_snapshot_rows_from_watchlist_books(self):
        store = RealtimeOrderBookStore()
        store.apply_polymarket_message(
            [
                {
                    "event_type": "book",
                    "asset_id": "yes-token",
                    "market": "market-1",
                    "timestamp": "1710000000000",
                    "bids": [{"price": "0.43", "size": "4"}],
                    "asks": [{"price": "0.45", "size": "10"}],
                },
                {
                    "event_type": "book",
                    "asset_id": "no-token",
                    "market": "market-1",
                    "timestamp": "1710000000000",
                    "bids": [{"price": "0.52", "size": "5"}],
                    "asks": [{"price": "0.53", "size": "7"}],
                },
            ]
        )

        rows = store.binary_snapshot_rows(
            [
                {
                    "market_id": "market-1",
                    "question": "Sample?",
                    "fee_rate": 0.03,
                    "yes_token_id": "yes-token",
                    "no_token_id": "no-token",
                }
            ],
            ts="2026-05-09T00:00:00Z",
        )

        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["type"], "binary_snapshot")
        self.assertEqual(row["fee_rate"], 0.03)
        self.assertEqual(row["yes"]["asks"], [[0.45, 10.0]])
        self.assertEqual(row["no"]["bids"], [[0.52, 5.0]])

    def test_load_watchlist_markets_and_token_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "watchlist.json"
            path.write_text(
                json.dumps(
                    {
                        "type": "polymarket_watchlist",
                        "markets": [
                            {"yes_token_id": "yes-token", "no_token_id": "no-token"},
                            {"yes_token_id": "yes-token", "no_token_id": "other-no"},
                        ],
                    }
                )
            )

            markets = load_watchlist_markets(path)

        self.assertEqual(token_ids_from_watchlist(markets), ["yes-token", "no-token", "other-no"])

    def test_monitor_polymarket_watchlist_scans_live_snapshots(self):
        messages = [
            [
                {
                    "event_type": "book",
                    "asset_id": "yes-token",
                    "market": "market-1",
                    "timestamp": "1710000000000",
                    "bids": [{"price": "0.44", "size": "5"}],
                    "asks": [{"price": "0.45", "size": "10"}],
                },
                {
                    "event_type": "book",
                    "asset_id": "no-token",
                    "market": "market-1",
                    "timestamp": "1710000000000",
                    "bids": [{"price": "0.52", "size": "5"}],
                    "asks": [{"price": "0.53", "size": "7"}],
                },
            ]
        ]
        fake_socket = _FakeWebSocket(messages)

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            watchlist = tmp_path / "watchlist.json"
            rules = tmp_path / "rules.json"
            report = tmp_path / "report.jsonl"
            updates = tmp_path / "updates.ndjson"
            snapshots = tmp_path / "snapshots.ndjson"
            watchlist.write_text(
                json.dumps(
                    {
                        "type": "polymarket_watchlist",
                        "markets": [
                            {
                                "market_id": "market-1",
                                "question": "Sample?",
                                "fee_rate": 0.0,
                                "yes_token_id": "yes-token",
                                "no_token_id": "no-token",
                            }
                        ],
                    }
                )
            )
            rules.write_text(json.dumps({}))
            progress_rows = []

            with patch.dict(
                sys.modules,
                {"websockets": SimpleNamespace(connect=lambda url: fake_socket)},
            ):
                summary = monitor_polymarket_watchlist(
                    watchlist,
                    report,
                    rules_path=rules,
                    updates_out_path=updates,
                    snapshots_out_path=snapshots,
                    max_messages=1,
                    snapshot_interval_seconds=0,
                    min_net_edge=0.0,
                    progress=progress_rows.append,
                )

            report_rows = [json.loads(line) for line in report.read_text().splitlines()]
            update_rows = [json.loads(line) for line in updates.read_text().splitlines()]
            snapshot_rows = [json.loads(line) for line in snapshots.read_text().splitlines()]

        self.assertEqual(summary["type"], "realtime_monitor_summary")
        self.assertEqual(summary["iterations_completed"], 1)
        self.assertEqual(summary["opportunity_count"], 1)
        self.assertEqual(progress_rows[0]["current_opportunity_count"], 1)
        self.assertEqual(report_rows[0]["type"], "realtime_monitor_iteration")
        self.assertEqual(report_rows[1]["type"], "realtime_monitor_summary")
        self.assertEqual(len(update_rows), 2)
        self.assertEqual(snapshot_rows[0]["type"], "binary_snapshot")
        self.assertEqual(json.loads(fake_socket.sent[0])["assets_ids"], ["yes-token", "no-token"])


class _FakeWebSocket:
    def __init__(self, messages):
        self._messages = list(messages)
        self.sent = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    async def send(self, payload):
        self.sent.append(payload)

    def __aiter__(self):
        return self

    async def __anext__(self):
        return await self.recv()

    async def recv(self):
        if not self._messages:
            raise StopAsyncIteration
        return json.dumps(self._messages.pop(0))


if __name__ == "__main__":
    unittest.main()
