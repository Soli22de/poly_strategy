import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional
from urllib.request import ProxyHandler, Request, build_opener, urlopen

from poly_strategy.alerts import read_opportunity_alerts


Sender = Callable[[str, dict, float, Optional[str]], dict]


def notify_alerts(
    alerts_path: Path,
    max_alerts: int = 20,
    webhook_url: Optional[str] = None,
    telegram_bot_token: Optional[str] = None,
    telegram_chat_id: Optional[str] = None,
    discord_webhook_url: Optional[str] = None,
    desktop: bool = False,
    dry_run: bool = False,
    timeout: float = 10.0,
    proxy: Optional[str] = None,
    webhook_sender: Optional[Sender] = None,
    desktop_sender: Optional[Callable[[str, str, bool], dict]] = None,
) -> list:
    if max_alerts < 0:
        raise ValueError("max_alerts must be non-negative")
    alerts = read_opportunity_alerts(alerts_path)[-max_alerts:]
    if not alerts:
        return []

    sender = webhook_sender or _post_json
    results = []
    for alert in alerts:
        text = format_alert_text(alert)
        payload = {"type": "poly_strategy_alert", "text": text, "alert": alert}
        if webhook_url:
            results.append(_notify_webhook("webhook", webhook_url, payload, dry_run, timeout, proxy, sender))
        if telegram_bot_token and telegram_chat_id:
            url = f"https://api.telegram.org/bot{telegram_bot_token}/sendMessage"
            results.append(
                _notify_webhook(
                    "telegram",
                    url,
                    {"chat_id": telegram_chat_id, "text": text, "disable_web_page_preview": True},
                    dry_run,
                    timeout,
                    proxy,
                    sender,
                )
            )
        if discord_webhook_url:
            results.append(_notify_webhook("discord", discord_webhook_url, {"content": text}, dry_run, timeout, proxy, sender))
        if desktop:
            send_desktop = desktop_sender or _send_desktop_notification
            response = send_desktop("PolyStrategy alert", text, dry_run)
            results.append(_notification_row("desktop", dry_run, response=response, alert=alert))
    return results


def format_alert_text(alert: dict) -> str:
    kind = alert.get("kind") or "unknown"
    alert_kind = alert.get("alert_kind") or "alert"
    edge = _fmt_float(alert.get("net_edge_per_share"))
    roi = _fmt_float(alert.get("paper_roi"))
    markets = ",".join(alert.get("market_ids") or []) or "unknown"
    return f"{alert_kind} {kind} edge={edge} roi={roi} markets={markets} key={alert.get('key') or ''}".strip()


def _notify_webhook(
    channel: str,
    url: str,
    payload: dict,
    dry_run: bool,
    timeout: float,
    proxy: Optional[str],
    sender: Sender,
) -> dict:
    if dry_run:
        return _notification_row(channel, dry_run, payload=payload)
    response = sender(url, payload, timeout, proxy)
    return _notification_row(channel, dry_run, response=response)


def _notification_row(
    channel: str,
    dry_run: bool,
    payload: Optional[dict] = None,
    response: Optional[dict] = None,
    alert: Optional[dict] = None,
) -> dict:
    row = {
        "type": "notification_result",
        "ts": _utc_now(),
        "channel": channel,
        "dry_run": dry_run,
        "status": "dry_run" if dry_run else "sent",
    }
    if payload is not None:
        row["payload"] = payload
    if response is not None:
        row["response"] = response
    if alert is not None:
        row["alert_key"] = alert.get("key")
        row["market_ids"] = alert.get("market_ids")
    return row


def _post_json(url: str, payload: dict, timeout: float, proxy: Optional[str] = None) -> dict:
    body = json.dumps(payload, sort_keys=True).encode("utf-8")
    request = Request(
        url,
        data=body,
        headers={"content-type": "application/json", "accept": "application/json", "user-agent": "poly-strategy/0.1"},
        method="POST",
    )
    if proxy:
        proxy_url = _normalize_proxy(proxy)
        opener = build_opener(ProxyHandler({"http": proxy_url, "https": proxy_url}))
        response_context = opener.open(request, timeout=timeout)
    else:
        response_context = urlopen(request, timeout=timeout)
    with response_context as response:
        raw_body = response.read().decode("utf-8")
        return {"status": getattr(response, "status", None), "body": _maybe_json(raw_body)}


def _send_desktop_notification(title: str, text: str, dry_run: bool = False) -> dict:
    if dry_run:
        return {"title": title, "text": text}
    script = 'display notification "{}" with title "{}"'.format(_escape_osascript(text), _escape_osascript(title))
    completed = subprocess.run(["osascript", "-e", script], check=True, capture_output=True, text=True)
    return {"returncode": completed.returncode, "stdout": completed.stdout, "stderr": completed.stderr}


def _maybe_json(text: str):
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def _fmt_float(value) -> str:
    if value is None or value == "":
        return "n/a"
    try:
        return f"{float(value):.6f}"
    except (TypeError, ValueError):
        return str(value)


def _escape_osascript(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _normalize_proxy(proxy: str) -> str:
    if "://" in proxy:
        return proxy
    return f"http://{proxy}"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
