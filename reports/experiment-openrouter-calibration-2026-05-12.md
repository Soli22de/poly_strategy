# OpenRouter Gemini Flash 校准实验报告（2026-05-12T06:50:07.649967+00:00）

**Model**: `google/gemini-2.0-flash-001`
**Sample**: n=5 markets, random.seed=42
**Prompt**: V2 strict (verbatim grounding + injection defense)

## 1. 总体指标

- schema_ok: 5/5 (100%)
- grounding_ok: 5/5 (100%)
- 总输入 tokens: 2760
- 总输出 tokens: 1985
- 平均输入/call: 552
- 平均输出/call: 397
- 平均延迟: 3.2s

## 2. 实际成本 vs 估算

- 实际：$0.001070 / 5 calls = **$0.000214/call**
- PR #6 估算：$0.000090/call
- 差距：需修正备忘录
- 推算 2000 markets 完整 T2 跑：$0.43

## 3. 每市场细节

### Market 1: `630772` — "Will the Democrats win the Maine Senate race in 2026?"
- description_len: 852
- schema_ok: True, grounding_ok: True, clauses: 2, ambiguity: 0.2
- tokens: 565 in + 355 out, elapsed: 3.6s
- sample clause: type=`deadline`, source_substring=`2026 midterm Maine U.S. Senate election...`

### Market 2: `679652` — "Will Christina Loren Clement be the Republican nominee for Senate in Georgia?"
- description_len: 399
- schema_ok: True, grounding_ok: True, clauses: 2, ambiguity: 0.3
- tokens: 459 in + 278 out, elapsed: 2.4s
- sample clause: type=`tiebreaker`, source_substring=`If no 2026 Georgia Republican Senate Primary takes place, this market will resol...`

### Market 3: `582320` — "Will Rennes finish in the top 4 of the Ligue 1 2025–26 standings?"
- description_len: 661
- schema_ok: True, grounding_ok: True, clauses: 3, ambiguity: 0.2
- tokens: 553 in + 384 out, elapsed: 2.9s
- sample clause: type=`deadline`, source_substring=`October 1, 2026...`

### Market 4: `630845` — "Will the Republicans win the New Hampshire Senate race in 2026?"
- description_len: 860
- schema_ok: True, grounding_ok: True, clauses: 2, ambiguity: 0.3
- tokens: 566 in + 357 out, elapsed: 2.9s
- sample clause: type=`deadline`, source_substring=`2026 midterm New Hampshire U.S. Senate election...`

### Market 5: `681026` — "Will DNM (DEK) win the most seats at the Cyprus House of Representatives electio"
- description_len: 1107
- schema_ok: True, grounding_ok: True, clauses: 5, ambiguity: 0.2
- tokens: 617 in + 611 out, elapsed: 4.0s
- sample clause: type=`deadline`, source_substring=`May 24, 2026...`
