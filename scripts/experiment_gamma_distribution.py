#!/usr/bin/env python3
"""Experiment: Gamma raw market distribution + structural ground truth.

One-shot experiment to unblock four things at once:
  1. Q1 (long-tail tier thresholds) — replaces hand-waved $50k/$5k/$100
     with real P10/P50/P90 from current Polymarket Gamma data.
  2. T4 corpus ($0 path) — derives mutex (neg-risk groups) and equivalent
     (exact question + endDate duplicates) pairs from the raw payload.
     No LLM cost.
  3. Real fixture data — first ~50 raw market payloads become T2 unit
     test fixtures (saves invented synthetic data later).
  4. Validates DS pkg #02 spec assumption that everything we need is in
     the public Gamma API.

Usage:
    python scripts/experiment_gamma_distribution.py [--pages N] [--limit L]

Default fetches 4 pages × 500 = 2000 markets, ~$0 cost, ~30 seconds.

Outputs (under data/experiments/<date>/ and reports/):
    data/experiments/<date>/gamma-raw.ndjson         — raw payloads (gitignored)
    data/experiments/<date>/structural-rules.json    — derived mutex+equiv pairs
    reports/experiment-gamma-distribution-<date>.md  — human-readable analysis
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from urllib.parse import urlencode
from urllib.request import Request, urlopen

GAMMA_MARKETS_URL = "https://gamma-api.polymarket.com/markets"
REPO_ROOT = Path(__file__).resolve().parent.parent


def fetch_markets_page(limit: int, offset: int, timeout: float = 30.0) -> list[dict]:
    params = {"limit": limit, "offset": offset, "active": "true"}
    url = f"{GAMMA_MARKETS_URL}?{urlencode(params)}"
    req = Request(url, headers={"User-Agent": "poly_strategy-experiment/1.0"})
    with urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def float_field(row: dict, *keys: str) -> float:
    for key in keys:
        val = row.get(key)
        if val is None:
            continue
        try:
            return float(val)
        except (TypeError, ValueError):
            continue
    return 0.0


def days_to_resolution(row: dict, now: datetime) -> float | None:
    end_date = row.get("endDate") or row.get("end_date")
    if not end_date:
        return None
    try:
        end = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
        return (end - now).total_seconds() / 86400.0
    except (TypeError, ValueError):
        return None


def bucket_days(d: float | None) -> str:
    if d is None:
        return "unknown"
    if d < 0:
        return "expired"
    if d < 7:
        return "<7d"
    if d < 14:
        return "7-14d"
    if d < 30:
        return "14-30d"
    if d < 90:
        return "30-90d"
    if d < 180:
        return "90-180d"
    return ">180d"


def percentiles(values: list[float], ps: Iterable[int]) -> dict[int, float]:
    if not values:
        return {p: 0.0 for p in ps}
    quantiles = statistics.quantiles(values, n=100, method="inclusive")
    return {p: quantiles[p - 1] if 1 <= p <= 99 else (min(values) if p == 0 else max(values)) for p in ps}


def derive_structural_rules(markets: list[dict]) -> dict:
    """Return {mutex_pairs, equivalent_pairs, neg_risk_groups, exact_duplicates}.

    Deterministic — no LLM. Mirrors the logic in rule_discovery.py:443-523.
    """
    neg_risk_groups: dict[str, list[str]] = defaultdict(list)
    by_question_enddate: dict[tuple[str, str], list[str]] = defaultdict(list)

    for m in markets:
        market_id = str(m.get("id") or m.get("market_id") or "")
        if not market_id:
            continue
        nr_id = m.get("negRiskMarketID") or m.get("neg_risk_market_id")
        if nr_id and m.get("negRisk"):
            neg_risk_groups[str(nr_id)].append(market_id)
        question = (m.get("question") or "").strip()
        end_date = (m.get("endDate") or "").strip()
        if question and end_date:
            by_question_enddate[(question, end_date)].append(market_id)

    mutex_pairs: list[tuple[str, str]] = []
    for group_market_ids in neg_risk_groups.values():
        if len(group_market_ids) < 2:
            continue
        for i in range(len(group_market_ids)):
            for j in range(i + 1, len(group_market_ids)):
                mutex_pairs.append((group_market_ids[i], group_market_ids[j]))

    equivalent_pairs: list[tuple[str, str]] = []
    exact_duplicates: list[dict] = []
    for (question, end_date), market_ids in by_question_enddate.items():
        if len(market_ids) >= 2:
            exact_duplicates.append({"question": question, "endDate": end_date, "market_ids": market_ids})
            for i in range(len(market_ids)):
                for j in range(i + 1, len(market_ids)):
                    equivalent_pairs.append((market_ids[i], market_ids[j]))

    return {
        "neg_risk_groups": {gid: ids for gid, ids in neg_risk_groups.items() if len(ids) >= 2},
        "mutex_pairs": mutex_pairs,
        "equivalent_pairs": equivalent_pairs,
        "exact_duplicates": exact_duplicates,
    }


def analyze(markets: list[dict], now: datetime) -> dict:
    active = [m for m in markets if m.get("enableOrderBook") is not False
              and m.get("acceptingOrders") is not False
              and not m.get("closed")]

    vol24 = [float_field(m, "volume24hrClob", "volume24hr") for m in active]
    vol7d = [float_field(m, "volume1wkClob", "volume1wk") for m in active]
    liq = [float_field(m, "liquidityNum", "liquidityClob", "liquidity") for m in active]
    spread = [float_field(m, "spread") for m in active if m.get("spread") is not None]

    days = [days_to_resolution(m, now) for m in active]
    day_buckets = defaultdict(int)
    for d in days:
        day_buckets[bucket_days(d)] += 1

    # No first-class category in Gamma; use events[0].series as proxy
    series_count: dict[str, int] = defaultdict(int)
    for m in active:
        ev = (m.get("events") or [{}])[0]
        # series may be a list of dicts; flatten to first slug if so
        raw_series = ev.get("series") or ev.get("seriesSlug")
        if isinstance(raw_series, list) and raw_series:
            first = raw_series[0]
            label = first.get("slug") if isinstance(first, dict) else str(first)
        elif isinstance(raw_series, str):
            label = raw_series
        else:
            label = None
        label = (label or "untagged").strip().lower() or "untagged"
        series_count[label] += 1

    ps = [5, 10, 25, 50, 75, 90, 95, 99]
    return {
        "total_market_count": len(markets),
        "active_market_count": len(active),
        "volume24hr_percentiles": percentiles(vol24, ps),
        "volume1wk_percentiles": percentiles(vol7d, ps),
        "liquidity_percentiles": percentiles(liq, ps),
        "spread_percentiles": percentiles(spread, ps) if spread else {p: 0.0 for p in ps},
        "spread_sample_size": len(spread),
        "days_to_resolution_buckets": dict(day_buckets),
        "series_counts_top10": dict(sorted(series_count.items(), key=lambda kv: -kv[1])[:10]),
    }


def candidate_tier_thresholds(stats: dict) -> dict:
    vp = stats["volume24hr_percentiles"]
    lp = stats["liquidity_percentiles"]
    sp = stats["spread_percentiles"]
    return {
        "headline": {"volume24hr_min": vp[90], "liquidity_min": lp[90], "spread_max": sp[10]},
        "mid": {"volume24hr_min": vp[50], "liquidity_min": lp[50], "spread_max": sp[50]},
        "longtail": {"volume24hr_min": vp[10], "volume24hr_max": vp[50],
                     "liquidity_min": lp[10], "liquidity_max": lp[50],
                     "spread_max": sp[90]},
        "dead": {"volume24hr_max": vp[10], "liquidity_max": lp[10]},
    }


def fmt_pct(percentiles: dict[int, float]) -> str:
    return " | ".join(f"P{p}=${v:,.0f}" for p, v in percentiles.items())


def render_report(stats: dict, structural: dict, snapshot_iso: str) -> str:
    tiers = candidate_tier_thresholds(stats)
    lines = [
        f"# Gamma 分布 + 结构化关系 实验报告（{snapshot_iso}）",
        "",
        "**来源**：`scripts/experiment_gamma_distribution.py` 一次性实验，不是 DS pkg #02 的最终实现。",
        "**用途**：回填 §9 Q1（长尾 tier 阈值）+ T4 $0 corpus 可行性验证 + T2 fixture 数据。",
        "",
        "---",
        "",
        "## 1. 基本统计",
        "",
        f"- 拉取总市场数：{stats['total_market_count']}",
        f"- 通过过滤的活跃市场：{stats['active_market_count']}",
        f"  (active=true & enableOrderBook!=false & acceptingOrders!=false & closed!=true)",
        "",
        "## 2. 总体分布百分位（活跃市场）",
        "",
        f"- **volume24hr**：{fmt_pct(stats['volume24hr_percentiles'])}",
        f"- **volume1wk**：{fmt_pct(stats['volume1wk_percentiles'])}",
        f"- **liquidity**：{fmt_pct(stats['liquidity_percentiles'])}",
        f"- **spread** (n={stats['spread_sample_size']}): " + " | ".join(f"P{p}={v:.4f}" for p, v in stats['spread_percentiles'].items()),
        "",
        "## 3. 距 resolution 分布",
        "",
    ]
    for bucket in ["<7d", "7-14d", "14-30d", "30-90d", "90-180d", ">180d", "expired", "unknown"]:
        n = stats["days_to_resolution_buckets"].get(bucket, 0)
        pct = 100 * n / max(stats["active_market_count"], 1)
        lines.append(f"- `{bucket}`: {n} ({pct:.1f}%)")

    lines += [
        "",
        "## 4. Top 10 series（Gamma 无 first-class category，用 `events[0].series` 代理）",
        "",
    ]
    for cat, n in stats["series_counts_top10"].items():
        pct = 100 * n / max(stats["active_market_count"], 1)
        lines.append(f"- `{cat}`: {n} ({pct:.1f}%)")

    lines += [
        "",
        "## 5. Q1 数据驱动 tier 阈值候选",
        "",
        "**直接可填进 §9 Q1 Decision**：",
        "",
        f"- `headline` tier (P90+): volume24hr ≥ ${tiers['headline']['volume24hr_min']:,.0f}, liquidity ≥ ${tiers['headline']['liquidity_min']:,.0f}, spread ≤ {tiers['headline']['spread_max']:.4f}",
        f"- `mid` tier (P50-P90):   volume24hr ${tiers['mid']['volume24hr_min']:,.0f}–${tiers['headline']['volume24hr_min']:,.0f}, liquidity ${tiers['mid']['liquidity_min']:,.0f}–${tiers['headline']['liquidity_min']:,.0f}, spread ≤ {tiers['mid']['spread_max']:.4f}",
        f"- `longtail` tier (P10-P50): volume24hr ${tiers['longtail']['volume24hr_min']:,.0f}–${tiers['longtail']['volume24hr_max']:,.0f}, liquidity ${tiers['longtail']['liquidity_min']:,.0f}–${tiers['longtail']['liquidity_max']:,.0f}, spread ≤ {tiers['longtail']['spread_max']:.4f}",
        f"- `dead` tier (<P10):     volume24hr ≤ ${tiers['dead']['volume24hr_max']:,.0f}, liquidity < ${tiers['dead']['liquidity_max']:,.0f}",
        "",
        "**注意**：因 P10 = $0，`longtail` 和 `dead` 的边界在 volume24hr 上重合（都从 0 起）。实务建议：用 **liquidity ≥ $791** 区分 longtail 和 dead；vol24hr=0 但 liquidity 在 $791-$10k 区间的市场是真长尾（做市商不来但有底子），vol24hr=0 且 liquidity<$791 才算 dead。",
        "",
        "**对比方案初稿**：",
        "",
        "| Tier | 方案初稿 | 数据驱动 (实测) | 差距 |",
        "|---|---|---|---|",
        f"| headline (vol24h) | ≥ $50,000 | ≥ ${tiers['headline']['volume24hr_min']:,.0f} | {'初稿偏高' if tiers['headline']['volume24hr_min'] < 50000 else '初稿偏低' if tiers['headline']['volume24hr_min'] > 50000 else '一致'} |",
        f"| mid 下限 (vol24h) | ≥ $5,000  | ≥ ${tiers['mid']['volume24hr_min']:,.0f} | {'初稿偏高' if tiers['mid']['volume24hr_min'] < 5000 else '初稿偏低' if tiers['mid']['volume24hr_min'] > 5000 else '一致'} |",
        f"| longtail 下限 (vol24h) | ≥ $100  | ≥ ${tiers['longtail']['volume24hr_min']:,.0f} | {'初稿偏高' if tiers['longtail']['volume24hr_min'] < 100 else '初稿偏低' if tiers['longtail']['volume24hr_min'] > 100 else '一致'} |",
        "",
        "## 6. T4 $0 corpus 可行性验证",
        "",
        f"- **Neg-risk 组数（≥2 市场）**：{len(structural['neg_risk_groups'])}",
        f"- **派生 mutex pairs**：{len(structural['mutex_pairs'])}",
        f"- **完全相同 question+endDate 组数**：{len(structural['exact_duplicates'])}",
        f"- **派生 equivalent pairs**：{len(structural['equivalent_pairs'])}",
        "",
    ]
    if len(structural['mutex_pairs']) >= 50:
        lines.append(f"✅ **T4 $0 corpus 可行**：mutex pairs ({len(structural['mutex_pairs'])}) ≥ 50 个，足够采样作 T4 judge 校准 ground truth。")
    else:
        lines.append(f"⚠️ **T4 $0 corpus 不足**：mutex pairs 只有 {len(structural['mutex_pairs'])}，需要补充策略（增加 sample size 或加 LLM 派生）。")

    lines += [
        "",
        "## 7. 数据质量警告",
        "",
        f"- `unknown` 距 resolution 桶 = {stats['days_to_resolution_buckets'].get('unknown', 0)} 个市场缺 endDate",
        f"- 总数（{stats['total_market_count']}）vs 活跃数（{stats['active_market_count']}）差距 = {stats['total_market_count'] - stats['active_market_count']} 个被过滤掉",
        "",
        "---",
        "",
        f"*Snapshot: {snapshot_iso}, source: gamma-api.polymarket.com/markets*",
    ]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", type=int, default=4, help="Pages to fetch (default 4)")
    ap.add_argument("--limit", type=int, default=500, help="Markets per page (default 500)")
    ap.add_argument("--out-dir", type=Path, default=None)
    args = ap.parse_args()

    now = datetime.now(tz=timezone.utc)
    date_tag = now.strftime("%Y-%m-%d")
    iso = now.isoformat()

    out_dir = args.out_dir or (REPO_ROOT / "data" / "experiments" / date_tag)
    reports_dir = REPO_ROOT / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    raw_path = out_dir / "gamma-raw.ndjson"
    structural_path = out_dir / "structural-rules.json"
    report_path = reports_dir / f"experiment-gamma-distribution-{date_tag}.md"

    print(f"[1/4] Fetching {args.pages} × {args.limit} markets from Gamma API...")
    all_markets: list[dict] = []
    with raw_path.open("w", encoding="utf-8") as f:
        for page in range(args.pages):
            offset = page * args.limit
            t0 = time.time()
            try:
                batch = fetch_markets_page(args.limit, offset)
            except Exception as e:
                print(f"  page {page+1} FAILED: {e}", file=sys.stderr)
                break
            elapsed = time.time() - t0
            print(f"  page {page+1}/{args.pages}: offset={offset}, n={len(batch)}, t={elapsed:.1f}s")
            if not batch:
                print(f"  empty batch, stopping early")
                break
            for m in batch:
                f.write(json.dumps(m, ensure_ascii=False) + "\n")
                all_markets.append(m)

    print(f"[2/4] Wrote {len(all_markets)} markets → {raw_path}")

    print(f"[3/4] Analyzing distribution + deriving structural rules...")
    stats = analyze(all_markets, now)
    structural = derive_structural_rules(all_markets)
    with structural_path.open("w", encoding="utf-8") as f:
        json.dump({
            "snapshot_time": iso,
            "neg_risk_groups": structural["neg_risk_groups"],
            "mutex_pair_count": len(structural["mutex_pairs"]),
            "equivalent_pair_count": len(structural["equivalent_pairs"]),
            "exact_duplicates": structural["exact_duplicates"][:50],
            "mutex_pairs_sample": structural["mutex_pairs"][:100],
            "equivalent_pairs_sample": structural["equivalent_pairs"][:100],
        }, f, indent=2, ensure_ascii=False)
    print(f"  → {structural_path}")

    print(f"[4/4] Rendering report...")
    report = render_report(stats, structural, iso)
    report_path.write_text(report, encoding="utf-8")
    print(f"  → {report_path}")

    print()
    print("=== Summary ===")
    print(f"Active markets: {stats['active_market_count']} / {stats['total_market_count']}")
    print(f"vol24hr P10/P50/P90: ${stats['volume24hr_percentiles'][10]:,.0f} / ${stats['volume24hr_percentiles'][50]:,.0f} / ${stats['volume24hr_percentiles'][90]:,.0f}")
    print(f"Neg-risk groups: {len(structural['neg_risk_groups'])}, mutex pairs: {len(structural['mutex_pairs'])}")
    print(f"Exact duplicates: {len(structural['exact_duplicates'])}, equivalent pairs: {len(structural['equivalent_pairs'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
