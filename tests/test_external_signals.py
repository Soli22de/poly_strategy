import json
import tempfile
import unittest
from pathlib import Path

from poly_strategy.external_signals import external_signal_report, ingest_external_signals


class ExternalSignalTests(unittest.TestCase):
    def test_ingest_external_signals_normalizes_json_payloads(self):
        payload = {
            "signals": [
                {
                    "id": "sig-1",
                    "strategy": "cross_platform",
                    "event": "Fed decision",
                    "edge": 0.05,
                    "roi": 0.08,
                    "legs": [
                        {"platform": "Polymarket", "marketId": "poly-1", "outcome": "YES", "ask": 0.45, "depth": 100},
                        {"platform": "Kalshi", "ticker": "kalshi-1", "outcome": "NO", "ask": 0.50, "depth": 90},
                    ],
                }
            ]
        }

        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "signals.json"
            out = Path(tmp) / "external.ndjson"
            source.write_text(json.dumps(payload))

            count = ingest_external_signals(out, "oddpool", input_path=source)
            row = json.loads(out.read_text().splitlines()[0])

        self.assertEqual(count, 1)
        self.assertEqual(row["type"], "external_signal")
        self.assertEqual(row["source"], "oddpool")
        self.assertEqual(row["source_id"], "sig-1")
        self.assertEqual(row["kind"], "cross_platform")
        self.assertEqual(row["quoted_edge"], 0.05)
        self.assertEqual(row["legs"][0]["venue"], "polymarket")
        self.assertEqual(row["legs"][1]["market_id"], "kalshi-1")


    def test_ingest_external_signals_supports_oddpool_current_shape(self):
        payload = {
            "arbitrages": [
                {
                    "id": "arb-1",
                    "net_cents": 1.25,
                    "roi": 0.04,
                    "depth": 200,
                    "platforms": [
                        {"platform": "Polymarket", "market_id": "poly-1", "outcome": "YES", "best_ask": 0.48},
                        {"platform": "Kalshi", "ticker": "KXTEST", "outcome": "NO", "best_ask": 0.50},
                    ],
                }
            ]
        }

        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "oddpool.json"
            out = Path(tmp) / "external.ndjson"
            source.write_text(json.dumps(payload))

            count = ingest_external_signals(out, "oddpool", input_path=source)
            row = json.loads(out.read_text().splitlines()[0])

        self.assertEqual(count, 1)
        self.assertEqual(row["source"], "oddpool")
        self.assertEqual(row["source_id"], "arb-1")
        self.assertEqual(row["quoted_edge"], 0.0125)
        self.assertEqual(row["quoted_depth"], 200)
        self.assertEqual([leg["venue"] for leg in row["legs"]], ["polymarket", "kalshi"])

    def test_external_signal_report_summarizes_sources_and_venues(self):
        rows = [
            {
                "type": "external_signal",
                "source": "oddpool",
                "source_id": "a",
                "kind": "cross_platform",
                "quoted_edge": 0.04,
                "quoted_roi": 0.05,
                "legs": [{"venue": "polymarket"}, {"venue": "kalshi"}],
            },
            {
                "type": "external_signal",
                "source": "custom",
                "source_id": "b",
                "kind": "basket",
                "quoted_edge": 0.10,
                "legs": [{"venue": "polymarket"}],
            },
        ]

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "external.ndjson"
            path.write_text("\n".join(json.dumps(row) for row in rows) + "\n")

            report = external_signal_report(path)

        self.assertEqual(report["signal_count"], 2)
        self.assertEqual(report["by_source"][0]["source"], "custom")
        self.assertEqual(report["top"][0]["source_id"], "b")
        self.assertIn({"venue_pair": "kalshi+polymarket", "count": 1}, report["by_venue_pair"])


if __name__ == "__main__":
    unittest.main()
