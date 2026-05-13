# LLM Research Profile Mainline Integration Design

Date: 2026-05-13

## Goal

Wire the LLM benchmark results into the production research pipeline so rule discovery, rule promotion, and cross-platform verification use the best tested provider order by default.

This change is configuration orchestration only. It must not enable live trading, place orders, or commit API keys.

## Current Context

The project already supports OpenAI-compatible provider variables:

- `OPENAI_MODEL`, `OPENAI_BASE_URL`, `OPENAI_API_MODE`, `OPENAI_API_KEY`
- `OPENAI_SECONDARY_*`
- `OPENAI_BACKUP_*`
- `OPENAI_FALLBACK_*`

The following mainline scripts consume those variables:

- `scripts/refresh_discovery_watchlist.sh`
- `scripts/run_rule_promotion_once.sh`
- `scripts/run_cross_platform_scan_once.sh`

The benchmark summary is in `reports/experiment-llm-complex-recognition-consolidated-summary-2026-05-13.md`.

## Selected Profile

Default profile name: `balanced`

Provider order:

| Role | Provider result | Base URL | API mode | Reason |
|---|---|---|---|---|
| primary | `windhub/deepseek-v3-2-251201` | `https://windhub.cc/v1` | `messages` | Best balance of strict recall and latency among stable candidates |
| secondary | `secondary/gemini-3.1-pro-preview` | `https://api.xn--chy-js0fk50c.top/v1` | `chat` | Formal CLI smoke passed; lower semantic strength but fast |
| backup | `elysiver/longcat-flash-chat` | `https://elysiver.h-e.top/v1` | `chat` | Best stable elysiver result, good recall and moderate latency |
| fallback | `gpt-5.4` on the original responses endpoint | `https://api.wwcloud.app` | `responses` | More expensive high-capability last resort |

Optional profile: `semantic`

- primary becomes `windhub/doubao-seed-1-8-251228/messages`
- other roles remain the same
- use for manual high-confidence research runs, not routine background loops

## Proposed Implementation

Add a small shell profile loader:

- `scripts/load_llm_research_profile.sh`

Responsibilities:

- Export the provider variables above for a selected profile.
- Default to `LLM_RESEARCH_PROFILE=balanced`.
- Never define API keys directly.
- Only assign provider roles whose matching key variables are already present.
- Preserve explicit user overrides unless `LLM_RESEARCH_PROFILE_FORCE=1`.
- Print a sanitized provider summary when `LLM_RESEARCH_PROFILE_VERBOSE=1`.

Key mapping:

| Role | Required key variable |
|---|---|
| primary/windhub | `OPENAI_API_KEY` |
| secondary/new middle provider | `OPENAI_SECONDARY_API_KEY` |
| backup/elysiver | `OPENAI_BACKUP_API_KEY` |
| fallback/original responses endpoint | `OPENAI_FALLBACK_API_KEY` |

The loader should set models, modes, and base URLs but leave key values untouched.

## Mainline Integration Points

Source the loader after `.env.local` is loaded and before provider variables are read in:

- `scripts/refresh_discovery_watchlist.sh`
- `scripts/run_rule_promotion_once.sh`
- `scripts/run_cross_platform_scan_once.sh`

`scripts/background_manager.sh` does not need direct model logic. It already delegates to those scripts.

## Behavior

Default run:

1. `.env.local` loads secrets and base endpoint values.
2. `load_llm_research_profile.sh` fills missing model/mode/base-url values from the benchmark profile.
3. Existing provider health checks and retry/fallback behavior remain responsible for runtime failures.
4. The scripts continue to write current logs such as `discover_provider label=...` and `rule_promotion_provider label=...`.

Override examples:

- Set `OPENAI_MODEL=...` to override only the primary model.
- Set `LLM_RESEARCH_PROFILE=semantic` for the slow high-recall primary.
- Set `LLM_RESEARCH_PROFILE_FORCE=1` to replace all profile-managed model/mode/base-url values.
- Set `LLM_RESEARCH_PROFILE=off` to disable the loader.

## Error Handling

- Missing key for a role should not hard-fail profile loading; it should skip that role.
- Existing script behavior decides whether no usable provider is fatal.
- Unsupported profile names should fail early with a clear message.
- The loader must not echo keys or full secret-bearing environment values.

## Testing

Add shell-focused tests that run the loader in a clean environment and assert:

- `balanced` exports the expected provider order.
- explicit user overrides are preserved by default.
- `LLM_RESEARCH_PROFILE_FORCE=1` replaces explicit values.
- `LLM_RESEARCH_PROFILE=off` makes no changes.
- no output contains API keys when verbose mode is enabled.

Add integration-level tests for the three mainline scripts if practical by sourcing them in a controlled shell or by extracting profile application into a testable function. If full script sourcing is too heavy, test the loader plus one small wrapper contract: scripts can source it without requiring keys.

## Non-Goals

- Do not change LLM prompts in this task.
- Do not re-run the full expensive benchmark suite.
- Do not turn on live execution.
- Do not write secrets into tracked files.
- Do not replace provider health checks; the loader only sets defaults.

## Success Criteria

- Mainline LLM paths use the benchmark-derived provider order without manual `.env.local` model edits.
- User overrides still work.
- Fallback remains available for the original responses endpoint.
- Tests cover the profile selection and override behavior.
- Full test suite passes after implementation.
