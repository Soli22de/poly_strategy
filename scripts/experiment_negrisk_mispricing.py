#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Experiment 7: Long-tail neg-risk mispricing survey.

The first experiment that actually addresses the alpha question
"is there money to be made in long-tail neg-risk markets?" instead
of optimizing extraction infrastructure.

Approach:
  1. Group all markets by `negRiskMarketID` (already done in experiment 1).
  2. For each neg-risk group with >=2 members:
       a. Sum bestAsk across members (this is the cost to "buy the whole basket")
       b. If sum < 1.0 → potential cheap basket arb (buy all, exactly one wins, profit = 1 - sum - fees)
       c. If sum > 1.0 → potential expensive basket (sell all, but harder mechanically)
  3. Adjust for fees: cost_with_fee = sum(p_i + feeRate * p_i * (1-p_i))
  4. Flag long-tail groups: at least one member with vol24hr < $40 (P50 of all markets per experiment 1)
  5. Report groups where edge > 0 (raw) and edge > 0 (after fees) and edge > 1% (worth pursuing).

Important caveats baked into the output:
  - We DO NOT assume neg-risk groups are exhaustive. Some groups have an
    "Other" / "Another candidate" market making them exhaustive; some
    don't. Flag is_likely_exhaustive heuristically (look for "Other" /
    "Another" in member questions).
  - bestAsk may be stale; for production execution we'd verify via CLOB
    /book endpoint. This is a feasibility survey, not a trade signal.
  - Slippage at thin-liquidity longtail markets can be huge; raw bestAsk
    alone doesn't tell us deliverable quantity. We DO record liquidity
    so reader can judge.

Usage:
    python scripts/experiment_negrisk_mispricing.py \
        --raw data/experiments/2026-05-12/gamma-raw.ndjson

Outputs:
    reports/experiment-negrisk-mispricing-<date>.md
    data/experiments/<date>/negrisk-mispricing-candidates.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def parse_outcomes(value) -> list[str]:
    """outcomes is sometimes stringified JSON, sometimes a list."""
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            v = json.loads(value)
            return v if isinstance(v, list) else []
        except json.JSONDecodeError:
            return []
    return []


def to_float(x, default: float | None = None) -> float | None:
    if x is None:
        return default
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


EXHAUSTIVE_MARKERS = [
    "no one ", "none of ", "another candidate", "another team", "another player",
    "another company", "another country", "another person",
    "any other", "no candidate", "neither ",
    "someone else", "no one named", "no one announced", "no one wins",
    "no one is", "no one will", "no one ends",
    "different player", "different team",
]


def is_other_marker(question: str) -> bool:
    """Does this single question look like a catch-all member?"""
    q = (question or "").lower()
    return any(token in q for token in EXHAUSTIVE_MARKERS)


