import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, List, Optional
from urllib.parse import quote, urlencode
from urllib.request import ProxyHandler, Request, build_opener, urlopen


GAMMA_MARKETS_URL = "https://gamma-api.polymarket.com/markets"
POLYMARKET_CLOB_BOOK_URL = "https://clob.polymarket.com/book"
POLYMARKET_CLOB_BOOKS_URL = "https://clob.polymarket.com/books"
POLYMARKET_DATA_TRADES_URL = "https://data-api.polymarket.com/trades"
KALSHI_API_URL = "https://external-api.kalshi.com/trade-api/v2"
KALSHI_DEFAULT_TAKER_FEE_RATE = 0.07


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


def collect_polymarket_gamma(
    path: Path,
    limit: int,
    timeout: float,
    proxy: Optional[str] = None,
    offset: int = 0,
) -> int:
    params = urlencode({"active": "true", "closed": "false", "limit": str(limit), "offset": str(offset)})
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


def collect_polymarket_gamma_pages(
    path: Path,
    limit: int,
    pages: int,
    timeout: float,
    proxy: Optional[str] = None,
    start_offset: int = 0,
    collect_page: Callable[[Path, int, float, Optional[str], int], int] = collect_polymarket_gamma,
) -> int:
    if limit < 1:
        raise ValueError("limit must be at least 1")
    if pages < 1:
        raise ValueError("pages must be at least 1")
    if start_offset < 0:
        raise ValueError("start_offset must be non-negative")

    total = 0
    for page in range(pages):
        total += collect_page(path, limit, timeout, proxy, start_offset + page * limit)
    return total


def collect_polymarket_gamma_markets_by_id(
    path: Path,
    market_ids: Iterable[str],
    timeout: float,
    proxy: Optional[str] = None,
    fetch_json: Optional[Callable[[str, float, Optional[str]], dict]] = None,
    skip_errors: bool = False,
    errors: Optional[list] = None,
    max_workers: int = 1,
) -> int:
    fetch = fetch_json or _fetch_json
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered_market_ids = []
    seen = set()
    for market_id in market_ids:
        normalized_market_id = str(market_id)
        if not normalized_market_id or normalized_market_id in seen:
            continue
        seen.add(normalized_market_id)
        ordered_market_ids.append(normalized_market_id)

    count = 0
    rows = []
    if max_workers <= 1 or len(ordered_market_ids) <= 1:
        for normalized_market_id in ordered_market_ids:
            try:
                row = _fetch_polymarket_gamma_market_by_id(normalized_market_id, timeout, proxy, fetch)
            except Exception as exc:
                if not skip_errors:
                    raise
                _append_collection_error(
                    errors,
                    "gamma_market_fetch_error",
                    market_id=normalized_market_id,
                    message=str(exc),
                    error_type=exc.__class__.__name__,
                )
                continue
            rows.append((normalized_market_id, row))
    else:
        worker_count = min(max_workers, len(ordered_market_ids))
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = {
                executor.submit(_fetch_polymarket_gamma_market_by_id, normalized_market_id, timeout, proxy, fetch): normalized_market_id
                for normalized_market_id in ordered_market_ids
            }
            fetched_rows = {}
            for future in as_completed(futures):
                normalized_market_id = futures[future]
                try:
                    fetched_rows[normalized_market_id] = future.result()
                except Exception as exc:
                    if not skip_errors:
                        raise
                    _append_collection_error(
                        errors,
                        "gamma_market_fetch_error",
                        market_id=normalized_market_id,
                        message=str(exc),
                        error_type=exc.__class__.__name__,
                    )
            for normalized_market_id in ordered_market_ids:
                row = fetched_rows.get(normalized_market_id)
                if row is not None:
                    rows.append((normalized_market_id, row))

    with path.open("a") as handle:
        for normalized_market_id, row in rows:
            handle.write(
                json.dumps(
                    {
                        "ts": _utc_now(),
                        "type": "raw_polymarket_gamma_market",
                        "market_id": str(row.get("id") or row.get("conditionId") or normalized_market_id),
                        "raw": row,
                    },
                    sort_keys=True,
                )
                + "\n"
            )
            count += 1
    return count


def _fetch_polymarket_gamma_market_by_id(
    market_id: str,
    timeout: float,
    proxy: Optional[str],
    fetch_json: Callable[[str, float, Optional[str]], dict],
) -> dict:
    normalized_market_id = str(market_id)
    if normalized_market_id.lower().startswith("0x"):
        row = fetch_json(f"{GAMMA_MARKETS_URL}?{urlencode({'condition_ids': normalized_market_id})}", timeout, proxy)
        if isinstance(row, list):
            for market in row:
                if str(market.get("conditionId") or "").lower() == normalized_market_id.lower():
                    return market
            if row:
                return row[0]
        raise RuntimeError("unexpected Polymarket Gamma condition_id response")
    row = fetch_json(f"{GAMMA_MARKETS_URL}/{quote(normalized_market_id)}", timeout, proxy)
    if not isinstance(row, dict):
        raise RuntimeError("unexpected Polymarket Gamma market response")
    return row


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


