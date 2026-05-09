import asyncio
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

from poly_strategy.orderbook import Level


POLYMARKET_MARKET_WS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
KALSHI_PROD_WS_URL = "wss://external-api-ws.kalshi.com/trade-api/ws/v2"
KALSHI_DEMO_WS_URL = "wss://external-api-ws.demo.kalshi.co/trade-api/ws/v2"


def polymarket_subscription_payload(asset_ids: Iterable[str], custom_feature_enabled: bool = True) -> dict:
    ids = [str(asset_id) for asset_id in dict.fromkeys(asset_ids) if asset_id]
    if not ids:
        raise ValueError("asset_ids cannot be empty")
    return {
        "assets_ids": ids,
        "type": "market",
        "custom_feature_enabled": custom_feature_enabled,
    }


def kalshi_orderbook_subscription_payload(
    market_tickers: Iterable[str],
    command_id: int = 1,
    use_yes_price: bool = True,
) -> dict:
    tickers = [str(ticker) for ticker in dict.fromkeys(market_tickers) if ticker]
    if not tickers:
        raise ValueError("market_tickers cannot be empty")
    params = {
        "channels": ["orderbook_delta"],
        "use_yes_price": use_yes_price,
    }
    if len(tickers) == 1:
        params["market_ticker"] = tickers[0]
    else:
        params["market_tickers"] = tickers
    return {"id": command_id, "cmd": "subscribe", "params": params}


class RealtimeOrderBookStore:
    def __init__(self):
        self._books = {}
        self.last_update_ts = None

    def apply_polymarket_message(self, message: dict) -> list:
        if isinstance(message, list):
            rows = []
            for item in message:
                rows.extend(self.apply_polymarket_message(item))
            return rows
        event_type = message.get("event_type")
        if event_type == "book":
            return [self._apply_polymarket_book(message)]
        if event_type == "price_change":
            return self._apply_polymarket_price_change(message)
        if event_type == "best_bid_ask":
            return [self._polymarket_best_bid_ask_row(message)]
        return []

    def book(self, token_id: str) -> dict:
        book = self._books.get(str(token_id), {"bids": {}, "asks": {}})
        return {
            "bids": _sorted_levels(book["bids"], reverse=True),
            "asks": _sorted_levels(book["asks"], reverse=False),
        }

    def binary_snapshot_row(self, market: dict, ts: Optional[str] = None) -> Optional[dict]:
        yes_token_id = market.get("yes_token_id")
        no_token_id = market.get("no_token_id")
        if not yes_token_id or not no_token_id:
            return None
        yes_book = self.book(yes_token_id)
        no_book = self.book(no_token_id)
        if not yes_book["asks"] or not no_book["asks"]:
            return None
        return {
            "ts": ts or self.last_update_ts or _utc_now(),
            "type": "binary_snapshot",
            "venue": "polymarket",
            "market_id": market["market_id"],
            "question": market.get("question"),
            "fee_rate": float(market.get("fee_rate") or 0.0),
            "yes": {"token_id": yes_token_id, "asks": _row_levels(yes_book["asks"]), "bids": _row_levels(yes_book["bids"])},
            "no": {"token_id": no_token_id, "asks": _row_levels(no_book["asks"]), "bids": _row_levels(no_book["bids"])},
        }

    def binary_snapshot_rows(self, markets: Iterable[dict], ts: Optional[str] = None) -> list:
        rows = []
        snapshot_ts = ts or self.last_update_ts or _utc_now()
        for market in markets:
            row = self.binary_snapshot_row(market, ts=snapshot_ts)
            if row is not None:
                rows.append(row)
        return rows

    def _apply_polymarket_book(self, message: dict) -> dict:
        token_id = str(message["asset_id"])
        bids = _levels_dict(message.get("bids", []))
        asks = _levels_dict(message.get("asks", []))
        self._books[token_id] = {"bids": bids, "asks": asks}
        self.last_update_ts = _timestamp_to_iso(message.get("timestamp"))
        return _update_row("polymarket", token_id, message.get("market"), "book", self.book(token_id), self.last_update_ts, message)

    def _apply_polymarket_price_change(self, message: dict) -> list:
        rows = []
        self.last_update_ts = _timestamp_to_iso(message.get("timestamp"))
        for change in message.get("price_changes", []):
            token_id = str(change.get("asset_id") or "")
            if not token_id:
                continue
            book = self._books.setdefault(token_id, {"bids": {}, "asks": {}})
            side = "bids" if str(change.get("side") or "").upper() == "BUY" else "asks"
            price = float(change["price"])
            size = float(change["size"])
            if size <= 0:
                book[side].pop(price, None)
            else:
                book[side][price] = size
            rows.append(_update_row("polymarket", token_id, message.get("market"), "price_change", self.book(token_id), self.last_update_ts, change))
        return rows

    def _polymarket_best_bid_ask_row(self, message: dict) -> dict:
        token_id = str(message.get("asset_id") or "")
        ts = _timestamp_to_iso(message.get("timestamp"))
        self.last_update_ts = ts
        return {
            "type": "realtime_best_bid_ask",
            "venue": "polymarket",
            "token_id": token_id,
            "market": message.get("market"),
            "best_bid": _optional_float(message.get("best_bid")),
            "best_ask": _optional_float(message.get("best_ask")),
            "spread": _optional_float(message.get("spread")),
            "ts": ts,
            "raw": message,
        }


