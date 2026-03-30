#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PROVIDER="${1:?provider required}"
MODE="${2:?mode required}"
ROLE="${3:?role required}"

resolve_cli_bin() {
  local provider="$1"

  if command -v "$provider" >/dev/null 2>&1; then
    command -v "$provider"
    return 0
  fi

  case "$provider" in
    codex)
      if [[ -x "/Applications/Codex.app/Contents/Resources/codex" ]]; then
        printf "%s\n" "/Applications/Codex.app/Contents/Resources/codex"
        return 0
      fi
      ;;
    claude)
      if [[ -x "$HOME/.local/bin/claude" ]]; then
        printf "%s\n" "$HOME/.local/bin/claude"
        return 0
      fi
      ;;
  esac

  return 1
}

role_prompt_path() {
  case "$1" in
    pm)
      printf "%s\n" "$REPO_ROOT/agents/prompts/pm.md"
      ;;
    ml)
      printf "%s\n" "$REPO_ROOT/agents/prompts/ml-engineer.md"
      ;;
    fs)
      printf "%s\n" "$REPO_ROOT/agents/prompts/full-stack.md"
      ;;
    *)
      echo "Unknown role: $1" >&2
      exit 1
      ;;
  esac
}

tab_title() {
  case "$1" in
    pm) printf "%s\n" "PM" ;;
    ml) printf "%s\n" "ML" ;;
    fs) printf "%s\n" "FS" ;;
  esac
}

if ! CLI_BIN="$(resolve_cli_bin "$PROVIDER")"; then
  echo "$PROVIDER CLI not found in PATH or known install locations."
  exit 1
fi

PROMPT_PATH="$(role_prompt_path "$ROLE")"
ROLE_PROMPT="$(tr '\n' ' ' < "$PROMPT_PATH")"
TITLE="$(tab_title "$ROLE")"

printf '\033]0;%s\007\033]1;%s\007' "$TITLE" "$TITLE"
cd "$REPO_ROOT"

case "$PROVIDER" in
  codex)
    case "$MODE" in
      auto)
        exec "$CLI_BIN" --full-auto --no-alt-screen "$ROLE_PROMPT"
        ;;
      safe)
        exec "$CLI_BIN" --sandbox workspace-write --ask-for-approval on-request --no-alt-screen "$ROLE_PROMPT"
        ;;
      *)
        echo "Unknown mode: $MODE" >&2
        exit 1
        ;;
    esac
    ;;
  claude)
    if [[ -n "${CLAUDE_FLAGS:-}" ]]; then
      # shellcheck disable=SC2206
      CLAUDE_ARGS=(${CLAUDE_FLAGS})
      exec "$CLI_BIN" "${CLAUDE_ARGS[@]}" "$ROLE_PROMPT"
    fi
    exec "$CLI_BIN" "$ROLE_PROMPT"
    ;;
  *)
    echo "Unknown provider: $PROVIDER" >&2
    exit 1
    ;;
esac
