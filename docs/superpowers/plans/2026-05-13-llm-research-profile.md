# LLM Research Profile Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the tested LLM provider order the default for discovery, rule promotion, and cross-platform verification without committing secrets or changing trading behavior.

**Architecture:** Add one shell profile loader that fills missing `OPENAI_*` provider settings from the benchmark-derived profile. Source it from the three mainline LLM scripts after `.env.local` loads and before they snapshot provider variables. Keep all keys external and preserve explicit user overrides unless force mode is enabled.

**Tech Stack:** Bash shell scripts, Python `pytest`, existing OpenAI-compatible client in `poly_strategy/openai_rules.py`.

---

## Files

- Create: `scripts/load_llm_research_profile.sh`
  - Single responsibility: export benchmark-derived provider defaults.
- Create: `tests/test_llm_research_profile.py`
  - Single responsibility: run the loader in controlled shell environments and assert exported variables.
- Modify: `scripts/refresh_discovery_watchlist.sh`
  - Source loader after `.env.local` and proxy setup, before provider variables are copied.
- Modify: `scripts/run_rule_promotion_once.sh`
  - Same loader source position.
- Modify: `scripts/run_cross_platform_scan_once.sh`
  - Same loader source position before cross-platform verifier command.

## Task 1: Add Loader Tests First

**Files:**
- Create: `tests/test_llm_research_profile.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_llm_research_profile.py`:

