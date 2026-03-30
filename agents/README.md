# Agent Team Setup

This folder contains role prompts for a 3-agent team:

- `pm.md`
- `ml-engineer.md`
- `full-stack.md`

## Launch in iTerm2

From the repo root:

```bash
chmod +x agents/launch_agent_team_iterm2.sh
chmod +x agents/run_agent.sh
chmod +x agents/kickoff_team_iterm2.sh
./agents/launch_agent_team_iterm2.sh
```

Providers and modes:

```bash
./agents/launch_agent_team_iterm2.sh codex safe
./agents/launch_agent_team_iterm2.sh codex auto
./agents/launch_agent_team_iterm2.sh claude safe
```

Kick off the team with one shared goal:

```bash
./agents/kickoff_team_iterm2.sh "Improve the assessment results experience and tighten eval quality" codex safe
```

- Default is `codex safe`.
- `safe` uses Codex workspace-write sandboxing with approvals on request.
- `auto` uses Codex `--full-auto` for faster local execution.
- For Claude, the script passes the role prompt directly to `claude` and lets you add extra CLI flags via `CLAUDE_FLAGS`.
- `launch_agent_team_iterm2.sh` opens three titled tabs: `PM`, `ML`, and `FS`.
- `kickoff_team_iterm2.sh` opens the tabs and sends each role an initial task based on one shared goal.

Example:

```bash
CLAUDE_FLAGS="--dangerously-skip-permissions" ./agents/launch_agent_team_iterm2.sh claude safe
```

## Recommended working agreement

- PM agent owns planning, handoff, and acceptance criteria.
- ML agent owns `evals/`, `models/`, `bayesian/`, and data scripts.
- Full-stack agent owns `frontend/` and `api/`.
- Ask each role to summarize decisions in plain text before another role depends on them.
- Avoid having multiple roles edit the same file tree at the same time.
- If you use Claude Code, confirm the local CLI flags once with `claude --help` and set `CLAUDE_FLAGS` accordingly.

## Example kickoff message for the PM pane

```text
Create a 1-week execution plan for the next highest-impact improvement to HalfFull. Split the work into PM, ML, and full-stack tracks with clear acceptance criteria.
```