def classify_exhaustiveness(members: list[dict]) -> str:
    """Return one of:
      - 'explicit_other'  : group has a member like 'No one wins' / 'Another candidate'.
                            High confidence that the group is structurally exhaustive.
      - 'binary'          : exactly 2 members. Often exhaustive (D/R, Yes/No)
                            but vulnerable to surprise third outcomes.
      - 'open_set'        : 3+ members with no catch-all. Almost certainly NOT
                            exhaustive — risk of all-NO resolution.
    """
    if any(m.get("is_other_marker") for m in members):
        return "explicit_other"
    if len(members) == 2:
        return "binary"
    return "open_set"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", type=Path, required=True)
    ap.add_argument("--longtail-vol24hr-max", type=float, default=40.0,
                    help="A group is 'longtail' if at least one member has vol24hr below this. Default $40 = P50 per experiment 1.")
    ap.add_argument("--fee-rate-default", type=float, default=0.015,
                    help="Fallback feeRate if feeSchedule.rate missing. 1.5%% ~ category midpoint.")
    ap.add_argument("--report-top-n", type=int, default=50)
    args = ap.parse_args()

    print(f"Loading {args.raw}...")
    markets = []
    with args.raw.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                markets.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    print(f"  {len(markets)} markets loaded")

    # Group by negRiskMarketID
    groups: dict[str, list[dict]] = defaultdict(list)
    for m in markets:
        nrid = m.get("negRiskMarketID")
        if nrid and m.get("negRisk"):
            groups[nrid].append(m)
    multi_groups = {k: v for k, v in groups.items() if len(v) >= 2}
    print(f"  {len(groups)} neg-risk groups, {len(multi_groups)} with >=2 members")

    # Analyse each group
    candidates: list[dict] = []
    for nrid, members in multi_groups.items():
        # Pull ask, fee, liquidity, vol for each
        member_rows = []
        for m in members:
            ask = to_float(m.get("bestAsk"))
            bid = to_float(m.get("bestBid"))
            vol24 = to_float(m.get("volume24hr"), 0.0) or to_float(m.get("volume24hrClob"), 0.0) or 0.0
            liq = to_float(m.get("liquidityNum"), 0.0) or to_float(m.get("liquidityClob"), 0.0) or 0.0
            fee_schedule = m.get("feeSchedule") or {}
            fee_rate = to_float(fee_schedule.get("rate"), args.fee_rate_default)
            if not m.get("feesEnabled", True):
                fee_rate = 0.0
            member_rows.append({
                "market_id": str(m.get("id") or "?"),
                "question": (m.get("question") or "")[:80],
                "bestAsk": ask,
                "bestBid": bid,
                "vol24hr": vol24,
                "liquidity": liq,
                "fee_rate": fee_rate,
                "category_tags": [],
                "is_other_marker": is_other_marker(m.get("question") or ""),
            })

        # Drop groups where any member is missing bestAsk
        if any(r["bestAsk"] is None for r in member_rows):
            continue
        # Drop groups where any ask is 0 or 1 (closed / fully resolved)
        if any(r["bestAsk"] is None or r["bestAsk"] <= 0.001 or r["bestAsk"] >= 0.999 for r in member_rows):
            # Skip — these are degenerate
            continue

        sum_ask = sum(r["bestAsk"] for r in member_rows)
        # Fee-adjusted basket cost (buy all YES, fee on each leg)
        fee_total = sum(r["fee_rate"] * r["bestAsk"] * (1 - r["bestAsk"]) for r in member_rows)
        cost_with_fee = sum_ask + fee_total

        # Edge if exhaustive (exactly one wins, payout=1.0)
        edge_raw = 1.0 - sum_ask
        edge_after_fee = 1.0 - cost_with_fee

        # Longtail filter: at least one member has vol24hr below threshold
        has_longtail_member = any(r["vol24hr"] < args.longtail_vol24hr_max for r in member_rows)
        # Liquidity minimum (per Q1 decision $787 = P10 for our dead/longtail cutoff)
        min_liquidity = min(r["liquidity"] for r in member_rows)

        # Tiered exhaustiveness classification (replaces broken size>=8 heuristic)
        exhaustiveness = classify_exhaustiveness(member_rows)
        has_other_member = any(r["is_other_marker"] for r in member_rows)
        # For backwards-compat keep this field but make it strict: only 'explicit_other'
        # counts as truly exhaustive. Binary groups are flagged separately.
        confidently_exhaustive = (exhaustiveness == "explicit_other")

        candidates.append({
            "negRiskMarketID": nrid,
            "size": len(member_rows),
            "sum_ask": round(sum_ask, 4),
            "fee_total": round(fee_total, 5),
            "cost_with_fee": round(cost_with_fee, 4),
            "edge_raw": round(edge_raw, 4),
            "edge_after_fee": round(edge_after_fee, 4),
            "has_longtail_member": has_longtail_member,
            "min_liquidity": round(min_liquidity, 0),
            "exhaustiveness": exhaustiveness,
            "confidently_exhaustive": confidently_exhaustive,
            "has_other_member": has_other_member,
            "members": member_rows,
        })

    # Stats
    n_total = len(candidates)
    n_long = sum(1 for c in candidates if c["has_longtail_member"])
    n_confidently_exh = sum(1 for c in candidates if c["confidently_exhaustive"])
    n_binary = sum(1 for c in candidates if c["exhaustiveness"] == "binary")
    n_open = sum(1 for c in candidates if c["exhaustiveness"] == "open_set")
    n_sub1 = sum(1 for c in candidates if c["sum_ask"] < 1.0)
    n_edge_pos = sum(1 for c in candidates if c["edge_after_fee"] > 0)
    n_edge_1pct = sum(1 for c in candidates if c["edge_after_fee"] > 0.01)

    # The strict candidate funnel: confidently exhaustive AND edge > 0 after fees
    strict_candidates = [c for c in candidates
                         if c["confidently_exhaustive"] and c["edge_after_fee"] > 0]
    binary_candidates = [c for c in candidates
                         if c["exhaustiveness"] == "binary" and c["edge_after_fee"] > 0]
    open_set_false_positives = [c for c in candidates
                                if c["exhaustiveness"] == "open_set" and c["edge_after_fee"] > 0]

    # Sort each group by post-fee edge
    candidates.sort(key=lambda c: c["edge_after_fee"], reverse=True)
    strict_candidates.sort(key=lambda c: c["edge_after_fee"], reverse=True)
    binary_candidates.sort(key=lambda c: c["edge_after_fee"], reverse=True)
    open_set_false_positives.sort(key=lambda c: c["edge_after_fee"], reverse=True)

    now = datetime.now(tz=timezone.utc)
    iso = now.isoformat()
    date_tag = now.strftime("%Y-%m-%d")

    # JSON dump
    out_dir = REPO_ROOT / "data" / "experiments" / date_tag
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "negrisk-mispricing-candidates.json"
    with json_path.open("w", encoding="utf-8") as f:
        json.dump({
            "snapshot_time": iso,
            "total_groups": n_total,
            "stats": {
                "groups_with_longtail_member": n_long,
                "groups_confidently_exhaustive": n_confidently_exh,
                "groups_binary": n_binary,
                "groups_open_set": n_open,
                "groups_sum_ask_below_1": n_sub1,
                "groups_edge_after_fee_positive_all": n_edge_pos,
                "groups_edge_after_fee_above_1pct_all": n_edge_1pct,
            },
            "strict_candidates": strict_candidates,
            "binary_candidates": binary_candidates[:args.report_top_n],
            "open_set_false_positives": open_set_false_positives[:args.report_top_n],
        }, f, indent=2, ensure_ascii=False)

    # Markdown report
    def fmt_row(c, exh_label):
        lt = "✓" if c["has_longtail_member"] else ""
        return f"| `{c['negRiskMarketID'][:14]}…` | {c['size']} | {c['sum_ask']:.4f} | {c['fee_total']:.5f} | {c['edge_after_fee']:+.4f} | {lt} | {exh_label} | ${c['min_liquidity']:,.0f} |"

    def render_member_table(c):
        out = ["| Member | bestAsk | bestBid | vol24hr | liquidity | fee_rate |",
               "|---|---:|---:|---:|---:|---:|"]
        for r in c["members"]:
            marker = " 🅾️" if r["is_other_marker"] else ""
            out.append(f"| {r['question'][:60]}{marker} | {r['bestAsk']:.3f} | {r['bestBid'] if r['bestBid'] is not None else '—'} | ${r['vol24hr']:,.0f} | ${r['liquidity']:,.0f} | {r['fee_rate']:.4f} |")
        return out

    lines = [
        f"# 长尾 Neg-Risk Mispricing 普查实验 7 (refined)（{iso}）",
        "",
        "**v2 改进**：原版 `likely_exhaustive` 把 size≥8 当作 exhaustive 是错的（Nobel 奖那种 20 人候选其实根本不穷举）。",
        "本版分级：",
        "- `explicit_other` —— 组内含 'No one / None / Another' 等显式 catch-all member（高置信度真 exhaustive）",
        "- `binary` —— 正好 2 个 member（多数是 D/R 政治对决，**可能**穷举，但有第三方风险）",
        "- `open_set` —— 3+ member 且无 catch-all（**几乎确定不穷举**，basket arb 是假信号）",
        "",
        "---",
        "",
        "## 1. 重新分级后的基本计数",
        "",
        f"- 总 neg-risk 组（已过滤 ask 退化）：**{n_total}**",
        f"  - `explicit_other`（**高置信度 exhaustive**）：**{n_confidently_exh}** ({100*n_confidently_exh/max(n_total,1):.0f}%)",
        f"  - `binary` (2 member)：**{n_binary}** ({100*n_binary/max(n_total,1):.0f}%)",
        f"  - `open_set` (假阳性源)：**{n_open}** ({100*n_open/max(n_total,1):.0f}%)",
        f"- 含至少 1 个长尾成员（vol24hr < ${args.longtail_vol24hr_max:.0f}）：**{n_long}** ({100*n_long/max(n_total,1):.0f}%)",
        "",
        "## 2. Sum(YES_ask) < 1.0 + edge>0 三分类",
        "",
        f"- **Strict 候选**（confidently exhaustive + edge_after_fee > 0）：**{len(strict_candidates)}**",
        f"- **Binary 候选**（2 member + edge > 0，需验证第三方风险）：**{len(binary_candidates)}**",
        f"- **Open-set 假阳性**（看似 edge > 0 但 basket 不穷举，**不能交易**）：**{len(open_set_false_positives)}**",
        "",
        "## 3. Strict 候选（真正值得 follow-up）",
        "",
    ]
    if not strict_candidates:
        lines.append("**无**。今天 snapshot 下，没有任何 neg-risk 组同时满足：含 `No one`/`Other` 显式 member，且 sum_ask < 1 - fee。")
        lines.append("")
        lines.append("Thesis 解读：长尾 neg-risk 的真 exhaustive 套利**目前已被定价干净**（至少在 06:13 snapshot 这个时刻）。")
    else:
        lines.append("| Group | size | sum_ask | fee_total | edge_after_fee | longtail? | tier | min_liq |")
        lines.append("|---|---:|---:|---:|---:|:---:|:---:|---:|")
        for c in strict_candidates:
            lines.append(fmt_row(c, "explicit"))
        lines.append("")
        for i, c in enumerate(strict_candidates, 1):
            lines.append(f"### Strict #{i}: edge = {c['edge_after_fee']:+.4f}, longtail = {c['has_longtail_member']}")
            lines.append("")
            lines += render_member_table(c)
            lines.append("")

    lines += [
        "## 4. Binary 候选（edge > 0，第三方风险待评估）",
        "",
    ]
    if not binary_candidates:
        lines.append("无 binary 组 edge > 0。")
    else:
        lines.append("| Group | sum_ask | edge_after_fee | longtail? | min_liq |")
        lines.append("|---|---:|---:|:---:|---:|")
        for c in binary_candidates[:15]:
            lt = "✓" if c["has_longtail_member"] else ""
            lines.append(f"| `{c['negRiskMarketID'][:14]}…` | {c['sum_ask']:.4f} | {c['edge_after_fee']:+.4f} | {lt} | ${c['min_liquidity']:,.0f} |")
        lines.append("")
        lines.append("Binary 组样本（前 3 个完整 member 表）：")
        lines.append("")
        for i, c in enumerate(binary_candidates[:3], 1):
            lines.append(f"#### Binary #{i}: edge = {c['edge_after_fee']:+.4f}")
            lines += render_member_table(c)
            lines.append("")

    lines += [
        "## 5. Open-set 假阳性（**不是机会**，列出避免误导）",
        "",
        "这些组 sum < 1 看似有 arb edge，但成员列表**不穷举** —— 实际胜者不在列表里时整篮归零。**不要根据这些数据交易。**",
        "",
    ]
    if not open_set_false_positives:
        lines.append("无。")
    else:
        lines.append("| Group | size | sum_ask | edge_after_fee | sample question |")
        lines.append("|---|---:|---:|---:|---|")
        for c in open_set_false_positives[:10]:
            sample_q = c["members"][0]["question"][:50] if c["members"] else "?"
            lines.append(f"| `{c['negRiskMarketID'][:14]}…` | {c['size']} | {c['sum_ask']:.4f} | {c['edge_after_fee']:+.4f} | {sample_q}… |")

    lines += [
        "",
        "## 6. 重要警告（读结果前必看）",
        "",
        "- **bestAsk 是 snapshot 时刻的最优挂单价**，不是任意可成交数量的均价。Long-tail 市场上 bestAsk 后面可能只挂 $5 的深度。",
        "- **fee_rate** 取每市场自带的 `feeSchedule.rate`；feesEnabled=False 的市场记 0。",
        "- **strict 也只是 'confidently exhaustive' 的启发式判定**，不是结构保证。生产时需要看 Polymarket Neg Risk Adapter 合约的实际配置。",
        "- **slippage 可能吃掉所有 edge** —— 实际交易前需要用 CLOB `/book` 端点核对深度。",
        "",
        "## 7. 真正要回答的问题",
        "",
        f"- 今天 snapshot 下，**confidently exhaustive 且 edge > 0 after fees 的组数 = {len(strict_candidates)}**。",
        f"  - 长尾子集 = {sum(1 for c in strict_candidates if c['has_longtail_member'])}",
        f"- 进入下一步的条件：用 CLOB orderbook 复核这 {len(strict_candidates)} 个候选的真实可成交深度，剔除 slippage 吃掉 edge 的，剩多少是真 alpha。",
        "",
        f"---\n*Snapshot: {iso}*",
    ]
    report_path = REPO_ROOT / "reports" / f"experiment-negrisk-mispricing-{date_tag}.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8")

    # Console summary
    print()
    print("=== Summary ===")
    print(f"Total neg-risk groups analyzed: {n_total}")
    print(f"  explicit_other (confidently exhaustive): {n_confidently_exh}")
    print(f"  binary (2 members):                       {n_binary}")
    print(f"  open_set (NOT exhaustive, false signal):  {n_open}")
    print()
    print(f"STRICT candidates (confidently_exh + edge>0): {len(strict_candidates)}")
    print(f"  of which longtail:                          {sum(1 for c in strict_candidates if c['has_longtail_member'])}")
    print(f"BINARY candidates (2-member + edge>0):        {len(binary_candidates)}")
    print(f"OPEN-SET false positives:                     {len(open_set_false_positives)}")
    print(f"\nReport: {report_path}")
    print(f"JSON: {json_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
