import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOADER = ROOT / "scripts" / "load_llm_research_profile.sh"


def run_loader(env):
    command = (
        "set -euo pipefail; "
        f"source {LOADER}; "
        "printf 'OPENAI_MODEL=%s\\n' \"${OPENAI_MODEL-}\"; "
        "printf 'OPENAI_BASE_URL=%s\\n' \"${OPENAI_BASE_URL-}\"; "
        "printf 'OPENAI_API_MODE=%s\\n' \"${OPENAI_API_MODE-}\"; "
        "printf 'OPENAI_SECONDARY_MODEL=%s\\n' \"${OPENAI_SECONDARY_MODEL-}\"; "
        "printf 'OPENAI_SECONDARY_BASE_URL=%s\\n' \"${OPENAI_SECONDARY_BASE_URL-}\"; "
        "printf 'OPENAI_SECONDARY_API_MODE=%s\\n' \"${OPENAI_SECONDARY_API_MODE-}\"; "
        "printf 'OPENAI_BACKUP_MODEL=%s\\n' \"${OPENAI_BACKUP_MODEL-}\"; "
        "printf 'OPENAI_BACKUP_BASE_URL=%s\\n' \"${OPENAI_BACKUP_BASE_URL-}\"; "
        "printf 'OPENAI_BACKUP_API_MODE=%s\\n' \"${OPENAI_BACKUP_API_MODE-}\"; "
        "printf 'OPENAI_FALLBACK_MODEL=%s\\n' \"${OPENAI_FALLBACK_MODEL-}\"; "
        "printf 'OPENAI_FALLBACK_BASE_URL=%s\\n' \"${OPENAI_FALLBACK_BASE_URL-}\"; "
        "printf 'OPENAI_FALLBACK_API_MODE=%s\\n' \"${OPENAI_FALLBACK_API_MODE-}\""
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
    assert values["OPENAI_FALLBACK_MODEL"] == "gpt-5.4"
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


def test_mainline_scripts_source_research_profile_loader():
    scripts = [
        ROOT / "scripts" / "refresh_discovery_watchlist.sh",
        ROOT / "scripts" / "run_rule_promotion_once.sh",
        ROOT / "scripts" / "run_cross_platform_scan_once.sh",
    ]

    for script in scripts:
        text = script.read_text(encoding="utf-8")
        assert "source scripts/load_llm_research_profile.sh" in text
