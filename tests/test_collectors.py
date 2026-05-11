import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from poly_strategy.collectors import (
    binary_snapshot_rows_from_gamma_markets,
    collect_kalshi_markets_by_event_tickers,
    collect_kalshi_markets_pages,
    collect_polymarket_binary_snapshots_for_market_ids,
    collect_polymarket_binary_snapshots_for_markets,
    collect_polymarket_binary_snapshots_loop,
    collect_polymarket_data_trades,
    collect_polymarket_gamma_pages,
    collect_polymarket_gamma_markets_by_id,
    fetch_polymarket_books_by_token_id,
    kalshi_binary_snapshot_rows_from_orderbooks,
    kalshi_binary_snapshot_rows_from_orderbook_lines,
    expand_market_ids_with_neg_risk_groups,
    limit_market_ids_by_gamma_order,
    market_ids_from_rule_file,
    raw_gamma_markets_from_ndjson,
    write_kalshi_binary_snapshots,
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

    def test_collect_polymarket_gamma_markets_by_id_can_fetch_condition_id(self):
        calls = []

        def fetch_json(url, timeout, proxy):
            calls.append(url)
            return [{"id": "123", "conditionId": "0xabc", "question": "Sample?"}]

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "gamma.ndjson"

            count = collect_polymarket_gamma_markets_by_id(path, ["0xabc"], timeout=7, proxy=None, fetch_json=fetch_json)
            row = json.loads(path.read_text().splitlines()[0])

        self.assertEqual(count, 1)
        self.assertIn("condition_ids=0xabc", calls[0])
        self.assertEqual(row["market_id"], "123")

    def test_collect_polymarket_gamma_markets_by_id_can_skip_failed_condition_id(self):
        errors = []

        def fetch_json(url, timeout, proxy):
            return []

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "gamma.ndjson"

            count = collect_polymarket_gamma_markets_by_id(
                path,
                ["0xmissing"],
                timeout=7,
                proxy=None,
                fetch_json=fetch_json,
                skip_errors=True,
                errors=errors,
            )

        self.assertEqual(count, 0)
        self.assertEqual(errors[0]["kind"], "gamma_market_fetch_error")

    def test_collect_polymarket_data_trades_maps_condition_ids(self):
        calls = []

        def fetch_json(url, timeout, proxy):
            calls.append((url, timeout, proxy))
            return [
                {
                    "conditionId": "0xabc",
                    "asset": "no-token",
                    "side": "SELL",
                    "price": 0.65,
                    "size": 4,
                    "timestamp": 1778371230,
                    "transactionHash": "0xtrade",
                }
            ]

        with tempfile.TemporaryDirectory() as tmp:
            gamma = Path(tmp) / "gamma.ndjson"
            out = Path(tmp) / "trades.ndjson"
            gamma.write_text(
                json.dumps(
                    {
                        "type": "raw_polymarket_gamma_market",
                        "market_id": "m1",
                        "raw": {"id": "m1", "conditionId": "0xabc"},
                    }
                )
                + "\n"
            )

            count = collect_polymarket_data_trades(
                out,
                gamma,
                ["m1"],
                limit=25,
                timeout=7,
                proxy="127.0.0.1:10808",
                side="SELL",
                fetch_json=fetch_json,
            )
            row = json.loads(out.read_text().splitlines()[0])

        self.assertEqual(count, 1)
        self.assertIn("market=0xabc", calls[0][0])
        self.assertIn("side=SELL", calls[0][0])
        self.assertEqual(calls[0][1], 7)
        self.assertEqual(calls[0][2], "127.0.0.1:10808")
        self.assertEqual(row["type"], "raw_polymarket_data_trade")
        self.assertEqual(row["market_id"], "m1")
        self.assertEqual(row["asset_id"], "no-token")
        self.assertEqual(row["price"], 0.65)

    def test_collect_polymarket_data_trades_can_fetch_per_market(self):
        calls = []

        def fetch_json(url, timeout, proxy):
            calls.append(url)
            if "market=0xabc" in url:
                return [
                    {
                        "conditionId": "0xabc",
                        "asset": "yes-a",
                        "side": "SELL",
                        "price": 0.41,
                        "size": 3,
                        "timestamp": 1778371230,
                        "transactionHash": "0xa",
                    }
                ]
            return [
                {
                    "conditionId": "0xdef",
                    "asset": "yes-b",
                    "side": "SELL",
                    "price": 0.42,
                    "size": 4,
                    "timestamp": 1778371240,
                    "transactionHash": "0xb",
                }
            ]

        with tempfile.TemporaryDirectory() as tmp:
            gamma = Path(tmp) / "gamma.ndjson"
            out = Path(tmp) / "trades.ndjson"
            gamma.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "type": "raw_polymarket_gamma_market",
                                "market_id": "m1",
                                "raw": {"id": "m1", "conditionId": "0xabc"},
                            }
                        ),
                        json.dumps(
                            {
                                "type": "raw_polymarket_gamma_market",
                                "market_id": "m2",
                                "raw": {"id": "m2", "conditionId": "0xdef"},
                            }
                        ),
                    ]
                )
                + "\n"
            )

            count = collect_polymarket_data_trades(
                out,
                gamma,
                ["m1", "m2"],
                limit=25,
                timeout=7,
                side="SELL",
                per_market=True,
                fetch_json=fetch_json,
            )
            rows = [json.loads(line) for line in out.read_text().splitlines()]

        self.assertEqual(count, 2)
        self.assertEqual(len(calls), 2)
        self.assertTrue(all("%2C" not in url and "," not in url for url in calls))
        self.assertEqual([row["market_id"] for row in rows], ["m1", "m2"])
        self.assertEqual([row["asset_id"] for row in rows], ["yes-a", "yes-b"])

    def test_collect_polymarket_data_trades_can_skip_per_market_errors(self):
        calls = []

        def fetch_json(url, timeout, proxy):
            calls.append(url)
            if "market=0xabc" in url:
                raise TimeoutError("slow")
            return [
                {
                    "conditionId": "0xdef",
                    "asset": "yes-b",
                    "side": "SELL",
                    "price": 0.42,
                    "size": 4,
                    "timestamp": 1778371240,
                }
            ]

        with tempfile.TemporaryDirectory() as tmp:
            gamma = Path(tmp) / "gamma.ndjson"
            out = Path(tmp) / "trades.ndjson"
            gamma.write_text(
                "\n".join(
                    [
                        json.dumps({"type": "raw_polymarket_gamma_market", "raw": {"id": "m1", "conditionId": "0xabc"}}),
                        json.dumps({"type": "raw_polymarket_gamma_market", "raw": {"id": "m2", "conditionId": "0xdef"}}),
                    ]
                )
                + "\n"
            )
            errors = []

            count = collect_polymarket_data_trades(
                out,
                gamma,
                ["m1", "m2"],
                limit=25,
                timeout=7,
                per_market=True,
                skip_errors=True,
                errors=errors,
                retries=1,
                fetch_json=fetch_json,
            )
            rows = [json.loads(line) for line in out.read_text().splitlines()]

        self.assertEqual(count, 1)
        self.assertEqual(len(calls), 3)
        self.assertEqual(errors[0]["kind"], "polymarket_data_trade_fetch_error")
        self.assertEqual(rows[0]["market_id"], "m2")

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

    def test_collect_kalshi_markets_pages_follows_cursor_until_exhausted(self):
        calls = []

        def fetch_page(limit, timeout, proxy, cursor=None, status="open", tickers=None):
            calls.append((limit, timeout, proxy, cursor, status, tuple(tickers or [])))
            if cursor is None:
                return ([{"ticker": "A"}], "cursor-1")
            if cursor == "cursor-1":
                return ([{"ticker": "B"}], None)
            return ([], None)

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "kalshi.ndjson"

            with patch("poly_strategy.collectors.fetch_kalshi_markets_page", side_effect=fetch_page):
                count = collect_kalshi_markets_pages(path, limit=2, timeout=3.0, proxy="127.0.0.1:10808", pages=None)

            rows = [json.loads(line) for line in path.read_text().splitlines()]

        self.assertEqual(count, 2)
        self.assertEqual([row["market_id"] for row in rows], ["A", "B"])
        self.assertEqual([call[3] for call in calls], [None, "cursor-1"])

    def test_collect_kalshi_markets_by_event_tickers_filters_each_event(self):
        calls = []

        def fetch_page(limit, timeout, proxy, cursor=None, status="open", tickers=None, event_ticker=None):
            calls.append((limit, timeout, proxy, status, event_ticker))
            return ([{"ticker": f"{event_ticker}-MKT", "event_ticker": event_ticker}], None)

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "kalshi-event-markets.ndjson"
            with patch("poly_strategy.collectors.fetch_kalshi_markets_page", side_effect=fetch_page):
                count = collect_kalshi_markets_by_event_tickers(
                    path,
                    ["KXEVENT", "KXEVENT", "KXOTHER"],
                    limit=1000,
                    timeout=3.0,
                    proxy="127.0.0.1:10808",
                    status="open",
                )
            rows = [json.loads(line) for line in path.read_text().splitlines()]

        self.assertEqual(count, 2)
        self.assertEqual([call[4] for call in calls], ["KXEVENT", "KXOTHER"])
        self.assertEqual([row["market_id"] for row in rows], ["KXEVENT-MKT", "KXOTHER-MKT"])

    def test_expand_market_ids_with_neg_risk_groups_adds_known_group_members(self):
        markets = [
            {"id": "a", "negRiskMarketID": "group-1"},
            {"id": "b", "negRiskMarketID": "group-1"},
            {"id": "c", "negRiskMarketID": "group-2"},
        ]

        market_ids = expand_market_ids_with_neg_risk_groups(markets, {"a"})

        self.assertEqual(market_ids, {"a", "b"})

    def test_expand_market_ids_with_neg_risk_groups_accepts_condition_id_aliases(self):
        markets = [
            {"id": "a", "conditionId": "0xa", "negRiskMarketID": "group-1"},
            {"id": "b", "conditionId": "0xb", "negRiskMarketID": "group-1"},
            {"id": "c", "conditionId": "0xc", "negRiskMarketID": "group-2"},
        ]

        market_ids = expand_market_ids_with_neg_risk_groups(markets, {"0xa"})

        self.assertEqual(market_ids, {"a", "b"})

    def test_limit_market_ids_by_gamma_order_caps_with_stable_order(self):
        markets = [{"id": "b"}, {"id": "a"}, {"id": "c"}]

        market_ids = limit_market_ids_by_gamma_order(markets, {"a", "b", "c", "unknown"}, 2)

        self.assertEqual(market_ids, {"b", "a"})

    def test_limit_market_ids_by_gamma_order_canonicalizes_condition_ids(self):
        markets = [{"id": "b", "conditionId": "0xb"}, {"id": "a", "conditionId": "0xa"}]

        market_ids = limit_market_ids_by_gamma_order(markets, {"0xa", "0xb"}, 2)

        self.assertEqual(market_ids, {"b", "a"})

    def test_limit_market_ids_by_gamma_order_rejects_non_positive_limit(self):
        with self.assertRaises(ValueError):
            limit_market_ids_by_gamma_order([], {"a"}, 0)

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

    def test_binary_snapshot_rows_from_gamma_markets_accepts_two_non_yes_no_outcomes(self):
        market = {
            "id": "up-down",
            "closed": False,
            "enableOrderBook": True,
            "acceptingOrders": True,
            "outcomes": json.dumps(["Up", "Down"]),
            "clobTokenIds": json.dumps(["up-token", "down-token"]),
        }
        books = {
            "up-token": {"asks": [{"price": "0.51", "size": "10"}], "bids": [{"price": "0.50", "size": "10"}]},
            "down-token": {"asks": [{"price": "0.48", "size": "10"}], "bids": [{"price": "0.47", "size": "10"}]},
        }

        rows = binary_snapshot_rows_from_gamma_markets([market], lambda token_id: books[token_id])

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["market_id"], "up-down")
        self.assertEqual(rows[0]["yes"]["token_id"], "up-token")
        self.assertEqual(rows[0]["no"]["token_id"], "down-token")

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

    def test_fetch_polymarket_books_by_token_id_uses_clob_book_endpoint(self):
        calls = []

        def fetch_json(url, timeout, proxy):
            calls.append((url, timeout, proxy))
            return {"asks": [{"price": "0.5", "size": "10"}], "bids": []}

        books = fetch_polymarket_books_by_token_id(
            ["token-a"],
            timeout=7.0,
            proxy="127.0.0.1:10808",
            fetch_json=fetch_json,
        )

        self.assertEqual(list(books), ["token-a"])
        self.assertIn("token_id=token-a", calls[0][0])
        self.assertEqual(calls[0][1], 7.0)
        self.assertEqual(calls[0][2], "127.0.0.1:10808")

    def test_fetch_polymarket_books_by_token_id_uses_batch_books_endpoint(self):
        calls = []

        def post_json(url, payload, timeout, proxy):
            calls.append((url, payload, timeout, proxy))
            return [
                {"asset_id": "token-a", "asks": [{"price": "0.5", "size": "10"}], "bids": []},
                {"asset_id": "token-b", "asks": [], "bids": [{"price": "0.4", "size": "5"}]},
            ]

        books = fetch_polymarket_books_by_token_id(
            ["token-a", "token-b"],
            timeout=7.0,
            proxy="127.0.0.1:10808",
            post_json=post_json,
            batch_size=500,
        )

        self.assertEqual(set(books), {"token-a", "token-b"})
        self.assertTrue(calls[0][0].endswith("/books"))
        self.assertEqual(calls[0][1], [{"token_id": "token-a"}, {"token_id": "token-b"}])
        self.assertEqual(calls[0][2], 7.0)
        self.assertEqual(calls[0][3], "127.0.0.1:10808")

    def test_fetch_polymarket_books_by_token_id_retries_missing_batch_books(self):
        post_calls = []
        fetch_calls = []

        def post_json(url, payload, timeout, proxy):
            post_calls.append((url, payload, timeout, proxy))
            return [
                {"asset_id": "token-a", "asks": [{"price": "0.5", "size": "10"}], "bids": []},
            ]

        def fetch_json(url, timeout, proxy):
            fetch_calls.append((url, timeout, proxy))
            return {"asset_id": "token-b", "asks": [{"price": "0.6", "size": "3"}], "bids": []}

        books = fetch_polymarket_books_by_token_id(
            ["token-a", "token-b"],
            timeout=7.0,
            proxy="127.0.0.1:10808",
            fetch_json=fetch_json,
            post_json=post_json,
            batch_size=500,
        )

        self.assertEqual(set(books), {"token-a", "token-b"})
        self.assertEqual(len(post_calls), 1)
        self.assertEqual(len(fetch_calls), 1)
        self.assertIn("token_id=token-b", fetch_calls[0][0])

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

    def test_kalshi_orderbooks_convert_bid_books_to_binary_snapshots(self):
        with tempfile.TemporaryDirectory() as tmp:
            orderbooks = Path(tmp) / "kalshi-books.ndjson"
            out = Path(tmp) / "kalshi-snapshots.ndjson"
            orderbooks.write_text(
                json.dumps(
                    {
                        "type": "raw_kalshi_orderbook",
                        "ts": "2026-05-09T00:00:00Z",
                        "market_id": "KXTEST",
                        "raw": {
                            "orderbook": {
                                "yes": [[45, 10], [40, 5]],
                                "no": [[55, 8]],
                            }
                        },
                    }
                )
                + "\n"
            )

            rows = list(kalshi_binary_snapshot_rows_from_orderbooks(orderbooks))
            rows_from_lines = list(kalshi_binary_snapshot_rows_from_orderbook_lines(orderbooks.read_text().splitlines()))
            count = write_kalshi_binary_snapshots(orderbooks, out)
            written = [json.loads(line) for line in out.read_text().splitlines()]

        self.assertEqual(count, 1)
        self.assertEqual(rows[0]["venue"], "kalshi")
        self.assertEqual(rows[0]["fee_rate"], 0.07)
        self.assertEqual(rows[0]["yes"]["bids"], [[0.45, 10.0], [0.4, 5.0]])
        self.assertEqual(rows[0]["yes"]["asks"], [[0.45, 8.0]])
        self.assertEqual(rows[0]["no"]["asks"], [[0.55, 10.0], [0.6, 5.0]])
        self.assertEqual(rows_from_lines, rows)
        self.assertEqual(written[0]["market_id"], "KXTEST")

    def test_kalshi_orderbooks_accept_orderbook_fp_payloads(self):
        row = json.dumps(
            {
                "type": "raw_kalshi_orderbook",
                "ts": "2026-05-09T00:00:00Z",
                "market_id": "KXTEST",
                "raw": {
                    "orderbook_fp": {
                        "yes_dollars": [["0.9100", "5.00"]],
                        "no_dollars": [["0.0700", "4.00"]],
                    }
                },
            }
        )

        snapshots = list(kalshi_binary_snapshot_rows_from_orderbook_lines([row]))

        self.assertEqual(snapshots[0]["yes"]["bids"], [[0.91, 5.0]])
        self.assertEqual(snapshots[0]["fee_rate"], 0.07)
        self.assertEqual(snapshots[0]["yes"]["asks"], [[0.93, 4.0]])
        self.assertEqual(snapshots[0]["no"]["asks"], [[0.09, 5.0]])

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