```python
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOADER = ROOT / "scripts" / "load_llm_research_profile.sh"


def run_loader(env):
    command = (
        "set -euo pipefail; "
        f"source {LOADER}; "
        "printf 'OPENAI_MODEL=%s\n' \"${OPENAI_MODEL-}\"; "
        "printf 'OPENAI_BASE_URL=%s\n' \"${OPENAI_BASE_URL-}\"; "
        "printf 'OPENAI_API_MODE=%s\n' \"${OPENAI_API_MODE-}\"; "
        "printf 'OPENAI_SECONDARY_MODEL=%s\n' \"${OPENAI_SECONDARY_MODEL-}\"; "
        "printf 'OPENAI_SECONDARY_BASE_URL=%s\n' \"${OPENAI_SECONDARY_BASE_URL-}\"; "
        "printf 'OPENAI_SECONDARY_API_MODE=%s\n' \"${OPENAI_SECONDARY_API_MODE-}\"; "
        "printf 'OPENAI_BACKUP_MODEL=%s\n' \"${OPENAI_BACKUP_MODEL-}\"; "
        "printf 'OPENAI_BACKUP_BASE_URL=%s\n' \"${OPENAI_BACKUP_BASE_URL-}\"; "
        "printf 'OPENAI_BACKUP_API_MODE=%s\n' \"${OPENAI_BACKUP_API_MODE-}\"; "
        "printf 'OPENAI_FALLBACK_MODEL=%s\n' \"${OPENAI_FALLBACK_MODEL-}\"; "
        "printf 'OPENAI_FALLBACK_BASE_URL=%s\n' \"${OPENAI_FALLBACK_BASE_URL-}\"; "
        "printf 'OPENAI_FALLBACK_API_MODE=%s\n' \"${OPENAI_FALLBACK_API_MODE-}\""
    )
    clean_env = {
        "PATH": os.environ.get("PATH", ""),
        "OPENAI_API_KEY": "primary-key",
        "OPENAI_SECONDARY_API_KEY": "secondary-key",
        "OPENAI_BACKUP_API_KEY": "backup-key",
        "OPENAI_FALLBACK_API_KEY": "fallback-key",
        **env,
    }
    result = subprocess.run(
        ["/bin/bash", "-lc", command],
        cwd=ROOT,
        env=clean_env,
        text=True,
        capture_output=True,
        check=True,
    )
    return dict(line.split("=", 1) for line in result.stdout.strip().splitlines())


def test_balanced_profile_exports_benchmark_provider_order():
    values = run_loader({})

    assert values["OPENAI_MODEL"] == "deepseek-v3-2-251201"
    assert values["OPENAI_BASE_URL"] == "https://windhub.cc/v1"
    assert values["OPENAI_API_MODE"] == "messages"
    assert values["OPENAI_SECONDARY_MODEL"] == "gemini-3.1-pro-preview"
    assert values["OPENAI_SECONDARY_BASE_URL"] == "https://api.xn--chy-js0fk50c.top/v1"
    assert values["OPENAI_SECONDARY_API_MODE"] == "chat"
    assert values["OPENAI_BACKUP_MODEL"] == "longcat-flash-chat"
    assert values["OPENAI_BACKUP_BASE_URL"] == "https://elysiver.h-e.top/v1"
    assert values["OPENAI_BACKUP_API_MODE"] == "chat"
    assert values["OPENAI_FALLBACK_MODEL"] == "gpt-5.4-mini"
    assert values["OPENAI_FALLBACK_BASE_URL"] == "https://api.wwcloud.app"
    assert values["OPENAI_FALLBACK_API_MODE"] == "responses"


def test_semantic_profile_uses_high_recall_primary_only():
    values = run_loader({"LLM_RESEARCH_PROFILE": "semantic"})

    assert values["OPENAI_MODEL"] == "doubao-seed-1-8-251228"
    assert values["OPENAI_BASE_URL"] == "https://windhub.cc/v1"
    assert values["OPENAI_API_MODE"] == "messages"
    assert values["OPENAI_BACKUP_MODEL"] == "longcat-flash-chat"


def test_loader_preserves_explicit_values_without_force():
    values = run_loader(
        {
            "OPENAI_MODEL": "manual-model",
            "OPENAI_BASE_URL": "https://manual.example/v1",
            "OPENAI_API_MODE": "chat",
        }
    )

    assert values["OPENAI_MODEL"] == "manual-model"
    assert values["OPENAI_BASE_URL"] == "https://manual.example/v1"
    assert values["OPENAI_API_MODE"] == "chat"


def test_force_replaces_explicit_values():
    values = run_loader(
        {
            "LLM_RESEARCH_PROFILE_FORCE": "1",
            "OPENAI_MODEL": "manual-model",
            "OPENAI_BASE_URL": "https://manual.example/v1",
            "OPENAI_API_MODE": "chat",
        }
    )

    assert values["OPENAI_MODEL"] == "deepseek-v3-2-251201"
    assert values["OPENAI_BASE_URL"] == "https://windhub.cc/v1"
    assert values["OPENAI_API_MODE"] == "messages"


def test_off_profile_makes_no_changes():
    values = run_loader({"LLM_RESEARCH_PROFILE": "off"})

    assert all(value == "" for value in values.values())


def test_missing_role_key_skips_that_role():
    values = run_loader({"OPENAI_BACKUP_API_KEY": ""})

    assert values["OPENAI_MODEL"] == "deepseek-v3-2-251201"
    assert values["OPENAI_BACKUP_MODEL"] == ""
    assert values["OPENAI_BACKUP_BASE_URL"] == ""
    assert values["OPENAI_BACKUP_API_MODE"] == ""


def test_verbose_output_does_not_print_keys():
    env = {
        "PATH": os.environ.get("PATH", ""),
        "OPENAI_API_KEY": "primary-secret",
        "OPENAI_SECONDARY_API_KEY": "secondary-secret",
        "OPENAI_BACKUP_API_KEY": "backup-secret",
        "OPENAI_FALLBACK_API_KEY": "fallback-secret",
        "LLM_RESEARCH_PROFILE_VERBOSE": "1",
    }
    result = subprocess.run(
        ["/bin/bash", "-lc", f"source {LOADER}"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )

    combined = result.stdout + result.stderr
    assert "primary-secret" not in combined
    assert "secondary-secret" not in combined
    assert "backup-secret" not in combined
    assert "fallback-secret" not in combined
    assert "deepseek-v3-2-251201" in combined
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
/Users/ww/Project/poly_strategy/.venv/bin/python -m pytest tests/test_llm_research_profile.py -q
```

