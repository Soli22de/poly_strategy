import json
import tempfile
import unittest
from pathlib import Path

from poly_strategy.cross_platform import (
    apply_cross_platform_verifications,
    cross_platform_pairs,
    cross_platform_signal_rows,
    event_tickers_from_cross_platform_candidates,
    expand_cross_platform_event_candidates,
    match_polymarket_kalshi_markets,
    normalize_cross_platform_match_report,
    opportunity_match_report_from_scan,
    write_cross_platform_signal_rows,
)


class CrossPlatformTests(unittest.TestCase):
    def test_match_polymarket_kalshi_markets_uses_title_overlap(self):
        with tempfile.TemporaryDirectory() as tmp:
            poly = Path(tmp) / "poly.ndjson"
            kalshi = Path(tmp) / "kalshi.ndjson"
            signals = Path(tmp) / "signals.ndjson"
            poly.write_text(
                json.dumps(
                    {
                        "type": "raw_polymarket_gamma_market",
                        "market_id": "pm1",
                        "raw": {"id": "pm1", "question": "Will Bitcoin hit 100k in 2026?"},
                    }
                )
                + "\n"
            )
            kalshi.write_text(
                json.dumps(
                    {
                        "type": "raw_kalshi_market",
                        "market_id": "KXBTC100K",
                        "raw": {"ticker": "KXBTC100K", "title": "Will Bitcoin hit 100k in 2026?"},
                    }
                )
                + "\n"
            )

            report = match_polymarket_kalshi_markets(poly, kalshi, min_score=0.5)
            signal_rows = cross_platform_signal_rows(report)
            count = write_cross_platform_signal_rows(signal_rows, signals)
            written = [json.loads(line) for line in signals.read_text().splitlines()]

        self.assertEqual(report["match_count"], 1)
        self.assertEqual(report["top"][0]["kalshi_ticker"], "KXBTC100K")
        self.assertEqual(report["top"][0]["status"], "verified_same_binary_event")
        self.assertTrue(report["top"][0]["trade_allowed"])
        self.assertEqual(count, 1)
        self.assertEqual(written[0]["type"], "external_signal")
        self.assertEqual(written[0]["kind"], "cross_platform_same_binary_verified")
        self.assertEqual(written[0]["legs"][0]["venue"], "polymarket")
        self.assertEqual(written[0]["legs"][0]["token"], "BINARY")
        self.assertEqual(written[0]["legs"][0]["side"], "watch")

    def test_cross_platform_unverified_matches_are_not_executable_legs(self):
        report = {
            "top": [
                {
                    "polymarket_market_id": "pm1",
                    "polymarket_title": "Will Bitcoin hit 100k in 2026?",
                    "kalshi_ticker": "KXELECTION",
                    "kalshi_title": "Will a candidate win the election?",
                    "score": 0.40,
                    "status": "candidate_needs_llm_or_manual_verification",
                    "trade_allowed": False,
                }
            ]
        }

        rows = cross_platform_signal_rows(report)
        verified_rows = cross_platform_signal_rows(report, verified_only=True)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["kind"], "cross_platform_candidate_unverified")
        self.assertEqual(rows[0]["legs"][0]["token"], None)
        self.assertEqual(rows[0]["legs"][0]["side"], "watch")
        self.assertEqual(verified_rows, [])

    def test_cross_platform_pairs_filters_unverified_by_default(self):
        report = {
            "top": [
                {
                    "polymarket_market_id": "verified-poly",
                    "kalshi_ticker": "KXVERIFIED",
                    "trade_allowed": True,
                },
                {
                    "polymarket_market_id": "unverified-poly",
                    "kalshi_ticker": "KXUNVERIFIED",
                    "trade_allowed": False,
                },
            ]
        }

        verified = cross_platform_pairs(report)
        all_pairs = cross_platform_pairs(report, verified_only=False)

        self.assertEqual([pair["polymarket_market_id"] for pair in verified], ["verified-poly"])
        self.assertEqual(len(all_pairs), 2)

    def test_apply_cross_platform_verifications_updates_trade_allowed(self):
        report = {
            "top": [
                {
                    "polymarket_market_id": "pm1",
                    "kalshi_ticker": "KX1",
                    "trade_allowed": False,
                    "status": "candidate_needs_llm_or_manual_verification",
                },
                {
                    "polymarket_market_id": "pm2",
                    "kalshi_ticker": "KX2",
                    "trade_allowed": False,
                    "status": "candidate_needs_llm_or_manual_verification",
                },
            ]
        }

        updated = apply_cross_platform_verifications(
            report,
            [
                {
                    "polymarket_market_id": "pm1",
                    "kalshi_ticker": "KX1",
                    "trade_allowed": True,
                    "confidence": 0.99,
                    "risk_flags": [],
                    "reason": "same market",
                }
            ],
        )

        self.assertTrue(updated["top"][0]["trade_allowed"])
        self.assertEqual(updated["top"][0]["status"], "verified_same_binary_event")
        self.assertEqual(updated["top"][1]["status"], "candidate_needs_llm_or_manual_verification")
        self.assertEqual(updated["llm_verified_count"], 1)
        self.assertEqual(updated["llm_rejected_count"], 0)

    def test_normalize_candidate_file_keeps_event_candidate_unexecutable(self):
        report = normalize_cross_platform_match_report(
            {
                "candidates": [
                    {
                        "polymarket_market_id": "pm1",
                        "polymarket_question": "Will Lionel Messi play in the 2026 FIFA World Cup?",
                        "kalshi_event_ticker": "KXSOCCERPLAYMESSI-26",
                        "kalshi_title": "Will Lionel Messi play in the World Cup? In 2026",
                        "score": 0.9,
                    }
                ]
            }
        )

        self.assertEqual(report["top"][0]["kalshi_event_ticker"], "KXSOCCERPLAYMESSI-26")
        self.assertEqual(report["top"][0]["kalshi_ticker"], "")
        self.assertEqual(report["top"][0]["status"], "candidate_needs_market_expansion")
        self.assertEqual(
            event_tickers_from_cross_platform_candidates(
                {"candidates": [{"kalshi_event_ticker": "KXSOCCERPLAYMESSI-26"}]}
            ),
            ["KXSOCCERPLAYMESSI-26"],
        )

    def test_expand_event_candidates_uses_real_kalshi_market_tickers(self):
        with tempfile.TemporaryDirectory() as tmp:
            kalshi = Path(tmp) / "kalshi.ndjson"
            kalshi.write_text(
                json.dumps(
                    {
                        "type": "raw_kalshi_market",
                        "market_id": "KXSOCCERPLAYMESSI-26",
                        "raw": {
                            "ticker": "KXSOCCERPLAYMESSI-26",
                            "event_ticker": "KXSOCCERPLAYMESSI-26",
                            "title": "Will Lionel Messi play in the World Cup?",
                            "yes_sub_title": "Yes",
                            "no_sub_title": "Yes",
                            "rules_primary": "If Lionel Messi is on the final squad for World Cup 2026, resolves Yes.",
                        },
                    }
                )
                + "\n"
            )

            report = expand_cross_platform_event_candidates(
                {
                    "candidates": [
                        {
                            "polymarket_market_id": "pm1",
                            "polymarket_question": "Will Lionel Messi play in the 2026 FIFA World Cup?",
                            "kalshi_event_ticker": "KXSOCCERPLAYMESSI-26",
                            "kalshi_title": "Will Lionel Messi play in the World Cup? In 2026",
                            "score": 0.9,
                        }
                    ]
                },
                kalshi,
            )

        self.assertEqual(report["match_count"], 1)
        self.assertEqual(report["top"][0]["kalshi_ticker"], "KXSOCCERPLAYMESSI-26")
        self.assertEqual(report["top"][0]["kalshi_event_ticker"], "KXSOCCERPLAYMESSI-26")
        self.assertEqual(report["top"][0]["status"], "candidate_needs_llm_or_manual_verification")

    def test_opportunity_match_report_filters_option_mismatches(self):
        match_report = {
            "top": [
                {
                    "polymarket_market_id": "pm-good",
                    "polymarket_question": "Will David Lisnard win the 2027 French presidential election?",
                    "kalshi_ticker": "KXFRENCH-DLIS",
                    "kalshi_title": "Will David Lisnard win the 2027 French presidential election?",
                    "source_kalshi_market": {"yes_sub_title": "David Lisnard"},
                },
                {
                    "polymarket_market_id": "pm-bad",
                    "polymarket_question": "Will Pedri win the 2026 Ballon d'Or?",
                    "kalshi_ticker": "KXBALLON-HKAN",
                    "kalshi_title": "Who will win the Ballon d'Or in 2026? | Harry Kane",
                    "source_kalshi_market": {"yes_sub_title": "Harry Kane"},
                },
            ]
        }
        scan_report = {
            "opportunities": [
                {
                    "net_edge_per_share": 0.02,
                    "total_edge": 2.0,
                    "quantity": 100,
                    "pair": {"polymarket_market_id": "pm-bad", "kalshi_ticker": "KXBALLON-HKAN"},
                },
                {
                    "net_edge_per_share": 0.01,
                    "total_edge": 1.0,
                    "quantity": 100,
                    "pair": {"polymarket_market_id": "pm-good", "kalshi_ticker": "KXFRENCH-DLIS"},
                },
            ]
        }

        filtered = opportunity_match_report_from_scan(scan_report, match_report, min_net_edge=0.005)

        self.assertEqual(filtered["match_count"], 1)
        self.assertEqual(filtered["top"][0]["polymarket_market_id"], "pm-good")
        self.assertTrue(filtered["top"][0]["option_match"])


if __name__ == "__main__":
    unittest.main()
