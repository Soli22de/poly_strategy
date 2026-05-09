import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from poly_strategy.collectors import (
    binary_snapshot_rows_from_gamma_markets,
    collect_polymarket_binary_snapshots_for_market_ids,
    collect_polymarket_binary_snapshots_for_markets,
    collect_polymarket_binary_snapshots_loop,
    collect_polymarket_gamma_pages,
    collect_polymarket_gamma_markets_by_id,
    expand_market_ids_with_neg_risk_groups,
    market_ids_from_rule_file,
    raw_gamma_markets_from_ndjson,
)


class CollectorTests(unittest.TestCase):
    def test_collect_polymarket_gamma_markets_by_id_appends_raw_rows(self):
        calls = []

        def fetch_json(url, timeout, proxy):
            calls.append((url, timeout, proxy))
            return {"id": url.rsplit("/", 1)[-1], "question": "Sample?"}

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "gamma.ndjson"

            count = collect_polymarket_gamma_markets_by_id(
                path,
                ["a market", "a market", "b"],
                timeout=7,
                proxy="127.0.0.1:10808",
                fetch_json=fetch_json,
            )
            rows = [json.loads(line) for line in path.read_text().splitlines()]

        self.assertEqual(count, 2)
        self.assertEqual(len(calls), 2)
        self.assertIn("a%20market", calls[0][0])
        self.assertEqual(calls[0][1], 7)
        self.assertEqual(calls[0][2], "127.0.0.1:10808")
        self.assertEqual([row["type"] for row in rows], ["raw_polymarket_gamma_market", "raw_polymarket_gamma_market"])

    def test_collect_polymarket_gamma_pages_uses_offsets(self):
        calls = []

        def collect_page(path, limit, timeout, proxy, offset):
            calls.append((path, limit, timeout, proxy, offset))
            return 2

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "gamma.ndjson"

            count = collect_polymarket_gamma_pages(
                path,
                limit=100,
                pages=3,
                timeout=7,
                proxy="127.0.0.1:10808",
                start_offset=50,
                collect_page=collect_page,
            )

        self.assertEqual(count, 6)
        self.assertEqual([call[4] for call in calls], [50, 150, 250])

    def test_expand_market_ids_with_neg_risk_groups_adds_known_group_members(self):
        markets = [
            {"id": "a", "negRiskMarketID": "group-1"},
            {"id": "b", "negRiskMarketID": "group-1"},
            {"id": "c", "negRiskMarketID": "group-2"},
        ]

        market_ids = expand_market_ids_with_neg_risk_groups(markets, {"a"})

        self.assertEqual(market_ids, {"a", "b"})

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

        rows = binary_snapshot_rows_from_gamma_markets([market], lambda token_id: books[token_id], ts="2026-05-08T00:00:00Z")

        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["type"], "binary_snapshot")
        self.assertEqual(row["ts"], "2026-05-08T00:00:00Z")
        self.assertEqual(row["market_id"], "123")
        self.assertEqual(row["fee_rate"], 0.05)
        self.assertEqual(row["yes"]["token_id"], "yes-token")
        self.assertEqual(row["yes"]["asks"][0], [0.45, 10.0])
        self.assertEqual(row["yes"]["bids"][0], [0.44, 10.0])
        self.assertEqual(row["no"]["asks"][0], [0.53, 7.0])

    def test_collect_polymarket_binary_snapshots_loop_runs_requested_iterations(self):
        calls = []

        def collect_once(path, limit, timeout, proxy, max_workers):
            calls.append((path, limit, timeout, proxy, max_workers))
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
        self.assertEqual(calls[0][1:], (2, 3.0, "http://127.0.0.1:10808", 1))

    def test_binary_snapshot_rows_from_gamma_markets_fetches_books_concurrently(self):
        markets = [
            {
                "id": "a",
                "closed": False,
                "enableOrderBook": True,
                "acceptingOrders": True,
                "outcomes": json.dumps(["Yes", "No"]),
                "clobTokenIds": json.dumps(["a-yes", "a-no"]),
            },
            {
                "id": "b",
                "closed": False,
                "enableOrderBook": True,
                "acceptingOrders": True,
                "outcomes": json.dumps(["Yes", "No"]),
                "clobTokenIds": json.dumps(["b-yes", "b-no"]),
            },
        ]
        books = {
            token_id: {"asks": [{"price": "0.50", "size": "10"}], "bids": []}
            for token_id in ["a-yes", "a-no", "b-yes", "b-no"]
        }
        fetched = []

        def book_fetcher(token_id):
            fetched.append(token_id)
            return books[token_id]

        rows = binary_snapshot_rows_from_gamma_markets(
            markets,
            book_fetcher,
            ts="2026-05-09T00:00:00Z",
            max_workers=4,
        )

        self.assertEqual([row["market_id"] for row in rows], ["a", "b"])
        self.assertEqual(set(fetched), {"a-yes", "a-no", "b-yes", "b-no"})

    def test_binary_snapshot_rows_can_skip_failed_book_fetches(self):
        markets = [
            {
                "id": "good",
                "closed": False,
                "enableOrderBook": True,
                "acceptingOrders": True,
                "outcomes": json.dumps(["Yes", "No"]),
                "clobTokenIds": json.dumps(["good-yes", "good-no"]),
            },
            {
                "id": "bad",
                "closed": False,
                "enableOrderBook": True,
                "acceptingOrders": True,
                "outcomes": json.dumps(["Yes", "No"]),
                "clobTokenIds": json.dumps(["bad-yes", "bad-no"]),
            },
        ]
        books = {
            "good-yes": {"asks": [{"price": "0.40", "size": "10"}], "bids": []},
            "good-no": {"asks": [{"price": "0.61", "size": "10"}], "bids": []},
            "bad-yes": {"asks": [{"price": "0.30", "size": "10"}], "bids": []},
        }
        errors = []

        def book_fetcher(token_id):
            if token_id == "bad-no":
                raise RuntimeError("temporary book failure")
            return books[token_id]

        rows = binary_snapshot_rows_from_gamma_markets(
            markets,
            book_fetcher,
            ts="2026-05-09T00:00:00Z",
            skip_book_errors=True,
            errors=errors,
        )

        self.assertEqual([row["market_id"] for row in rows], ["good"])
        self.assertEqual([error["kind"] for error in errors], ["book_fetch_error", "market_skipped"])
        self.assertEqual(errors[0]["token_id"], "bad-no")
        self.assertEqual(errors[1]["market_id"], "bad")

    def test_market_ids_from_rule_file_reads_all_rule_sections(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rules.json"
            path.write_text(
                json.dumps(
                    {
                        "implications": [{"antecedent": "a", "consequent": "b"}],
                        "mutually_exclusive": [{"first": "c", "second": "d"}],
                        "equivalent": [{"first": "e", "second": "f"}],
                        "collectively_exhaustive": [{"first": "g", "second": "h"}],
                        "exhaustive_groups": [{"market_ids": ["m", "n", "o"]}],
                        "complement": [{"first": "i", "second": "j"}],
                        "candidates": [{"market_a_id": "k", "market_b_id": "l"}],
                    }
                )
            )

            market_ids = market_ids_from_rule_file(path)

        self.assertEqual(market_ids, {"a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "m", "n", "o"})

    def test_market_ids_from_rule_file_falls_back_to_clean_pair_candidates(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rules.json"
            path.write_text(
                json.dumps(
                    {
                        "candidates": [
                            {
                                "relation_type": "mutually_exclusive",
                                "market_a_id": "a",
                                "market_b_id": "b",
                                "trade_allowed": True,
                                "risk_flags": [],
                            },
                            {
                                "relation_type": "implies",
                                "market_a_id": "c",
                                "market_b_id": "d",
                                "trade_allowed": True,
                                "risk_flags": [],
                            },
                            {
                                "relation_type": "equivalent",
                                "market_a_id": "risky",
                                "market_b_id": "b",
                                "trade_allowed": True,
                                "risk_flags": ["ambiguous_wording"],
                            },
                        ]
                    }
                )
            )

            market_ids = market_ids_from_rule_file(path)

        self.assertEqual(market_ids, {"a", "b"})

    def test_collect_polymarket_binary_snapshots_for_markets_fetches_only_rule_markets(self):
        markets = [
            {
                "id": "a",
                "closed": False,
                "enableOrderBook": True,
                "acceptingOrders": True,
                "outcomes": json.dumps(["Yes", "No"]),
                "clobTokenIds": json.dumps(["a-yes", "a-no"]),
                "question": "A?",
            },
            {
                "id": "b",
                "closed": False,
                "enableOrderBook": True,
                "acceptingOrders": True,
                "outcomes": json.dumps(["Yes", "No"]),
                "clobTokenIds": json.dumps(["b-yes", "b-no"]),
                "question": "B?",
            },
            {
                "id": "unused",
                "closed": False,
                "enableOrderBook": True,
                "acceptingOrders": True,
                "outcomes": json.dumps(["Yes", "No"]),
                "clobTokenIds": json.dumps(["unused-yes", "unused-no"]),
                "question": "Unused?",
            },
        ]
        books = {
            "a-yes": {"asks": [{"price": "0.40", "size": "10"}], "bids": []},
            "a-no": {"asks": [{"price": "0.61", "size": "10"}], "bids": []},
            "b-yes": {"asks": [{"price": "0.30", "size": "10"}], "bids": []},
            "b-no": {"asks": [{"price": "0.72", "size": "10"}], "bids": []},
        }
        fetched = []

        def book_fetcher(token_id):
            fetched.append(token_id)
            return books[token_id]

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "targeted.ndjson"
            count = collect_polymarket_binary_snapshots_for_markets(
                path,
                markets,
                {"a", "b"},
                book_fetcher,
                ts="2026-05-08T00:00:00Z",
            )
            rows = [json.loads(line) for line in path.read_text().splitlines()]

        self.assertEqual(count, 2)
        self.assertEqual(fetched, ["a-yes", "a-no", "b-yes", "b-no"])
        self.assertEqual({row["market_id"] for row in rows}, {"a", "b"})
        self.assertEqual({row["ts"] for row in rows}, {"2026-05-08T00:00:00Z"})

    def test_collect_polymarket_binary_snapshots_for_market_ids_expands_groups(self):
        gamma_rows = [
            _raw_gamma("a", "group", ["a-yes", "a-no"]),
            _raw_gamma("b", "group", ["b-yes", "b-no"]),
            _raw_gamma("unused", "", ["unused-yes", "unused-no"]),
        ]
        books = {
            token_id: {"asks": [{"price": "0.50", "size": "10"}], "bids": []}
            for token_id in ["a-yes", "a-no", "b-yes", "b-no"]
        }

        def fetch_json(url, timeout, proxy=None):
            token_id = url.split("token_id=", 1)[1]
            return books[token_id]

        with tempfile.TemporaryDirectory() as tmp:
            gamma = Path(tmp) / "gamma.ndjson"
            out = Path(tmp) / "snapshots.ndjson"
            gamma.write_text("\n".join(json.dumps(row) for row in gamma_rows) + "\n")
            with patch("poly_strategy.collectors._fetch_json", side_effect=fetch_json):
                count = collect_polymarket_binary_snapshots_for_market_ids(
                    out,
                    gamma,
                    ["a"],
                    timeout=5.0,
                    expand_neg_risk_groups=True,
                )
            rows = [json.loads(line) for line in out.read_text().splitlines()]

        self.assertEqual(count, 2)
        self.assertEqual({row["market_id"] for row in rows}, {"a", "b"})

    def test_raw_gamma_markets_from_ndjson_dedupes_repeated_collections(self):
        rows = [
            {"type": "raw_polymarket_gamma_market", "market_id": "a", "raw": {"id": "a", "question": "old"}},
            {"type": "raw_polymarket_gamma_market", "market_id": "b", "raw": {"id": "b", "question": "b"}},
            {"type": "raw_polymarket_gamma_market", "market_id": "a", "raw": {"id": "a", "question": "new"}},
        ]

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "gamma.ndjson"
            path.write_text("\n".join(json.dumps(row) for row in rows) + "\n")

            markets = raw_gamma_markets_from_ndjson(path)

        self.assertEqual([market["id"] for market in markets], ["a", "b"])
        self.assertEqual(markets[0]["question"], "new")


def _raw_gamma(market_id: str, group_id: str, token_ids: list) -> dict:
    return {
        "type": "raw_polymarket_gamma_market",
        "market_id": market_id,
        "raw": {
            "id": market_id,
            "question": f"{market_id}?",
            "closed": False,
            "enableOrderBook": True,
            "acceptingOrders": True,
            "outcomes": json.dumps(["Yes", "No"]),
            "clobTokenIds": json.dumps(token_ids),
            "negRiskMarketID": group_id or None,
        },
    }


if __name__ == "__main__":
    unittest.main()
