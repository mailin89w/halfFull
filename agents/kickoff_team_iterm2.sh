#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
GOAL="${1:-}"
PROVIDER="${2:-codex}"
MODE="${3:-safe}"

usage() {
  cat <<'EOF'
Usage:
  ./agents/kickoff_team_iterm2.sh "goal for the team" [codex|claude] [safe|auto]

Example:
  ./agents/kickoff_team_iterm2.sh "Improve the assessment results experience and tighten eval quality" codex safe
EOF
}

if [[ -z "$GOAL" ]]; then
  usage
  exit 1
fi

if ! command -v osascript >/dev/null 2>&1; then
  echo "osascript is required to control iTerm2."
  exit 1
fi

"$REPO_ROOT/agents/launch_agent_team_iterm2.sh" "$PROVIDER" "$MODE"

PM_TASK="Goal: $GOAL

Create a concrete plan for this goal. Split it into PM, ML, and full-stack tasks with acceptance criteria, dependencies, and a recommended execution order. Then keep acting as coordinator and ask the other two agents for short status updates."

ML_TASK="Goal: $GOAL

You are the ML owner. Inspect the current evals/models/scripts surface area relevant to this goal and propose the smallest high-impact ML or evaluation task you can own. If the PM has not handed you a task yet, do lightweight exploration only and summarize likely ML risks, opportunities, and the best next task."

FS_TASK="Goal: $GOAL

You are the full-stack owner. Inspect the current frontend/api surface area relevant to this goal and propose the smallest high-impact implementation task you can own. If the PM has not handed you a task yet, do lightweight exploration only and summarize likely product and integration opportunities."

osascript \
  -e 'on run argv' \
  -e 'set pmTask to item 1 of argv' \
  -e 'set mlTask to item 2 of argv' \
  -e 'set fsTask to item 3 of argv' \
  -e 'tell application "iTerm"' \
  -e '  tell current window' \
  -e '    delay 2' \
  -e '    tell current session of current tab to write text pmTask' \
  -e '    tell current session of tab 2 to write text mlTask' \
  -e '    tell current session of tab 3 to write text fsTask' \
  -e '  end tell' \
  -e 'end tell' \
  -e 'end run' \
  "$PM_TASK" "$ML_TASK" "$FS_TASK"

echo "Opened team tabs and sent kickoff tasks."
