import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, List, Optional
from urllib.parse import urlencode
from urllib.request import ProxyHandler, Request, build_opener, urlopen


GAMMA_MARKETS_URL = "https://gamma-api.polymarket.com/markets"
POLYMARKET_CLOB_BOOK_URL = "https://clob.polymarket.com/book"


def write_sample_snapshot(path: Path) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "ts": _utc_now(),
        "type": "binary_snapshot",
        "venue": "polymarket",
        "market_id": "sample-yes-no-bundle",
        "fee_rate": 0.0,
        "yes": {"asks": [[0.45, 10], [0.46, 20]], "bids": [[0.44, 5]]},
        "no": {"asks": [[0.53, 7], [0.54, 30]], "bids": [[0.52, 5]]},
    }
    path.write_text(json.dumps(row, sort_keys=True) + "\n")
    return 1


def collect_polymarket_gamma(path: Path, limit: int, timeout: float, proxy: Optional[str] = None) -> int:
    params = urlencode({"active": "true", "closed": "false", "limit": str(limit)})
    rows = _fetch_json(f"{GAMMA_MARKETS_URL}?{params}", timeout, proxy=proxy)
    if not isinstance(rows, list):
        raise RuntimeError("unexpected Polymarket Gamma response")

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as handle:
        for row in rows:
            handle.write(
                json.dumps(
                    {
                        "ts": _utc_now(),
                        "type": "raw_polymarket_gamma_market",
                        "market_id": row.get("id") or row.get("conditionId"),
                        "raw": row,
                    },
                    sort_keys=True,
                )
                + "\n"
            )
    return len(rows)


def collect_polymarket_books(path: Path, token_ids: Iterable[str], timeout: float, proxy: Optional[str] = None) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("a") as handle:
        for token_id in token_ids:
            params = urlencode({"token_id": token_id})
            row = _fetch_json(f"{POLYMARKET_CLOB_BOOK_URL}?{params}", timeout, proxy=proxy)
            handle.write(
                json.dumps(
                    {
                        "ts": _utc_now(),
                        "type": "raw_polymarket_clob_book",
                        "token_id": token_id,
                        "raw": row,
                    },
                    sort_keys=True,
                )
                + "\n"
            )
            count += 1
    return count


def collect_polymarket_binary_snapshots(
    path: Path,
    limit: int,
    timeout: float,
    proxy: Optional[str] = None,
) -> int:
    params = urlencode({"active": "true", "closed": "false", "limit": str(limit)})
    markets = _fetch_json(f"{GAMMA_MARKETS_URL}?{params}", timeout, proxy=proxy)
    if not isinstance(markets, list):
        raise RuntimeError("unexpected Polymarket Gamma response")

    def fetch_book(token_id: str) -> dict:
        book_params = urlencode({"token_id": token_id})
        return _fetch_json(f"{POLYMARKET_CLOB_BOOK_URL}?{book_params}", timeout, proxy=proxy)

    rows = binary_snapshot_rows_from_gamma_markets(markets, fetch_book)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    return len(rows)


def collect_polymarket_binary_snapshots_loop(
    path: Path,
    limit: int,
    timeout: float,
    proxy: Optional[str],
    interval_seconds: float,
    iterations: int,
    collect_once: Callable[[Path, int, float, Optional[str]], int] = collect_polymarket_binary_snapshots,
    sleep: Callable[[float], None] = time.sleep,
) -> int:
    if iterations < 1:
        raise ValueError("iterations must be at least 1")
    if interval_seconds < 0:
        raise ValueError("interval_seconds must be non-negative")

    total = 0
    for index in range(iterations):
        total += collect_once(path, limit, timeout, proxy)
        if index < iterations - 1 and interval_seconds > 0:
            sleep(interval_seconds)
    return total


def binary_snapshot_rows_from_gamma_markets(
    markets: Iterable[dict],
    book_fetcher: Callable[[str], dict],
) -> List[dict]:
    rows = []
    for market in markets:
        if not _is_binary_market(market):
            continue
        token_ids = _loads_json_list(market.get("clobTokenIds"))
        if len(token_ids) != 2:
            continue

        yes_book = _normalized_book(book_fetcher(str(token_ids[0])))
        no_book = _normalized_book(book_fetcher(str(token_ids[1])))
        yes_book["token_id"] = str(token_ids[0])
        no_book["token_id"] = str(token_ids[1])
        rows.append(
            {
                "ts": _utc_now(),
                "type": "binary_snapshot",
                "venue": "polymarket",
                "market_id": str(market.get("id") or market.get("conditionId")),
                "question": market.get("question"),
                "fee_rate": _market_fee_rate(market),
                "yes": yes_book,
                "no": no_book,
            }
        )
    return rows


def _fetch_json(url: str, timeout: float, proxy: Optional[str] = None):
    request = Request(url, headers={"accept": "application/json", "user-agent": "poly-strategy/0.1"})
    if proxy:
        proxy_url = _normalize_proxy(proxy)
        opener = build_opener(ProxyHandler({"http": proxy_url, "https": proxy_url}))
        response_context = opener.open(request, timeout=timeout)
    else:
        response_context = urlopen(request, timeout=timeout)
    with response_context as response:
        return json.loads(response.read().decode("utf-8"))


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _normalize_proxy(proxy: str) -> str:
    if "://" in proxy:
        return proxy
    return f"http://{proxy}"


def _is_binary_market(market: dict) -> bool:
    if market.get("closed") is True:
        return False
    if market.get("enableOrderBook") is False:
        return False
    if market.get("acceptingOrders") is False:
        return False
    outcomes = _loads_json_list(market.get("outcomes"))
    return [str(outcome).lower() for outcome in outcomes] == ["yes", "no"]


def _loads_json_list(value) -> List[str]:
    if isinstance(value, list):
        return value
    if not value:
        return []
    return json.loads(value)


def _market_fee_rate(market: dict) -> float:
    if not market.get("feesEnabled"):
        return 0.0
    fee_schedule = market.get("feeSchedule") or {}
    return float(fee_schedule.get("rate") or 0.0)


def _normalized_book(book: dict) -> dict:
    return {
        "asks": _levels(book.get("asks", []), reverse=False),
        "bids": _levels(book.get("bids", []), reverse=True),
    }


def _levels(levels: Iterable[dict], reverse: bool) -> List[List[float]]:
    parsed = [[float(level["price"]), float(level["size"])] for level in levels]
    parsed.sort(key=lambda level: level[0], reverse=reverse)
    return parsed