Expected: fail because `scripts/load_llm_research_profile.sh` does not exist.

## Task 2: Implement Profile Loader

**Files:**
- Create: `scripts/load_llm_research_profile.sh`

- [ ] **Step 1: Implement minimal loader**

Create `scripts/load_llm_research_profile.sh`:

```bash
#!/usr/bin/env bash

llm_profile_is_true() {
  case "${1:-}" in
    1|true|TRUE|yes|YES|on|ON) return 0 ;;
    *) return 1 ;;
  esac
}

llm_profile_set_default() {
  local name="$1"
  local value="$2"
  if llm_profile_is_true "${LLM_RESEARCH_PROFILE_FORCE:-0}" || [[ -z "${!name:-}" ]]; then
    export "$name=$value"
  fi
}

llm_profile_set_role() {
  local key_name="$1"
  local model_name="$2"
  local base_url_name="$3"
  local api_mode_name="$4"
  local model_value="$5"
  local base_url_value="$6"
  local api_mode_value="$7"
  [[ -n "${!key_name:-}" ]] || return 0
  llm_profile_set_default "$model_name" "$model_value"
  llm_profile_set_default "$base_url_name" "$base_url_value"
  llm_profile_set_default "$api_mode_name" "$api_mode_value"
}

llm_profile_print_summary() {
  llm_profile_is_true "${LLM_RESEARCH_PROFILE_VERBOSE:-0}" || return 0
  {
    echo "llm_research_profile profile=${LLM_RESEARCH_PROFILE:-balanced}"
    echo "llm_provider role=primary model=${OPENAI_MODEL:-} api_mode=${OPENAI_API_MODE:-} base_url=${OPENAI_BASE_URL:-}"
    echo "llm_provider role=secondary model=${OPENAI_SECONDARY_MODEL:-} api_mode=${OPENAI_SECONDARY_API_MODE:-} base_url=${OPENAI_SECONDARY_BASE_URL:-}"
    echo "llm_provider role=backup model=${OPENAI_BACKUP_MODEL:-} api_mode=${OPENAI_BACKUP_API_MODE:-} base_url=${OPENAI_BACKUP_BASE_URL:-}"
    echo "llm_provider role=fallback model=${OPENAI_FALLBACK_MODEL:-} api_mode=${OPENAI_FALLBACK_API_MODE:-} base_url=${OPENAI_FALLBACK_BASE_URL:-}"
  } >&2
}

llm_research_profile="${LLM_RESEARCH_PROFILE:-balanced}"
case "$llm_research_profile" in
  off|none|disabled|0)
    return 0 2>/dev/null || exit 0
    ;;
  balanced)
    llm_profile_set_role OPENAI_API_KEY OPENAI_MODEL OPENAI_BASE_URL OPENAI_API_MODE \
      "deepseek-v3-2-251201" "https://windhub.cc/v1" "messages"
    ;;
  semantic)
    llm_profile_set_role OPENAI_API_KEY OPENAI_MODEL OPENAI_BASE_URL OPENAI_API_MODE \
      "doubao-seed-1-8-251228" "https://windhub.cc/v1" "messages"
    ;;
  *)
    echo "unsupported LLM_RESEARCH_PROFILE: $llm_research_profile" >&2
    return 2 2>/dev/null || exit 2
    ;;
esac

llm_profile_set_role OPENAI_SECONDARY_API_KEY OPENAI_SECONDARY_MODEL OPENAI_SECONDARY_BASE_URL OPENAI_SECONDARY_API_MODE \
  "gemini-3.1-pro-preview" "https://api.xn--chy-js0fk50c.top/v1" "chat"
llm_profile_set_role OPENAI_BACKUP_API_KEY OPENAI_BACKUP_MODEL OPENAI_BACKUP_BASE_URL OPENAI_BACKUP_API_MODE \
  "longcat-flash-chat" "https://elysiver.h-e.top/v1" "chat"
llm_profile_set_role OPENAI_FALLBACK_API_KEY OPENAI_FALLBACK_MODEL OPENAI_FALLBACK_BASE_URL OPENAI_FALLBACK_API_MODE \
  "gpt-5.4-mini" "https://api.wwcloud.app" "responses"

llm_profile_print_summary
```