def collect_polymarket_data_trades(
    path: Path,
    gamma_path: Path,
    market_ids: Iterable[str],
    limit: int,
    timeout: float,
    proxy: Optional[str] = None,
    side: Optional[str] = None,
    offset: int = 0,
    per_market: bool = False,
    max_workers: int = 1,
    skip_errors: bool = False,
    errors: Optional[list] = None,
    retries: int = 0,
    fetch_json: Optional[Callable[[str, float, Optional[str]], object]] = None,
) -> int:
    if limit < 1:
        raise ValueError("limit must be at least 1")
    if offset < 0:
        raise ValueError("offset must be non-negative")
    if max_workers < 1:
        raise ValueError("max_workers must be at least 1")
    if retries < 0:
        raise ValueError("retries must be non-negative")

    markets = raw_gamma_markets_from_ndjson(gamma_path)
    condition_to_market_id = _condition_ids_for_market_ids(markets, market_ids)
    if not condition_to_market_id:
        return 0

    fetch = fetch_json or _fetch_json
    if per_market:
        trades = _fetch_polymarket_data_trades_per_market(
            list(condition_to_market_id),
            limit,
            offset,
            side,
            timeout,
            proxy,
            fetch,
            max_workers,
            skip_errors,
            errors,
            retries,
        )
    else:
        trades = _fetch_polymarket_data_trades_with_retries(
            list(condition_to_market_id),
            limit,
            offset,
            side,
            timeout,
            proxy,
            fetch,
            skip_errors,
            errors,
            retries,
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    seen_trade_keys = set()
    condition_lookup = {condition_id.lower(): market_id for condition_id, market_id in condition_to_market_id.items()}
    with path.open("a") as handle:
        for trade in trades:
            if not isinstance(trade, dict):
                continue
            condition_id = str(trade.get("conditionId") or trade.get("condition_id") or "").strip()
            trade_key = _polymarket_data_trade_key(trade)
            if trade_key in seen_trade_keys:
                continue
            seen_trade_keys.add(trade_key)
            row = {
                "ts": _utc_now(),
                "type": "raw_polymarket_data_trade",
                "market_id": condition_lookup.get(condition_id.lower(), condition_id),
                "condition_id": condition_id,
                "asset_id": str(trade.get("asset") or trade.get("asset_id") or "").strip(),
                "side": str(trade.get("side") or "").upper(),
                "price": _maybe_float(trade.get("price")),
                "size": _maybe_float(trade.get("size")),
                "trade_ts": _trade_timestamp_to_iso(trade.get("timestamp")),
                "raw": trade,
            }
            handle.write(json.dumps(row, sort_keys=True) + "\n")
            count += 1
    return count


def _fetch_polymarket_data_trades_per_market(
    condition_ids: List[str],
    limit: int,
    offset: int,
    side: Optional[str],
    timeout: float,
    proxy: Optional[str],
    fetch_json: Callable[[str, float, Optional[str]], object],
    max_workers: int,
    skip_errors: bool,
    errors: Optional[list],
    retries: int,
) -> List[dict]:
    def fetch_condition(condition_id: str) -> List[dict]:
        trades = _fetch_polymarket_data_trades_with_retries(
            [condition_id],
            limit,
            offset,
            side,
            timeout,
            proxy,
            fetch_json,
            skip_errors,
            errors,
            retries,
        )
        for trade in trades:
            if isinstance(trade, dict) and not (trade.get("conditionId") or trade.get("condition_id")):
                trade["conditionId"] = condition_id
        return trades

    if max_workers <= 1 or len(condition_ids) <= 1:
        rows = []
        for condition_id in condition_ids:
            rows.extend(fetch_condition(condition_id))
        return rows

    rows_by_condition = {}
    with ThreadPoolExecutor(max_workers=min(max_workers, len(condition_ids))) as executor:
        futures = {executor.submit(fetch_condition, condition_id): condition_id for condition_id in condition_ids}
        for future in as_completed(futures):
            rows_by_condition[futures[future]] = future.result()

    rows = []
    for condition_id in condition_ids:
        rows.extend(rows_by_condition.get(condition_id, []))
    return rows


def _fetch_polymarket_data_trades_with_retries(
    condition_ids: List[str],
    limit: int,
    offset: int,
    side: Optional[str],
    timeout: float,
    proxy: Optional[str],
    fetch_json: Callable[[str, float, Optional[str]], object],
    skip_errors: bool,
    errors: Optional[list],
    retries: int,
) -> List[dict]:
    url = _polymarket_data_trades_url(condition_ids, limit, offset, side)
    attempts = retries + 1
    for attempt in range(attempts):
        try:
            response = fetch_json(url, timeout, proxy)
            return _polymarket_data_trade_rows_from_response(response)
        except Exception as exc:
            if attempt < retries:
                continue
            if not skip_errors:
                raise
            _append_collection_error(
                errors,
                "polymarket_data_trade_fetch_error",
                market_id=",".join(condition_ids),
                message=str(exc),
                error_type=exc.__class__.__name__,
            )
            return []
    return []


def _polymarket_data_trades_url(
    condition_ids: List[str],
    limit: int,
    offset: int,
    side: Optional[str],
) -> str:
    params = {
        "market": ",".join(condition_ids),
        "limit": str(limit),
        "offset": str(offset),
    }
    if side:
        params["side"] = str(side).upper()
    return f"{POLYMARKET_DATA_TRADES_URL}?{urlencode(params)}"


def _polymarket_data_trade_rows_from_response(response: object) -> List[dict]:
    if isinstance(response, list):
        trades = response
    elif isinstance(response, dict):
        trades = response.get("trades")
    else:
        trades = None
    if not isinstance(trades, list):
        raise RuntimeError("unexpected Polymarket data trades response")
    return [trade for trade in trades if isinstance(trade, dict)]


def _polymarket_data_trade_key(trade: dict) -> tuple:
    return (
        str(trade.get("transactionHash") or trade.get("transaction_hash") or ""),
        str(trade.get("asset") or trade.get("asset_id") or ""),
        str(trade.get("conditionId") or trade.get("condition_id") or ""),
        str(trade.get("timestamp") or trade.get("trade_ts") or ""),
        str(trade.get("side") or "").upper(),
        str(trade.get("price") or ""),
        str(trade.get("size") or ""),
    )


def fetch_polymarket_books_by_token_id(
    token_ids: Iterable[str],
    timeout: float,
    proxy: Optional[str] = None,
    max_workers: int = 1,
    skip_errors: bool = False,
    errors: Optional[list] = None,
    fetch_json: Optional[Callable[[str, float, Optional[str]], dict]] = None,
    post_json: Optional[Callable[[str, object, float, Optional[str]], object]] = None,
    batch_size: int = 500,
    retry_missing: bool = True,
) -> dict:
    if batch_size < 1:
        raise ValueError("batch_size must be at least 1")
    fetch = fetch_json or _fetch_json
    post = post_json or _post_json
    ordered_token_ids = list(dict.fromkeys(str(token_id) for token_id in token_ids if token_id))
    if batch_size > 1 and (fetch_json is None or post_json is not None):
        return _fetch_polymarket_books_by_batch(
            ordered_token_ids,
            timeout,
            proxy,
            fetch,
            post,
            batch_size,
            max_workers,
            skip_errors,
            errors,
            retry_missing,
        )

    def fetch_book(token_id: str) -> dict:
        params = urlencode({"token_id": token_id})
        return fetch(f"{POLYMARKET_CLOB_BOOK_URL}?{params}", timeout, proxy)

    return _fetch_books_by_token_id(
        ordered_token_ids,
        fetch_book,
        max_workers,
        skip_errors=skip_errors,
        errors=errors,
    )


def _fetch_polymarket_books_by_batch(
    token_ids: list,
    timeout: float,
    proxy: Optional[str],
    fetch_json: Callable[[str, float, Optional[str]], dict],
    post_json: Callable[[str, object, float, Optional[str]], object],
    batch_size: int,
    max_workers: int,
    skip_errors: bool,
    errors: Optional[list],
    retry_missing: bool,
) -> dict:
    if max_workers < 1:
        raise ValueError("max_workers must be at least 1")
    chunks = [token_ids[index : index + batch_size] for index in range(0, len(token_ids), batch_size)]
    if not chunks:
        return {}

    def fetch_chunk(chunk: list) -> dict:
        payload = [{"token_id": token_id} for token_id in chunk]
        response = post_json(POLYMARKET_CLOB_BOOKS_URL, payload, timeout, proxy)
        if not isinstance(response, list):
            raise RuntimeError("unexpected Polymarket batch books response")
        books = {}
        for index, book in enumerate(response):
            if not isinstance(book, dict):
                continue
            token_id = str(book.get("asset_id") or (chunk[index] if index < len(chunk) else "")).strip()
            if token_id:
                books[token_id] = book
        return books

    def fetch_single(token_id: str) -> dict:
        params = urlencode({"token_id": token_id})
        return fetch_json(f"{POLYMARKET_CLOB_BOOK_URL}?{params}", timeout, proxy)

    def fill_missing(chunk: list, books: dict) -> dict:
        if not retry_missing:
            return books
        missing_token_ids = [token_id for token_id in chunk if token_id not in books]
        if not missing_token_ids:
            return books
        books.update(
            _fetch_books_by_token_id(
                missing_token_ids,
                fetch_single,
                max_workers,
                skip_errors=skip_errors,
                errors=errors,
            )
        )
        return books

    if max_workers == 1 or len(chunks) == 1:
        books = {}
        for chunk in chunks:
            try:
                books.update(fill_missing(chunk, fetch_chunk(chunk)))
            except Exception as exc:
                if not skip_errors:
                    raise
                for token_id in chunk:
                    _append_collection_error(
                        errors,
                        "book_fetch_error",
                        token_id=token_id,
                        message=str(exc),
                        error_type=exc.__class__.__name__,
                    )
        return books

    worker_count = min(max_workers, len(chunks))
    books = {}
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = {executor.submit(fetch_chunk, chunk): chunk for chunk in chunks}
        for future in as_completed(futures):
            chunk = futures[future]
            try:
                books.update(fill_missing(chunk, future.result()))
            except Exception as exc:
                if not skip_errors:
                    raise
                for token_id in chunk:
                    _append_collection_error(
                        errors,
                        "book_fetch_error",
                        token_id=token_id,
                        message=str(exc),
                        error_type=exc.__class__.__name__,
                    )
    return books


def collect_kalshi_markets(
    path: Path,
    limit: int,
    timeout: float,
    proxy: Optional[str] = None,
    cursor: Optional[str] = None,
    status: Optional[str] = "open",
    tickers: Optional[Iterable[str]] = None,
) -> int:
    markets, _ = fetch_kalshi_markets_page(limit, timeout, proxy, cursor=cursor, status=status, tickers=tickers)
    return _write_kalshi_market_rows(path, markets)


def collect_kalshi_markets_by_event_tickers(
    path: Path,
    event_tickers: Iterable[str],
    limit: int,
    timeout: float,
    proxy: Optional[str] = None,
    status: Optional[str] = "open",
) -> int:
    total = 0
    seen = set()
    for event_ticker in event_tickers:
        normalized_event_ticker = str(event_ticker or "").strip()
        if not normalized_event_ticker or normalized_event_ticker in seen:
            continue
        seen.add(normalized_event_ticker)
        markets, _ = fetch_kalshi_markets_page(
            limit,
            timeout,
            proxy,
            status=status,
            event_ticker=normalized_event_ticker,
        )
        total += _write_kalshi_market_rows(path, markets)
    return total


def collect_kalshi_markets_pages(
    path: Path,
    limit: int,
    timeout: float,
    proxy: Optional[str] = None,
    cursor: Optional[str] = None,
    status: Optional[str] = "open",
    tickers: Optional[Iterable[str]] = None,
    pages: Optional[int] = 1,
) -> int:
    if pages is not None and pages < 1:
        raise ValueError("pages must be at least 1, or None for all pages")

    total = 0
    current_cursor = cursor
    seen_cursors = set()
    page_index = 0
    while pages is None or page_index < pages:
        markets, next_cursor = fetch_kalshi_markets_page(
            limit,
            timeout,
            proxy,
            cursor=current_cursor,
            status=status,
            tickers=tickers,
        )
        total += _write_kalshi_market_rows(path, markets)
        page_index += 1
        if not next_cursor or next_cursor in seen_cursors:
            break
        seen_cursors.add(next_cursor)
        current_cursor = next_cursor
    return total


def fetch_kalshi_markets_page(
    limit: int,
    timeout: float,
    proxy: Optional[str] = None,
    cursor: Optional[str] = None,
    status: Optional[str] = "open",
    tickers: Optional[Iterable[str]] = None,
    event_ticker: Optional[str] = None,
) -> tuple:
    if limit < 0:
        raise ValueError("limit must be non-negative")
    params = {"limit": str(limit)}
    if cursor:
        params["cursor"] = cursor
    if status:
        params["status"] = status
    ticker_list = [str(ticker) for ticker in tickers or [] if ticker]
    if ticker_list:
        params["tickers"] = ",".join(ticker_list)
    if event_ticker:
        params["event_ticker"] = str(event_ticker)
    row = _fetch_json(f"{KALSHI_API_URL}/markets?{urlencode(params)}", timeout, proxy=proxy)
    markets = row.get("markets") if isinstance(row, dict) else None
    if not isinstance(markets, list):
        raise RuntimeError("unexpected Kalshi markets response")
    next_cursor = row.get("cursor")
    if isinstance(next_cursor, str):
        next_cursor = next_cursor.strip() or None
    else:
        next_cursor = None
    return markets, next_cursor


def _write_kalshi_market_rows(path: Path, markets: Iterable[dict]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as handle:
        count = 0
        for market in markets:
            handle.write(
                json.dumps(
                    {
                        "ts": _utc_now(),
                        "type": "raw_kalshi_market",
                        "market_id": market.get("ticker"),
                        "raw": market,
                    },
                    sort_keys=True,
                )
                + "\n"
            )
            count += 1
    return count


def collect_kalshi_orderbooks(
    path: Path,
    tickers: Iterable[str],
    timeout: float,
    proxy: Optional[str] = None,
) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    seen = set()
    with path.open("a") as handle:
        for ticker in tickers:
            normalized_ticker = str(ticker).strip()
            if not normalized_ticker or normalized_ticker in seen:
                continue
            seen.add(normalized_ticker)
            row = _fetch_json(f"{KALSHI_API_URL}/markets/{quote(normalized_ticker)}/orderbook", timeout, proxy=proxy)
            handle.write(
                json.dumps(
                    {
                        "ts": _utc_now(),
                        "type": "raw_kalshi_orderbook",
                        "market_id": normalized_ticker,
                        "raw": row,
                    },
                    sort_keys=True,
                )
                + "\n"
            )
            count += 1
    return count


def write_kalshi_binary_snapshots(orderbooks_path: Path, out_path: Path) -> int:
    rows = list(kalshi_binary_snapshot_rows_from_orderbooks(orderbooks_path))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("a") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    return len(rows)


def kalshi_binary_snapshot_rows_from_orderbooks(path: Path) -> Iterable[dict]:
    with path.open() as handle:
        yield from kalshi_binary_snapshot_rows_from_orderbook_lines(handle)


def kalshi_binary_snapshot_rows_from_orderbook_lines(lines: Iterable[str]) -> Iterable[dict]:
    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        row = json.loads(line)
        if row.get("type") != "raw_kalshi_orderbook":
            continue
        market_id = str(row.get("market_id") or "").strip()
        if not market_id:
            continue
        orderbook = _kalshi_orderbook_payload(row.get("raw") or {})
        yes_bids = _kalshi_levels(orderbook, "yes")
        no_bids = _kalshi_levels(orderbook, "no")
        # Kalshi exposes bids. In a binary market, a NO bid at p is a YES ask at 1-p, and vice versa.
        yield {
            "ts": row.get("ts") or _utc_now(),
            "type": "binary_snapshot",
            "venue": "kalshi",
            "market_id": market_id,
            "fee_rate": KALSHI_DEFAULT_TAKER_FEE_RATE,
            "yes": {
                "token_id": f"{market_id}:YES",
                "asks": _complement_asks(no_bids),
                "bids": yes_bids,
            },
            "no": {
                "token_id": f"{market_id}:NO",
                "asks": _complement_asks(yes_bids),
                "bids": no_bids,
            },
        }


def collect_polymarket_binary_snapshots(
    path: Path,
    limit: int,
    timeout: float,
    proxy: Optional[str] = None,
    max_workers: int = 1,
    skip_book_errors: bool = False,
    errors: Optional[list] = None,
) -> int:
    params = urlencode({"active": "true", "closed": "false", "limit": str(limit)})
    markets = _fetch_json(f"{GAMMA_MARKETS_URL}?{params}", timeout, proxy=proxy)
    if not isinstance(markets, list):
        raise RuntimeError("unexpected Polymarket Gamma response")

    def fetch_book(token_id: str) -> dict:
        book_params = urlencode({"token_id": token_id})
        return _fetch_json(f"{POLYMARKET_CLOB_BOOK_URL}?{book_params}", timeout, proxy=proxy)

    rows = binary_snapshot_rows_from_gamma_markets(
        markets,
        fetch_book,
        ts=_utc_now(),
        max_workers=max_workers,
        skip_book_errors=skip_book_errors,
        errors=errors,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    return len(rows)


def collect_polymarket_binary_snapshots_for_rules(
    path: Path,
    gamma_path: Path,
    rules_path: Path,
    timeout: float,
    proxy: Optional[str] = None,
    max_workers: int = 1,
    skip_book_errors: bool = False,
    errors: Optional[list] = None,
    expand_neg_risk_groups: bool = True,
    max_markets: Optional[int] = None,
) -> int:
    markets = raw_gamma_markets_from_ndjson(gamma_path)
    market_ids = market_ids_from_rule_file(rules_path)
    if expand_neg_risk_groups:
        market_ids = expand_market_ids_with_neg_risk_groups(markets, market_ids)
    market_ids = limit_market_ids_by_gamma_order(markets, market_ids, max_markets)

    def fetch_book(token_id: str) -> dict:
        book_params = urlencode({"token_id": token_id})
        return _fetch_json(f"{POLYMARKET_CLOB_BOOK_URL}?{book_params}", timeout, proxy=proxy)

    return collect_polymarket_binary_snapshots_for_markets(
        path,
        markets,
        market_ids,
        fetch_book,
        ts=_utc_now(),
        max_workers=max_workers,
        skip_book_errors=skip_book_errors,
        errors=errors,
    )


def collect_polymarket_binary_snapshots_for_market_ids(
    path: Path,
    gamma_path: Path,
    market_ids: Iterable[str],
    timeout: float,
    proxy: Optional[str] = None,
    max_workers: int = 1,
    skip_book_errors: bool = False,
    errors: Optional[list] = None,
    expand_neg_risk_groups: bool = True,
    refresh_missing_gamma: bool = False,
    max_markets: Optional[int] = None,
) -> int:
    markets = raw_gamma_markets_from_ndjson(gamma_path)
    selected_market_ids = {str(market_id) for market_id in market_ids if market_id}
    known_market_ids = {str(market.get("id") or market.get("conditionId") or "") for market in markets}
    missing_market_ids = sorted(selected_market_ids - known_market_ids)
    if missing_market_ids and refresh_missing_gamma:
        collect_polymarket_gamma_markets_by_id(gamma_path, missing_market_ids, timeout, proxy)
        markets = raw_gamma_markets_from_ndjson(gamma_path)

    if expand_neg_risk_groups:
        selected_market_ids = expand_market_ids_with_neg_risk_groups(markets, selected_market_ids)
    selected_market_ids = limit_market_ids_by_gamma_order(markets, selected_market_ids, max_markets)

    def fetch_book(token_id: str) -> dict:
        book_params = urlencode({"token_id": token_id})
        return _fetch_json(f"{POLYMARKET_CLOB_BOOK_URL}?{book_params}", timeout, proxy=proxy)

    return collect_polymarket_binary_snapshots_for_markets(
        path,
        markets,
        selected_market_ids,
        fetch_book,
        ts=_utc_now(),
        max_workers=max_workers,
        skip_book_errors=skip_book_errors,
        errors=errors,
    )


def collect_polymarket_binary_snapshots_for_rules_loop(
    path: Path,
    gamma_path: Path,
    rules_path: Path,
    timeout: float,
    proxy: Optional[str],
    interval_seconds: float,
    iterations: int,
    collect_once: Callable[[Path, Path, Path, float, Optional[str], int], int] = collect_polymarket_binary_snapshots_for_rules,
    sleep: Callable[[float], None] = time.sleep,
    max_workers: int = 1,
    expand_neg_risk_groups: bool = True,
    max_markets: Optional[int] = None,
) -> int:
    if iterations < 1:
        raise ValueError("iterations must be at least 1")
    if interval_seconds < 0:
        raise ValueError("interval_seconds must be non-negative")

    total = 0
    for index in range(iterations):
        total += collect_once(
            path,
            gamma_path,
            rules_path,
            timeout,
            proxy,
            max_workers,
            expand_neg_risk_groups=expand_neg_risk_groups,
            max_markets=max_markets,
        )
        if index < iterations - 1 and interval_seconds > 0:
            sleep(interval_seconds)
    return total


def collect_polymarket_binary_snapshots_for_markets(
    path: Path,
    markets: Iterable[dict],
    market_ids: Iterable[str],
    book_fetcher: Callable[[str], dict],
    ts: Optional[str] = None,
    max_workers: int = 1,
    skip_book_errors: bool = False,
    errors: Optional[list] = None,
) -> int:
    wanted = {str(market_id) for market_id in market_ids}
    rows = binary_snapshot_rows_from_gamma_markets(
        (market for market in markets if str(market.get("id") or market.get("conditionId")) in wanted),
        book_fetcher,
        ts=ts or _utc_now(),
        max_workers=max_workers,
        skip_book_errors=skip_book_errors,
        errors=errors,
    )
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
    collect_once: Callable[[Path, int, float, Optional[str], int], int] = collect_polymarket_binary_snapshots,
    sleep: Callable[[float], None] = time.sleep,
    max_workers: int = 1,
) -> int:
    if iterations < 1:
        raise ValueError("iterations must be at least 1")
    if interval_seconds < 0:
        raise ValueError("interval_seconds must be non-negative")

    total = 0
    for index in range(iterations):
        total += collect_once(path, limit, timeout, proxy, max_workers)
        if index < iterations - 1 and interval_seconds > 0:
            sleep(interval_seconds)
    return total


def binary_snapshot_rows_from_gamma_markets(
    markets: Iterable[dict],
    book_fetcher: Callable[[str], dict],
    ts: Optional[str] = None,
    max_workers: int = 1,
    skip_book_errors: bool = False,
    errors: Optional[list] = None,
) -> List[dict]:
    if max_workers < 1:
        raise ValueError("max_workers must be at least 1")

    rows = []
    snapshot_ts = ts or _utc_now()
    selected_markets = []
    for market in markets:
        if not _is_binary_market(market):
            continue
        token_ids = _loads_json_list(market.get("clobTokenIds"))
        if len(token_ids) != 2:
            continue
        selected_markets.append((market, str(token_ids[0]), str(token_ids[1])))

    books_by_token_id = _fetch_books_by_token_id(
        [token_id for _, yes_token_id, no_token_id in selected_markets for token_id in [yes_token_id, no_token_id]],
        book_fetcher,
        max_workers,
        skip_errors=skip_book_errors,
        errors=errors,
    )
    for market, yes_token_id, no_token_id in selected_markets:
        market_id = str(market.get("id") or market.get("conditionId"))
        if yes_token_id not in books_by_token_id or no_token_id not in books_by_token_id:
            if skip_book_errors:
                _append_collection_error(
                    errors,
                    "market_skipped",
                    market_id=market_id,
                    token_id=",".join([yes_token_id, no_token_id]),
                    message="missing one or more CLOB books",
                )
                continue
            missing_token_id = yes_token_id if yes_token_id not in books_by_token_id else no_token_id
            raise KeyError(missing_token_id)
        try:
            yes_book = _normalized_book(books_by_token_id[yes_token_id])
            no_book = _normalized_book(books_by_token_id[no_token_id])
        except (KeyError, TypeError, ValueError) as exc:
            if not skip_book_errors:
                raise
            _append_collection_error(
                errors,
                "book_normalize_error",
                market_id=market_id,
                token_id=",".join([yes_token_id, no_token_id]),
                message=str(exc),
                error_type=exc.__class__.__name__,
            )
            continue
        yes_book["token_id"] = yes_token_id
        no_book["token_id"] = no_token_id
        rows.append(
            {
                "ts": snapshot_ts,
                "type": "binary_snapshot",
                "venue": "polymarket",
                "market_id": market_id,
                "question": market.get("question"),
                "fee_rate": market_fee_rate(market),
                "yes": yes_book,
                "no": no_book,
            }
        )
    return rows


def _fetch_books_by_token_id(
    token_ids: Iterable[str],
    book_fetcher: Callable[[str], dict],
    max_workers: int,
    skip_errors: bool = False,
    errors: Optional[list] = None,
) -> dict:
    ordered_token_ids = list(dict.fromkeys(str(token_id) for token_id in token_ids))
    if max_workers == 1 or len(ordered_token_ids) <= 1:
        books = {}
        for token_id in ordered_token_ids:
            try:
                books[token_id] = book_fetcher(token_id)
            except Exception as exc:
                if not skip_errors:
                    raise
                _append_collection_error(
                    errors,
                    "book_fetch_error",
                    token_id=token_id,
                    message=str(exc),
                    error_type=exc.__class__.__name__,
                )
        return books

    worker_count = min(max_workers, len(ordered_token_ids))
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = {executor.submit(book_fetcher, token_id): token_id for token_id in ordered_token_ids}
        books = {}
        for future in as_completed(futures):
            token_id = futures[future]
            try:
                books[token_id] = future.result()
            except Exception as exc:
                if not skip_errors:
                    raise
                _append_collection_error(
                    errors,
                    "book_fetch_error",
                    token_id=token_id,
                    message=str(exc),
                    error_type=exc.__class__.__name__,
                )
        return books


def _append_collection_error(
    errors: Optional[list],
    kind: str,
    *,
    message: str,
    token_id: Optional[str] = None,
    market_id: Optional[str] = None,
    error_type: Optional[str] = None,
) -> None:
    if errors is None:
        return
    row = {
        "kind": kind,
        "message": message,
    }
    if token_id is not None:
        row["token_id"] = token_id
    if market_id is not None:
        row["market_id"] = market_id
    if error_type is not None:
        row["error_type"] = error_type
    errors.append(row)


def raw_gamma_markets_from_ndjson(path: Path) -> List[dict]:
    markets_by_id = {}
    market_order = []
    with path.open() as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            row = json.loads(line)
            if row.get("type") != "raw_polymarket_gamma_market":
                continue
            raw = row.get("raw")
            if isinstance(raw, dict):
                market_id = str(row.get("market_id") or raw.get("id") or raw.get("conditionId") or "")
                if not market_id:
                    continue
                if market_id not in markets_by_id:
                    market_order.append(market_id)
                markets_by_id[market_id] = raw
    return [markets_by_id[market_id] for market_id in market_order]


def market_ids_from_rule_file(path: Path) -> set:
    row = json.loads(path.read_text())
    market_ids = set()
    for rule in row.get("implications", []):
        _add_if_present(market_ids, rule, "antecedent")
        _add_if_present(market_ids, rule, "consequent")
    for section in ["mutually_exclusive", "equivalent", "collectively_exhaustive", "complement"]:
        for rule in row.get(section, []):
            _add_if_present(market_ids, rule, "first")
            _add_if_present(market_ids, rule, "second")
    for rule in row.get("exhaustive_groups", []):
        for market_id in _market_ids_from_group_rule(rule):
            market_ids.add(market_id)
    if market_ids:
        return market_ids

    # Backward-compatible fallback for older candidate-only rule files.
    for candidate in row.get("candidates", []):
        if not _candidate_is_tradeable_pair(candidate):
            continue
        _add_if_present(market_ids, candidate, "market_a_id")
        _add_if_present(market_ids, candidate, "market_b_id")
    return market_ids


def expand_market_ids_with_neg_risk_groups(markets: Iterable[dict], market_ids: Iterable[str]) -> set:
    selected_aliases = {str(market_id).strip() for market_id in market_ids if market_id}
    if not selected_aliases:
        return selected_aliases

    markets_by_id = {}
    group_ids = set()
    selected_market_ids = set()
    alias_to_market_id = {}
    for market in markets:
        market_id = canonical_market_id(market)
        if not market_id:
            continue
        markets_by_id[market_id] = market
        aliases = market_id_aliases(market)
        for alias in aliases:
            alias_to_market_id[alias] = market_id
        if aliases & selected_aliases:
            selected_market_ids.add(market_id)
            group_id = str(market.get("negRiskMarketID") or "").strip()
            if group_id:
                group_ids.add(group_id)

    expanded = set(selected_market_ids)
    expanded.update(market_id for market_id in selected_aliases if market_id not in alias_to_market_id)
    for market_id, market in markets_by_id.items():
        if str(market.get("negRiskMarketID") or "").strip() in group_ids:
            expanded.add(market_id)
    return expanded


def limit_market_ids_by_gamma_order(
    markets: Iterable[dict],
    market_ids: Iterable[str],
    max_markets: Optional[int],
) -> set:
    markets = list(markets)
    alias_to_market_id = market_id_alias_map(markets)
    selected_market_ids = {
        alias_to_market_id.get(str(market_id).strip(), str(market_id).strip()) for market_id in market_ids if market_id
    }
    if max_markets is None:
        return selected_market_ids
    if max_markets < 1:
        raise ValueError("max_markets must be at least 1")

    ordered = []
    for market in markets:
        market_id = canonical_market_id(market)
        if market_id and market_id in selected_market_ids:
            ordered.append(market_id)
            if len(ordered) >= max_markets:
                return set(ordered)

    if len(ordered) >= max_markets:
        return set(ordered)
    remaining = sorted(selected_market_ids - set(ordered))
    return set(ordered + remaining[: max_markets - len(ordered)])


def canonical_market_id(market: dict) -> str:
    return str(market.get("id") or market.get("conditionId") or "").strip()


def market_id_aliases(market: dict) -> set:
    aliases = set()
    for key in ["id", "conditionId"]:
        value = market.get(key)
        if value:
            aliases.add(str(value).strip())
    return aliases


def market_id_alias_map(markets: Iterable[dict]) -> dict:
    alias_map = {}
    for market in markets:
        market_id = canonical_market_id(market)
        if not market_id:
            continue
        for alias in market_id_aliases(market):
            alias_map[alias] = market_id
    return alias_map


def _condition_ids_for_market_ids(markets: Iterable[dict], market_ids: Iterable[str]) -> dict:
    markets = list(markets)
    selected = {str(market_id).strip() for market_id in market_ids if str(market_id).strip()}
    if not selected:
        return {}
    alias_map = market_id_alias_map(markets)
    canonical_selected = {alias_map.get(market_id, market_id) for market_id in selected}
    condition_to_market_id = {}
    for market in markets:
        market_id = canonical_market_id(market)
        condition_id = str(market.get("conditionId") or "").strip()
        if not market_id or not condition_id:
            continue
        aliases = market_id_aliases(market)
        if market_id in canonical_selected or aliases & selected:
            condition_to_market_id[condition_id] = market_id
    for market_id in selected:
        if market_id.lower().startswith("0x") and market_id not in condition_to_market_id:
            condition_to_market_id[market_id] = market_id
    return condition_to_market_id


def _add_if_present(target: set, row: dict, key: str) -> None:
    value = row.get(key)
    if value:
        target.add(str(value))


def _market_ids_from_group_rule(rule: dict) -> List[str]:
    raw_market_ids = rule.get("market_ids")
    if raw_market_ids is None:
        raw_market_ids = rule.get("markets")
    if not isinstance(raw_market_ids, list):
        return []
    return [str(market_id) for market_id in raw_market_ids if market_id]


def _candidate_is_tradeable_pair(candidate: dict) -> bool:
    if candidate.get("relation_type") not in {
        "mutually_exclusive",
        "equivalent",
        "collectively_exhaustive",
        "complement",
    }:
        return False
    if candidate.get("trade_allowed") is False:
        return False
    if candidate.get("risk_flags"):
        return False
    return True


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


def _post_json(url: str, payload, timeout: float, proxy: Optional[str] = None):
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "accept": "application/json",
            "content-type": "application/json",
            "user-agent": "poly-strategy/0.1",
        },
        method="POST",
    )
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


