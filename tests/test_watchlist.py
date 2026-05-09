import json
import tempfile
import unittest
from pathlib import Path

from poly_strategy.watchlist import build_polymarket_watchlist, write_watchlist


class WatchlistTests(unittest.TestCase):
    def test_build_polymarket_watchlist_expands_neg_risk_group_tokens(self):
        gamma_rows = [
            _gamma_row("a", "group-1", ["a-yes", "a-no"], "0"),
            _gamma_row("b", "group-1", ["b-yes", "b-no"], "1"),
            _gamma_row("unused", "group-2", ["unused-yes", "unused-no"], "0"),
        ]
        rules = {"mutually_exclusive": [{"first": "a", "second": "a"}]}

        with tempfile.TemporaryDirectory() as tmp:
            gamma_path = Path(tmp) / "gamma.ndjson"
            rules_path = Path(tmp) / "rules.json"
            out = Path(tmp) / "watchlist.json"
            gamma_path.write_text("\n".join(json.dumps(row) for row in gamma_rows) + "\n")
            rules_path.write_text(json.dumps(rules))

            rows = build_polymarket_watchlist(gamma_path, rules_path)
            count = write_watchlist(rows, out)
            written = json.loads(out.read_text())

        self.assertEqual(count, 2)
        self.assertEqual([row["market_id"] for row in rows], ["a", "b"])
        self.assertEqual(rows[0]["yes_token_id"], "a-yes")
        self.assertEqual(rows[0]["fee_rate"], 0.03)
        self.assertEqual(written["type"], "polymarket_watchlist")
        self.assertEqual(len(written["markets"]), 2)


def _gamma_row(market_id: str, group_id: str, token_ids: list, threshold: str):
    return {
        "type": "raw_polymarket_gamma_market",
        "market_id": market_id,
        "raw": {
            "id": market_id,
            "question": f"{market_id} wins?",
            "negRisk": True,
            "negRiskMarketID": group_id,
            "groupItemTitle": market_id.upper(),
            "groupItemThreshold": threshold,
            "clobTokenIds": json.dumps(token_ids),
            "feesEnabled": True,
            "feeSchedule": {"rate": 0.03},
        },
    }


if __name__ == "__main__":
    unittest.main()