- [ ] **Step 2: Run loader tests**

Run:

```bash
/Users/ww/Project/poly_strategy/.venv/bin/python -m pytest tests/test_llm_research_profile.py -q
```

Expected: all tests in `tests/test_llm_research_profile.py` pass.

- [ ] **Step 3: Commit**

```bash
git add scripts/load_llm_research_profile.sh tests/test_llm_research_profile.py
git commit -m "Add LLM research provider profile"
git push
```

## Task 3: Source Loader from Mainline Scripts

**Files:**
- Modify: `scripts/refresh_discovery_watchlist.sh`
- Modify: `scripts/run_rule_promotion_once.sh`
- Modify: `scripts/run_cross_platform_scan_once.sh`

- [ ] **Step 1: Write integration test**

Append to `tests/test_llm_research_profile.py`:

```python
def test_mainline_scripts_source_research_profile_loader():
    scripts = [
        ROOT / "scripts" / "refresh_discovery_watchlist.sh",
        ROOT / "scripts" / "run_rule_promotion_once.sh",
        ROOT / "scripts" / "run_cross_platform_scan_once.sh",
    ]

    for script in scripts:
        text = script.read_text(encoding="utf-8")
        assert "source scripts/load_llm_research_profile.sh" in text
```

- [ ] **Step 2: Run integration test to verify it fails**

Run:

```bash
/Users/ww/Project/poly_strategy/.venv/bin/python -m pytest tests/test_llm_research_profile.py::test_mainline_scripts_source_research_profile_loader -q
```

Expected: fail because the scripts do not source the loader yet.

- [ ] **Step 3: Modify each script**

In each target script, add this after `.env.local` loading and proxy setup, before provider variables are assigned:

```bash
if [[ -f scripts/load_llm_research_profile.sh ]]; then
  # shellcheck disable=SC1091
  source scripts/load_llm_research_profile.sh
fi
```

For `scripts/run_cross_platform_scan_once.sh`, add it after `.env.local` is sourced and before LLM verification command variables are consumed.

- [ ] **Step 4: Run integration test**

Run:

```bash
/Users/ww/Project/poly_strategy/.venv/bin/python -m pytest tests/test_llm_research_profile.py -q
```

Expected: all profile tests pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/refresh_discovery_watchlist.sh scripts/run_rule_promotion_once.sh scripts/run_cross_platform_scan_once.sh tests/test_llm_research_profile.py
git commit -m "Wire LLM profile into main scripts"
git push
```

## Task 4: Final Verification

**Files:**
- Verify all changed files.

- [ ] **Step 1: Static shell syntax**

Run:

```bash
bash -n scripts/load_llm_research_profile.sh
bash -n scripts/refresh_discovery_watchlist.sh
bash -n scripts/run_rule_promotion_once.sh
bash -n scripts/run_cross_platform_scan_once.sh
```

Expected: no output and exit code 0.

- [ ] **Step 2: Python compile**

Run:

```bash
/Users/ww/Project/poly_strategy/.venv/bin/python -m py_compile scripts/*.py poly_strategy/*.py
```

Expected: no output and exit code 0.

- [ ] **Step 3: Full test suite**

Run:

```bash
/Users/ww/Project/poly_strategy/.venv/bin/python -m pytest -q
```

Expected: all tests pass.

- [ ] **Step 4: Inspect git status**

Run:

```bash
git status --short --branch
```

Expected: clean branch on `main...origin/main`.
