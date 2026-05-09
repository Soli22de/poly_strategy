import json
import tempfile
import unittest
from pathlib import Path

from poly_strategy.cross_platform import (
    cross_platform_signal_rows,
    match_polymarket_kalshi_markets,
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
        self.assertEqual(count, 1)
        self.assertEqual(written[0]["type"], "external_signal")
        self.assertEqual(written[0]["legs"][0]["venue"], "polymarket")


if __name__ == "__main__":
    unittest.main()
