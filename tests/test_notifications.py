import json
import tempfile
import unittest
from pathlib import Path

from poly_strategy.notifications import format_alert_text, notify_alerts


class NotificationTests(unittest.TestCase):
    def test_notify_alerts_builds_dry_run_rows_for_enabled_channels(self):
        with tempfile.TemporaryDirectory() as tmp:
            alerts = Path(tmp) / "alerts.ndjson"
            alerts.write_text(json.dumps(_alert("a")) + "\n")

            rows = notify_alerts(
                alerts,
                webhook_url="https://example.test/hook",
                telegram_bot_token="token",
                telegram_chat_id="chat",
                discord_webhook_url="https://discord.test/hook",
                desktop=True,
                dry_run=True,
            )

        self.assertEqual([row["channel"] for row in rows], ["webhook", "telegram", "discord", "desktop"])
        self.assertTrue(all(row["dry_run"] for row in rows))
        self.assertIn("edge=0.020000", rows[0]["payload"]["text"])

    def test_notify_alerts_uses_sender_when_not_dry_run(self):
        sent = []

        def sender(url, payload, timeout, proxy):
            sent.append((url, payload, timeout, proxy))
            return {"status": 200}

        with tempfile.TemporaryDirectory() as tmp:
            alerts = Path(tmp) / "alerts.ndjson"
            alerts.write_text(json.dumps(_alert("a")) + "\n")

            rows = notify_alerts(
                alerts,
                webhook_url="https://example.test/hook",
                dry_run=False,
                timeout=3,
                proxy="127.0.0.1:10808",
                webhook_sender=sender,
            )

        self.assertEqual(len(sent), 1)
        self.assertEqual(sent[0][0], "https://example.test/hook")
        self.assertEqual(sent[0][2], 3)
        self.assertEqual(sent[0][3], "127.0.0.1:10808")
        self.assertEqual(rows[0]["status"], "sent")

    def test_format_alert_text_is_compact(self):
        text = format_alert_text(_alert("a"))

        self.assertIn("stable_paper_trade", text)
        self.assertIn("yes_no_bundle", text)
        self.assertIn("m1,m2", text)


def _alert(key: str) -> dict:
    return {
        "type": "opportunity_alert",
        "alert_kind": "stable_paper_trade",
        "key": key,
        "kind": "yes_no_bundle",
        "market_ids": ["m1", "m2"],
        "net_edge_per_share": 0.02,
        "paper_roi": 0.03,
    }


if __name__ == "__main__":
    unittest.main()