def _trade_timestamp_to_iso(value) -> Optional[str]:
    if value is None or value == "":
        return None
    try:
        return datetime.fromtimestamp(float(value), tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    except (TypeError, ValueError, OSError):
        return str(value)


def _maybe_float(value) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


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
    if outcomes and len(outcomes) != 2:
        return False
    return len(_loads_json_list(market.get("clobTokenIds"))) == 2


def _loads_json_list(value) -> List[str]:
    if isinstance(value, list):
        return value
    if not value:
        return []
    try:
        loaded = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return []
    if not isinstance(loaded, list):
        return []
    return loaded


def market_fee_rate(market: dict) -> float:
    if not market.get("feesEnabled"):
        return 0.0
    fee_schedule = market.get("feeSchedule") or {}
    return float(fee_schedule.get("rate") or 0.0)


def _market_fee_rate(market: dict) -> float:
    return market_fee_rate(market)


def _normalized_book(book: dict) -> dict:
    return {
        "asks": _levels(book.get("asks", []), reverse=False),
        "bids": _levels(book.get("bids", []), reverse=True),
    }


def _levels(levels: Iterable[dict], reverse: bool) -> List[List[float]]:
    parsed = [[float(level["price"]), float(level["size"])] for level in levels]
    parsed.sort(key=lambda level: level[0], reverse=reverse)
    return parsed


def _kalshi_orderbook_payload(row: dict) -> dict:
    if "orderbook" in row and isinstance(row["orderbook"], dict):
        return row["orderbook"]
    if "orderbook_fp" in row and isinstance(row["orderbook_fp"], dict):
        return row["orderbook_fp"]
    return row if isinstance(row, dict) else {}


def _kalshi_levels(orderbook: dict, side: str) -> List[List[float]]:
    value = orderbook.get(side) or orderbook.get(f"{side}_dollars") or []
    parsed = []
    for level in value:
        price = size = None
        if isinstance(level, dict):
            price = level.get("price") or level.get("dollars") or level.get("yes_price") or level.get("no_price")
            size = level.get("size") or level.get("quantity") or level.get("contracts")
        elif isinstance(level, list) and len(level) >= 2:
            price, size = level[0], level[1]
        if price is None or size is None:
            continue
        parsed.append([_kalshi_price_to_probability(price), float(size)])
    parsed.sort(key=lambda row: row[0], reverse=True)
    return parsed


def _kalshi_price_to_probability(value) -> float:
    price = float(value)
    if price > 1.0:
        price = price / 100.0
    return round(price, 6)


def _complement_asks(bids: Iterable[List[float]]) -> List[List[float]]:
    asks = [[round(1.0 - price, 6), size] for price, size in bids]
    asks.sort(key=lambda row: row[0])
    return asks