def load_watchlist_markets(path: Path) -> list:
    row = json.loads(path.read_text())
    if row.get("type") != "polymarket_watchlist":
        raise ValueError("watchlist type must be polymarket_watchlist")
    markets = row.get("markets")
    if not isinstance(markets, list):
        raise ValueError("watchlist markets must be a list")
    return markets


def token_ids_from_watchlist(markets: Iterable[dict]) -> list:
    token_ids = []
    for market in markets:
        for key in ["yes_token_id", "no_token_id"]:
            token_id = market.get(key)
            if token_id:
                token_ids.append(str(token_id))
    return list(dict.fromkeys(token_ids))


def stream_polymarket_watchlist(
    watchlist_path: Path,
    out_path: Path,
    snapshot_out_path: Optional[Path] = None,
    max_messages: Optional[int] = None,
    snapshot_interval_seconds: Optional[float] = 2.0,
    url: str = POLYMARKET_MARKET_WS_URL,
) -> int:
    return asyncio.run(
        _stream_polymarket_watchlist(
            watchlist_path,
            out_path,
            snapshot_out_path=snapshot_out_path,
            max_messages=max_messages,
            snapshot_interval_seconds=snapshot_interval_seconds,
            url=url,
        )
    )


async def _stream_polymarket_watchlist(
    watchlist_path: Path,
    out_path: Path,
    snapshot_out_path: Optional[Path],
    max_messages: Optional[int],
    snapshot_interval_seconds: Optional[float],
    url: str,
) -> int:
    if max_messages is not None and max_messages < 1:
        raise ValueError("max_messages must be at least 1")
    if snapshot_interval_seconds is not None and snapshot_interval_seconds < 0:
        raise ValueError("snapshot_interval_seconds must be non-negative")
    try:
        import websockets
    except ImportError as exc:
        raise RuntimeError("install websockets to use stream-polymarket-watchlist") from exc

    markets = load_watchlist_markets(watchlist_path)
    payload = polymarket_subscription_payload(token_ids_from_watchlist(markets))
    store = RealtimeOrderBookStore()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if snapshot_out_path:
        snapshot_out_path.parent.mkdir(parents=True, exist_ok=True)

    count = 0
    last_snapshot_at = None
    async with websockets.connect(url) as websocket:
        await websocket.send(json.dumps(payload))
        with out_path.open("a") as update_handle:
            snapshot_handle = snapshot_out_path.open("a") if snapshot_out_path else None
            try:
                async for raw_message in websocket:
                    message = json.loads(raw_message)
                    rows = store.apply_polymarket_message(message)
                    for row in rows:
                        update_handle.write(json.dumps(row, sort_keys=True) + "\n")
                    update_handle.flush()
                    if snapshot_handle and _should_write_snapshot(last_snapshot_at, snapshot_interval_seconds):
                        snapshot_rows = store.binary_snapshot_rows(markets)
                        for row in snapshot_rows:
                            snapshot_handle.write(json.dumps(row, sort_keys=True) + "\n")
                        if snapshot_rows:
                            snapshot_handle.flush()
                            last_snapshot_at = time.monotonic()
                    count += 1
                    if max_messages is not None and count >= max_messages:
                        break
            finally:
                if snapshot_handle:
                    snapshot_handle.close()
    return count


def _levels_dict(levels: Iterable[dict]) -> dict:
    return {float(level["price"]): float(level["size"]) for level in levels if float(level.get("size", 0)) > 0}


def _sorted_levels(levels: dict, reverse: bool) -> list:
    return [Level(price, size) for price, size in sorted(levels.items(), key=lambda item: item[0], reverse=reverse)]


def _row_levels(levels: Iterable[Level]) -> list:
    return [[level.price, level.size] for level in levels]


def _should_write_snapshot(last_snapshot_at: Optional[float], interval_seconds: Optional[float]) -> bool:
    if interval_seconds is None or interval_seconds == 0:
        return True
    if last_snapshot_at is None:
        return True
    return time.monotonic() - last_snapshot_at >= interval_seconds


def _update_row(venue: str, token_id: str, market: Optional[str], event_type: str, book: dict, ts: str, raw: dict) -> dict:
    return {
        "type": "realtime_orderbook_update",
        "venue": venue,
        "token_id": token_id,
        "market": market,
        "event_type": event_type,
        "ts": ts,
        "best_bid": book["bids"][0].price if book["bids"] else None,
        "best_ask": book["asks"][0].price if book["asks"] else None,
        "bid_levels": _row_levels(book["bids"]),
        "ask_levels": _row_levels(book["asks"]),
        "raw": raw,
    }


def _timestamp_to_iso(value) -> str:
    if value is None or value == "":
        return _utc_now()
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return str(value)
    seconds = numeric / 1000.0 if numeric > 100000000000 else numeric
    return datetime.fromtimestamp(seconds, timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _optional_float(value):
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
