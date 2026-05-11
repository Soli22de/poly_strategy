import asyncio
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, Optional

from poly_strategy.backtest import load_rule_set, snapshot_from_row
from poly_strategy.collectors import fetch_polymarket_books_by_token_id
from poly_strategy.monitoring import IncrementalReplayState, stable_current_opportunities
from poly_strategy.orderbook import Level
from poly_strategy.paper import opportunity_to_row, select_paper_trades, trade_to_row


POLYMARKET_MARKET_WS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
KALSHI_PROD_WS_URL = "wss://external-api-ws.kalshi.com/trade-api/ws/v2"
KALSHI_DEMO_WS_URL = "wss://external-api-ws.demo.kalshi.co/trade-api/ws/v2"
DEFAULT_WS_MAX_SIZE = 4 * 1024 * 1024


class RealtimeStaleError(RuntimeError):
    pass


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

    @property
    def token_count(self) -> int:
        return len(self._books)

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

    def seed_polymarket_book(self, token_id: str, book: dict, ts: Optional[str] = None) -> dict:
        normalized_token_id = str(token_id)
        self._books[normalized_token_id] = {
            "bids": _levels_dict(book.get("bids", [])),
            "asks": _levels_dict(book.get("asks", [])),
        }
        self.last_update_ts = ts or _utc_now()
        return _update_row("polymarket", normalized_token_id, None, "seed_book", self.book(normalized_token_id), self.last_update_ts, book)

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
        if not yes_book["asks"] and not no_book["asks"]:
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
    ws_max_size: Optional[int] = DEFAULT_WS_MAX_SIZE,
    url: str = POLYMARKET_MARKET_WS_URL,
) -> int:
    return asyncio.run(
        _stream_polymarket_watchlist(
            watchlist_path,
            out_path,
            snapshot_out_path=snapshot_out_path,
            max_messages=max_messages,
            snapshot_interval_seconds=snapshot_interval_seconds,
            ws_max_size=ws_max_size,
            url=url,
        )
    )


def monitor_polymarket_watchlist(
    watchlist_path: Path,
    report_out_path: Path,
    rules_path: Optional[Path] = None,
    gamma_path: Optional[Path] = None,
    updates_out_path: Optional[Path] = None,
    snapshots_out_path: Optional[Path] = None,
    latest_snapshots_out_path: Optional[Path] = None,
    max_messages: Optional[int] = None,
    max_iterations: Optional[int] = None,
    snapshot_interval_seconds: Optional[float] = 2.0,
    stale_timeout_seconds: Optional[float] = 30.0,
    reconnect_delay_seconds: float = 2.0,
    max_reconnects: Optional[int] = None,
    min_net_edge: float = 0.0,
    max_capital_per_trade: Optional[float] = None,
    bankroll: Optional[float] = None,
    min_paper_roi: Optional[float] = None,
    min_paper_edge: Optional[float] = None,
    min_paper_quantity: float = 1e-9,
    min_run_observations: int = 1,
    min_run_seconds: float = 0.0,
    max_opportunities_per_iteration: int = 10,
    ws_max_size: Optional[int] = DEFAULT_WS_MAX_SIZE,
    url: str = POLYMARKET_MARKET_WS_URL,
    seed_orderbooks: bool = False,
    seed_timeout: float = 10.0,
    seed_proxy: Optional[str] = None,
    seed_max_workers: int = 8,
    progress: Optional[Callable[[dict], None]] = None,
) -> dict:
    return asyncio.run(
        _monitor_polymarket_watchlist(
            watchlist_path,
            report_out_path,
            rules_path=rules_path,
            gamma_path=gamma_path,
            updates_out_path=updates_out_path,
            snapshots_out_path=snapshots_out_path,
            latest_snapshots_out_path=latest_snapshots_out_path,
            max_messages=max_messages,
            max_iterations=max_iterations,
            snapshot_interval_seconds=snapshot_interval_seconds,
            stale_timeout_seconds=stale_timeout_seconds,
            reconnect_delay_seconds=reconnect_delay_seconds,
            max_reconnects=max_reconnects,
            min_net_edge=min_net_edge,
            max_capital_per_trade=max_capital_per_trade,
            bankroll=bankroll,
            min_paper_roi=min_paper_roi,
            min_paper_edge=min_paper_edge,
            min_paper_quantity=min_paper_quantity,
            min_run_observations=min_run_observations,
            min_run_seconds=min_run_seconds,
            max_opportunities_per_iteration=max_opportunities_per_iteration,
            ws_max_size=ws_max_size,
            url=url,
            seed_orderbooks=seed_orderbooks,
            seed_timeout=seed_timeout,
            seed_proxy=seed_proxy,
            seed_max_workers=seed_max_workers,
            progress=progress,
        )
    )


