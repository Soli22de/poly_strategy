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
