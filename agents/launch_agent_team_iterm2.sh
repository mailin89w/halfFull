#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PROVIDER="${1:-codex}"
MODE="${2:-safe}"
usage() {
  cat <<'EOF'
Usage:
  ./agents/launch_agent_team_iterm2.sh [codex|claude] [safe|auto]

Examples:
  ./agents/launch_agent_team_iterm2.sh
  ./agents/launch_agent_team_iterm2.sh codex safe
  ./agents/launch_agent_team_iterm2.sh claude safe

Environment overrides:
  CLAUDE_FLAGS   Extra flags appended when provider=claude
EOF
}

case "$PROVIDER" in
  codex|claude)
    ;;
  -h|--help|help)
    usage
    exit 0
    ;;
  *)
    echo "Unknown provider: $PROVIDER"
    usage
    exit 1
    ;;
esac

if ! command -v osascript >/dev/null 2>&1; then
  echo "osascript is required to control iTerm2."
  exit 1
fi

PM_CMD="cd $(printf %q "$REPO_ROOT") && $(printf %q "$REPO_ROOT/agents/run_agent.sh") $(printf %q "$PROVIDER") $(printf %q "$MODE") pm"
ML_CMD="cd $(printf %q "$REPO_ROOT") && $(printf %q "$REPO_ROOT/agents/run_agent.sh") $(printf %q "$PROVIDER") $(printf %q "$MODE") ml"
FS_CMD="cd $(printf %q "$REPO_ROOT") && $(printf %q "$REPO_ROOT/agents/run_agent.sh") $(printf %q "$PROVIDER") $(printf %q "$MODE") fs"

osascript \
  -e 'on run argv' \
  -e 'set pmCommand to item 1 of argv' \
  -e 'set mlCommand to item 2 of argv' \
  -e 'set fsCommand to item 3 of argv' \
  -e 'tell application "iTerm"' \
  -e '  activate' \
  -e '  set newWindow to (create window with default profile)' \
  -e '  tell newWindow' \
  -e '    tell current session to write text pmCommand' \
  -e '    set mlTab to (create tab with default profile)' \
  -e '    tell current session of mlTab to write text mlCommand' \
  -e '    set fsTab to (create tab with default profile)' \
  -e '    tell current session of fsTab to write text fsCommand' \
  -e '  end tell' \
  -e 'end tell' \
  -e 'end run' \
  "$PM_CMD" "$ML_CMD" "$FS_CMD"

echo "Opened PM, ML, and full-stack $PROVIDER tabs in iTerm2."
