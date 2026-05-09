import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urlencode, urlparse


ODDPOOL_API_BASE = "https://api.oddpool.com"
ODDPOOL_FREE_MONTHLY_REQUESTS = 1000
ODDPOOL_FREE_MIN_INTERVAL_SECONDS = 1.0


class OddpoolQuotaError(RuntimeError):
    pass


def oddpool_free_recent_markets_url(
    base_url: str = ODDPOOL_API_BASE,
    limit: int = 30,
    exchange: Optional[str] = None,
) -> str:
    params = {"limit": str(limit)}
    if exchange:
        params["exchange"] = exchange
    return f"{base_url.rstrip('/')}/search/recent/markets?{urlencode(params)}"


def oddpool_free_recent_events_url(
    base_url: str = ODDPOOL_API_BASE,
    limit: int = 30,
    exchange: Optional[str] = None,
) -> str:
    params = {"limit": str(limit)}
    if exchange:
        params["exchange"] = exchange
    return f"{base_url.rstrip('/')}/search/recent/events?{urlencode(params)}"


def oddpool_free_market_search_url(
    query: str,
    base_url: str = ODDPOOL_API_BASE,
    limit: int = 30,
    exchange: Optional[str] = None,
) -> str:
    params = {"q": query, "limit": str(limit)}
    if exchange:
        params["exchange"] = exchange
    return f"{base_url.rstrip('/')}/search/markets?{urlencode(params)}"


def is_oddpool_premium_url(url: str) -> bool:
    path = urlparse(str(url)).path.lower()
    return path.startswith("/arbitrage") or "/arbitrage/" in path


def reserve_oddpool_quota(
    state_path: Path,
    endpoint: str,
    monthly_limit: int = ODDPOOL_FREE_MONTHLY_REQUESTS,
    min_interval_seconds: float = ODDPOOL_FREE_MIN_INTERVAL_SECONDS,
    now: Optional[datetime] = None,
    sleep_for_rate_limit: bool = True,
) -> dict:
    if monthly_limit < 1:
        raise ValueError("monthly_limit must be at least 1")
    if min_interval_seconds < 0:
        raise ValueError("min_interval_seconds must be non-negative")

    now = now or datetime.now(timezone.utc)
    state = _read_quota_state(state_path)
    state = _reset_month_if_needed(state, now)

    wait_seconds = _quota_wait_seconds(state, now, min_interval_seconds)
    if wait_seconds > 0 and sleep_for_rate_limit:
        time.sleep(wait_seconds)
        now = datetime.now(timezone.utc)
        state = _reset_month_if_needed(_read_quota_state(state_path), now)
        wait_seconds = _quota_wait_seconds(state, now, min_interval_seconds)

    used = int(state.get("used") or 0)
    if used >= monthly_limit:
        raise OddpoolQuotaError(f"Oddpool monthly quota exhausted: used={used} limit={monthly_limit}")

    requests = list(state.get("recent_requests") or [])
    request_row = {"ts": _utc_iso(now), "endpoint": endpoint}
    requests.append(request_row)
    state.update(
        {
            "type": "oddpool_quota_state",
            "month": now.strftime("%Y-%m"),
            "used": used + 1,
            "monthly_limit": monthly_limit,
            "remaining": max(0, monthly_limit - used - 1),
            "last_request_at": request_row["ts"],
            "last_endpoint": endpoint,
            "min_interval_seconds": min_interval_seconds,
            "wait_seconds": wait_seconds,
            "recent_requests": requests[-20:],
        }
    )
    _write_quota_state(state_path, state)
    return dict(state)


def _quota_wait_seconds(state: dict, now: datetime, min_interval_seconds: float) -> float:
    last_request_at = state.get("last_request_at")
    if not last_request_at or min_interval_seconds <= 0:
        return 0.0
    try:
        last = datetime.fromisoformat(str(last_request_at).replace("Z", "+00:00"))
    except ValueError:
        return 0.0
    elapsed = (now - last).total_seconds()
    return max(0.0, min_interval_seconds - elapsed)


def _reset_month_if_needed(state: dict, now: datetime) -> dict:
    month = now.strftime("%Y-%m")
    if state.get("month") == month:
        return state
    return {"type": "oddpool_quota_state", "month": month, "used": 0, "recent_requests": []}


def _read_quota_state(path: Path) -> dict:
    if not path or not path.exists():
        return {}
    try:
        loaded = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _write_quota_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")
    tmp.replace(path)


def _utc_iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