async def _stream_polymarket_watchlist(
    watchlist_path: Path,
    out_path: Path,
    snapshot_out_path: Optional[Path],
    max_messages: Optional[int],
    snapshot_interval_seconds: Optional[float],
    ws_max_size: Optional[int],
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
    async with websockets.connect(url, max_size=ws_max_size) as websocket:
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


async def _monitor_polymarket_watchlist(
    watchlist_path: Path,
    report_out_path: Path,
    rules_path: Optional[Path],
    gamma_path: Optional[Path],
    updates_out_path: Optional[Path],
    snapshots_out_path: Optional[Path],
    latest_snapshots_out_path: Optional[Path],
    max_messages: Optional[int],
    max_iterations: Optional[int],
    snapshot_interval_seconds: Optional[float],
    stale_timeout_seconds: Optional[float],
    reconnect_delay_seconds: float,
    max_reconnects: Optional[int],
    min_net_edge: float,
    max_capital_per_trade: Optional[float],
    bankroll: Optional[float],
    min_paper_roi: Optional[float],
    min_paper_edge: Optional[float],
    min_paper_quantity: float,
    min_run_observations: int,
    min_run_seconds: float,
    max_opportunities_per_iteration: int,
    ws_max_size: Optional[int],
    url: str,
    seed_orderbooks: bool,
    seed_timeout: float,
    seed_proxy: Optional[str],
    seed_max_workers: int,
    progress: Optional[Callable[[dict], None]],
) -> dict:
    _validate_realtime_limits(
        max_messages=max_messages,
        max_iterations=max_iterations,
        snapshot_interval_seconds=snapshot_interval_seconds,
        stale_timeout_seconds=stale_timeout_seconds,
        reconnect_delay_seconds=reconnect_delay_seconds,
        max_reconnects=max_reconnects,
        ws_max_size=ws_max_size,
        min_run_observations=min_run_observations,
        min_run_seconds=min_run_seconds,
        max_opportunities_per_iteration=max_opportunities_per_iteration,
    )
    try:
        import websockets
    except ImportError as exc:
        raise RuntimeError("install websockets to use realtime WebSocket commands") from exc

    markets = load_watchlist_markets(watchlist_path)
    payload = polymarket_subscription_payload(token_ids_from_watchlist(markets))
    rule_set = load_rule_set(rules_path, gamma_path=gamma_path)
    replay_state = IncrementalReplayState()
    store = RealtimeOrderBookStore()

    report_out_path.parent.mkdir(parents=True, exist_ok=True)
    if updates_out_path:
        updates_out_path.parent.mkdir(parents=True, exist_ok=True)
    if snapshots_out_path:
        snapshots_out_path.parent.mkdir(parents=True, exist_ok=True)
    if latest_snapshots_out_path:
        latest_snapshots_out_path.parent.mkdir(parents=True, exist_ok=True)

    message_count = 0
    iteration = 0
    snapshots_collected = 0
    next_snapshot_at = _initial_next_snapshot_at(snapshot_interval_seconds)
    connection_count = 0
    reconnect_count = 0
    stop_requested = False
    last_error = None
    report_handle = report_out_path.open("a")
    updates_handle = updates_out_path.open("a") if updates_out_path else None
    snapshots_handle = snapshots_out_path.open("a") if snapshots_out_path else None
    try:
        if seed_orderbooks:
            seed_errors = []
            seed_books = fetch_polymarket_books_by_token_id(
                token_ids_from_watchlist(markets),
                seed_timeout,
                proxy=seed_proxy,
                max_workers=seed_max_workers,
                skip_errors=True,
                errors=seed_errors,
            )
            update_rows = [
                store.seed_polymarket_book(token_id, book)
                for token_id, book in seed_books.items()
            ]
            _write_rows(updates_handle, update_rows)
            _write_rows(
                report_handle,
                [
                    {
                        "type": "realtime_monitor_seed",
                        "ts": _utc_now(),
                        "requested_token_count": len(token_ids_from_watchlist(markets)),
                        "seeded_token_count": len(seed_books),
                        "error_count": len(seed_errors),
                        "errors": seed_errors[:20],
                    }
                ],
            )
        while not stop_requested:
            connection_count += 1
            connection_started_at = time.monotonic()
            last_message_at = connection_started_at
            _write_rows(report_handle, [_connection_event_row("connecting", connection_count, reconnect_count)])
            try:
                async with websockets.connect(url, max_size=ws_max_size) as websocket:
                    await websocket.send(json.dumps(payload))
                    _write_rows(report_handle, [_connection_event_row("connected", connection_count, reconnect_count)])
                    while True:
                        deadline_at = _next_realtime_deadline(
                            next_snapshot_at,
                            last_message_at,
                            stale_timeout_seconds,
                        )
                        raw_message = await _recv_until_deadline(websocket, deadline_at)
                        if raw_message is not None:
                            message_count += 1
                            last_message_at = time.monotonic()
                            message = json.loads(raw_message)
                            update_rows = store.apply_polymarket_message(message)
                            _write_rows(updates_handle, update_rows)

                        if _is_stale(last_message_at, stale_timeout_seconds):
                            raise RealtimeStaleError("Polymarket WebSocket did not receive messages before stale timeout")

                        if _should_scan_now(raw_message, next_snapshot_at, snapshot_interval_seconds):
                            snapshot_rows = store.binary_snapshot_rows(markets)
                            next_snapshot_at = _advance_next_snapshot_at(snapshot_interval_seconds)
                            if snapshot_rows:
                                iteration += 1
                                snapshots_collected += len(snapshot_rows)
                                _write_rows(snapshots_handle, snapshot_rows)
                                if latest_snapshots_out_path:
                                    _write_rows_atomic(latest_snapshots_out_path, snapshot_rows)
                                snapshots = [snapshot_from_row(row) for row in snapshot_rows]
                                batch_result = replay_state.apply_snapshots(
                                    snapshots,
                                    rule_set,
                                    min_net_edge=min_net_edge,
                                    max_capital_per_trade=max_capital_per_trade,
                                    bankroll=bankroll,
                                    min_paper_roi=min_paper_roi,
                                    min_paper_edge=min_paper_edge,
                                    min_paper_quantity=min_paper_quantity,
                                )
                                stable_opportunities = stable_current_opportunities(
                                    batch_result.current_opportunities,
                                    batch_result.current_runs,
                                    min_run_observations=min_run_observations,
                                    min_run_seconds=min_run_seconds,
                                )
                                stable_selection = select_paper_trades(
                                    stable_opportunities,
                                    max_capital_per_trade=max_capital_per_trade,
                                    bankroll=bankroll,
                                    min_quantity=min_paper_quantity,
                                    min_roi=min_paper_roi,
                                    min_edge=min_paper_edge,
                                )
                                row = _realtime_monitor_iteration_row(
                                    iteration,
                                    message_count,
                                    len(snapshot_rows),
                                    store,
                                    replay_state,
                                    batch_result.current_opportunities,
                                    stable_opportunities,
                                    stable_selection,
                                    batch_result.current_runs,
                                    max_opportunities_per_iteration,
                                    connection_count,
                                    reconnect_count,
                                    _message_age_seconds(last_message_at),
                                )
                                _write_rows(report_handle, [row])
                                if progress:
                                    progress(row)
                                if max_iterations is not None and iteration >= max_iterations:
                                    stop_requested = True
                                    break

                        if max_messages is not None and message_count >= max_messages:
                            stop_requested = True
                            break
            except Exception as exc:
                last_error = f"{exc.__class__.__name__}: {exc}"
                _write_rows(report_handle, [_connection_event_row("disconnected", connection_count, reconnect_count, exc)])
                reconnect_count += 1
                if max_reconnects is not None and reconnect_count > max_reconnects:
                    raise
                _write_rows(report_handle, [_connection_event_row("reconnect_sleep", connection_count, reconnect_count)])
                await asyncio.sleep(reconnect_delay_seconds)
    finally:
        for handle in [snapshots_handle, updates_handle, report_handle]:
            if handle:
                handle.close()

    summary = _realtime_monitor_summary_row(
        watchlist_path,
        report_out_path,
        snapshots_out_path,
        latest_snapshots_out_path,
        updates_out_path,
        message_count,
        iteration,
        snapshots_collected,
        replay_state,
        connection_count,
        reconnect_count,
        last_error,
    )
    _append_jsonl_row(report_out_path, summary)
    return summary


def _validate_realtime_limits(
    max_messages: Optional[int],
    max_iterations: Optional[int],
    snapshot_interval_seconds: Optional[float],
    stale_timeout_seconds: Optional[float],
    reconnect_delay_seconds: float,
    max_reconnects: Optional[int],
    ws_max_size: Optional[int],
    min_run_observations: int,
    min_run_seconds: float,
    max_opportunities_per_iteration: int,
) -> None:
    if max_messages is not None and max_messages < 1:
        raise ValueError("max_messages must be at least 1")
    if max_iterations is not None and max_iterations < 1:
        raise ValueError("max_iterations must be at least 1")
    if snapshot_interval_seconds is not None and snapshot_interval_seconds < 0:
        raise ValueError("snapshot_interval_seconds must be non-negative")
    if stale_timeout_seconds is not None and stale_timeout_seconds < 0:
        raise ValueError("stale_timeout_seconds must be non-negative")
    if reconnect_delay_seconds < 0:
        raise ValueError("reconnect_delay_seconds must be non-negative")
    if max_reconnects is not None and max_reconnects < 0:
        raise ValueError("max_reconnects must be non-negative")
    if ws_max_size is not None and ws_max_size < 1:
        raise ValueError("ws_max_size must be at least 1 or None")
    if min_run_observations < 1:
        raise ValueError("min_run_observations must be at least 1")
    if min_run_seconds < 0:
        raise ValueError("min_run_seconds must be non-negative")
    if max_opportunities_per_iteration < 0:
        raise ValueError("max_opportunities_per_iteration must be non-negative")


def _realtime_monitor_iteration_row(
    iteration: int,
    messages_seen: int,
    snapshots_collected: int,
    store: RealtimeOrderBookStore,
    result: IncrementalReplayState,
    current_opportunities: list,
    stable_opportunities: list,
    stable_selection,
    current_runs: list,
    max_opportunities_per_iteration: int,
    connection_count: int,
    reconnect_count: int,
    last_message_age_seconds: float,
) -> dict:
    stable_paper_capital_used = sum(trade.capital_used for trade in stable_selection.trades)
    stable_paper_edge = sum(trade.edge for trade in stable_selection.trades)
    top_current = _top_opportunity_rows(current_opportunities, max_opportunities_per_iteration)
    top_stable = _top_opportunity_rows(stable_opportunities, max_opportunities_per_iteration)
    top_stable_trades = [
        trade_to_row(trade)
        for trade in sorted(stable_selection.trades, key=lambda trade: trade.roi, reverse=True)[
            :max_opportunities_per_iteration
        ]
    ]
    return {
        "type": "realtime_monitor_iteration",
        "ts": _utc_now(),
        "iteration": iteration,
        "messages_seen": messages_seen,
        "connection_count": connection_count,
        "reconnect_count": reconnect_count,
        "last_message_age_seconds": last_message_age_seconds,
        "known_token_count": store.token_count,
        "snapshots_collected": snapshots_collected,
        "snapshot_count": result.snapshot_count,
        "opportunity_count": result.opportunity_count,
        "current_opportunity_count": len(current_opportunities),
        "stable_opportunity_count": len(stable_opportunities),
        "paper_trade_count": result.paper_trade_count,
        "paper_rejection_count": len(result.paper_rejections),
        "paper_capital_used": result.paper_capital_used,
        "paper_edge": result.paper_edge,
        "paper_roi": result.paper_edge / result.paper_capital_used if result.paper_capital_used > 0 else 0.0,
        "stable_paper_trade_count": len(stable_selection.trades),
        "stable_paper_rejection_count": len(stable_selection.rejections),
        "stable_paper_capital_used": stable_paper_capital_used,
        "stable_paper_edge": stable_paper_edge,
        "stable_paper_roi": stable_paper_edge / stable_paper_capital_used if stable_paper_capital_used > 0 else 0.0,
        "last_snapshot_ts": result.last_snapshot_ts,
        "current_opportunities": top_current,
        "stable_opportunities": top_stable,
        "stable_paper_trades": top_stable_trades,
        "current_runs": [_run_to_row(run) for run in current_runs],
    }


def _realtime_monitor_summary_row(
    watchlist_path: Path,
    report_out_path: Path,
    snapshots_out_path: Optional[Path],
    latest_snapshots_out_path: Optional[Path],
    updates_out_path: Optional[Path],
    messages_seen: int,
    iterations_completed: int,
    snapshots_collected: int,
    result: IncrementalReplayState,
    connection_count: int,
    reconnect_count: int,
    last_error: Optional[str],
) -> dict:
    return {
        "type": "realtime_monitor_summary",
        "ts": _utc_now(),
        "watchlist_path": str(watchlist_path),
        "report_path": str(report_out_path),
        "snapshots_path": str(snapshots_out_path) if snapshots_out_path else None,
        "latest_snapshots_path": str(latest_snapshots_out_path) if latest_snapshots_out_path else None,
        "updates_path": str(updates_out_path) if updates_out_path else None,
        "messages_seen": messages_seen,
        "connection_count": connection_count,
        "reconnect_count": reconnect_count,
        "last_error": last_error,
        "iterations_completed": iterations_completed,
        "snapshots_collected": snapshots_collected,
        "snapshot_count": result.snapshot_count,
        "opportunity_count": result.opportunity_count,
        "paper_trade_count": result.paper_trade_count,
        "paper_capital_used": result.paper_capital_used,
        "paper_edge": result.paper_edge,
        "paper_roi": result.paper_edge / result.paper_capital_used if result.paper_capital_used > 0 else 0.0,
        "last_snapshot_ts": result.last_snapshot_ts,
        "run_count": len(result.runs),
    }


def _top_opportunity_rows(opportunities: list, limit: int) -> list:
    if limit == 0:
        return []
    return [
        opportunity_to_row(opportunity)
        for opportunity in sorted(opportunities, key=lambda opportunity: opportunity.net_edge_per_share, reverse=True)[
            :limit
        ]
    ]


def _run_to_row(run) -> dict:
    return {
        "key": run.key,
        "market_id": run.market_id,
        "start_ts": run.start_ts,
        "end_ts": run.end_ts,
        "observation_count": run.observation_count,
        "duration_seconds": run.duration_seconds,
        "max_edge_per_share": run.max_edge_per_share,
    }


def _connection_event_row(
    event: str,
    connection_count: int,
    reconnect_count: int,
    exc: Optional[Exception] = None,
) -> dict:
    row = {
        "type": "realtime_monitor_connection_event",
        "ts": _utc_now(),
        "event": event,
        "connection_count": connection_count,
        "reconnect_count": reconnect_count,
    }
    if exc is not None:
        row["error_type"] = exc.__class__.__name__
        row["message"] = str(exc)
    return row


def _write_rows(handle, rows: Iterable[dict]) -> None:
    if not handle:
        return
    wrote = False
    for row in rows:
        handle.write(json.dumps(row, sort_keys=True) + "\n")
        wrote = True
    if wrote:
        handle.flush()


def _write_rows_atomic(path: Path, rows: Iterable[dict]) -> None:
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    tmp_path.replace(path)


def _append_jsonl_row(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")


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


def _initial_next_snapshot_at(interval_seconds: Optional[float]) -> Optional[float]:
    if interval_seconds is None or interval_seconds == 0:
        return None
    return time.monotonic() + interval_seconds


def _advance_next_snapshot_at(interval_seconds: Optional[float]) -> Optional[float]:
    if interval_seconds is None or interval_seconds == 0:
        return None
    return time.monotonic() + interval_seconds


async def _recv_until_next_snapshot(websocket, next_snapshot_at: Optional[float], interval_seconds: Optional[float]):
    if interval_seconds is None or interval_seconds == 0:
        return await websocket.recv()
    timeout = max(0.0, (next_snapshot_at or time.monotonic()) - time.monotonic())
    try:
        return await asyncio.wait_for(websocket.recv(), timeout=timeout)
    except asyncio.TimeoutError:
        return None


async def _recv_until_deadline(websocket, deadline_at: Optional[float]):
    if deadline_at is None:
        return await websocket.recv()
    timeout = max(0.0, deadline_at - time.monotonic())
    try:
        return await asyncio.wait_for(websocket.recv(), timeout=timeout)
    except asyncio.TimeoutError:
        return None


def _next_realtime_deadline(
    next_snapshot_at: Optional[float],
    last_message_at: float,
    stale_timeout_seconds: Optional[float],
) -> Optional[float]:
    deadlines = []
    if next_snapshot_at is not None:
        deadlines.append(next_snapshot_at)
    if stale_timeout_seconds is not None:
        deadlines.append(last_message_at + stale_timeout_seconds)
    return min(deadlines) if deadlines else None


def _is_stale(last_message_at: float, stale_timeout_seconds: Optional[float]) -> bool:
    if stale_timeout_seconds is None:
        return False
    return _message_age_seconds(last_message_at) >= stale_timeout_seconds


def _message_age_seconds(last_message_at: float) -> float:
    return max(0.0, time.monotonic() - last_message_at)


def _should_scan_now(raw_message, next_snapshot_at: Optional[float], interval_seconds: Optional[float]) -> bool:
    if interval_seconds is None or interval_seconds == 0:
        return raw_message is not None
    return time.monotonic() >= (next_snapshot_at or 0.0)


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
