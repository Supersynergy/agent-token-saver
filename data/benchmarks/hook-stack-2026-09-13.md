# Installed hook stack benchmark — 2026-09-13

Source: `$HOME/.claude/settings.json`. 4 timed runs per hook plus empty/garbage-stdin
fail-open probes. Blocking exit codes (1/2) count as decisions, not crashes;
a timeout or signal exit fails the check.

| Event | Hook | Case | p50 ms | p95 ms | stdout B | exits | probes | fail-open |
|---|---|---|---:|---:|---:|---|---|:--:|
| PostToolUse | `… $HOME/.ultimate-token-saver/bin/token-tracker.py` | bash_ok | 32.7 | 34.2 | 0 | [0] | [0, 0] | yes |
| PostToolUse | `…h $HOME/projects/cmux-vault/bin/claude-cmux-title` | bash_ok | 102.1 | 126.2 | 0 | [0] | [0, 0] | yes |
| PostToolUse | `/bin/bash $HOME/.claude/hooks/auto-fmt.sh` | bash_ok | 35.8 | 37.5 | 0 | [0] | [0, 0] | yes |
| PostToolUse | `…ns/3.14.4/bin/python3 $HOME/.local/bin/si observe` | bash_ok | 62.1 | 69.3 | 0 | [0] | [0, 0] | yes |
| PreToolUse | `rtk hook claude` | bash_ls | 30.8 | 31.8 | 169 | [0] | [0, 0] | yes |
| PreToolUse | `…/bash $HOME/.claude/hooks/pretooluse-pii-guard.sh` | bash_ls | 55.5 | 57.9 | 0 | [0] | [0, 0] | yes |
| PreToolUse | `/bin/bash $HOME/.claude/hooks/secret-guard.sh` | bash_ls | 32.4 | 33.8 | 0 | [0] | [0, 0] | yes |
| PreToolUse | `/bin/bash $HOME/.claude/hooks/protect-prod.sh` | bash_ls | 32.8 | 33.2 | 0 | [0] | [0, 0] | yes |
| PreToolUse | `…rew/bin/shellfirm check --stdin --format json --exit-code` | bash_ls | 58.0 | 79.2 | 170 | [0] | [0, 64] | yes |
| PreToolUse | `/bin/bash $HOME/.claude/hooks/superweb-default.sh` | bash_ls | 15.1 | 18.3 | 0 | [0] | [0, 0] | yes |
| PreToolUse | `…s/master/.agent-token-saver/hooks/agent-worker-capsule.py` | bash_ls | 30.6 | 31.2 | 0 | [0] | [0, 0] | yes |
| SessionEnd | `…ers/master/projects/cmux-vault/bin/claude-cmux-title stop` | clear | 102.1 | 108.5 | 0 | [0] | [0, 0] | yes |
| SessionEnd | `/bin/bash $HOME/.claude/hooks/session-diary.sh` | clear | 42.5 | 45.5 | 0 | [0] | [0, 0] | yes |
| SessionEnd | `…/bash $HOME/.claude/hooks/session-distill-hook.sh` | clear | 25.8 | 27.8 | 0 | [0] | [0, 0] | yes |
| SessionStart | `…h $HOME/projects/cmux-vault/bin/claude-cmux-title` | startup | 107.0 | 108.2 | 0 | [0] | [0, 0] | yes |
| SessionStart | `/bin/bash $HOME/.claude/hooks/rtk-trust-check.sh` | startup | 28.6 | 37.3 | 0 | [0] | [0, 0] | yes |
| SessionStart | `…/bash $HOME/.claude/hooks/session-resume-greet.sh` | startup | 347.1 | 514.3 | 0 | [0] | [0, 0] | yes |
| SessionStart | `…bash $HOME/.claude/hooks/synapse/session_start.sh` | startup | 4108.4 | 4145.2 | 0 | [0] | [0, 0] | yes |
| SessionStart | `…claude/cts/skills/claude-restore/bin/claude-session-track` | startup | 36.4 | 38.7 | 0 | [0] | [0, 0] | yes |
| SessionStart | `bd prime --hook-json` | startup | 80.9 | 91.7 | 79 | [0] | [0, 0] | yes |
| SessionStart | `"$HOME/.claude/hooks/context-mode-cache-heal.mjs"` | startup | 41.8 | 47.3 | 0 | [0] | [0, 0] | yes |
| Stop | `…ers/master/projects/cmux-vault/bin/claude-cmux-title stop` | first_stop | 138.1 | 177.7 | 0 | [0] | [0, 0] | yes |
| Stop | `…/bash $HOME/.claude/hooks/synapse/stop_extract.sh` | first_stop | 42.2 | 45.0 | 0 | [0] | [0, 0] | yes |
| Stop | `$HOME/.claude/hooks/stop-verify-gate.py` | first_stop | 46.3 | 59.2 | 2 | [0] | [0, 0] | yes |
| Stop | `…rs/master/.agent-token-saver/hooks/token-session-guard.py` | first_stop | 37.7 | 48.2 | 2 | [0] | [0, 0] | yes |
| UserPromptSubmit | `…h $HOME/projects/cmux-vault/bin/claude-cmux-title` | trivial | 94.1 | 106.7 | 0 | [0] | [0, 0] | yes |
| UserPromptSubmit | `…h $HOME/projects/cmux-vault/bin/claude-cmux-title` | saver_route | 96.5 | 97.7 | 0 | [0] | [0, 0] | yes |
| UserPromptSubmit | `…bash $HOME/.claude/hooks/synapse/prompt_submit.sh` | trivial | 67.1 | 70.5 | 0 | [0] | [0, 0] | yes |
| UserPromptSubmit | `…bash $HOME/.claude/hooks/synapse/prompt_submit.sh` | saver_route | 4078.4 | 4085.8 | 0 | [0] | [0, 0] | yes |
| UserPromptSubmit | `/bin/bash $HOME/.claude/hooks/session-diary.sh` | trivial | 42.5 | 47.7 | 0 | [0] | [0, 0] | yes |
| UserPromptSubmit | `/bin/bash $HOME/.claude/hooks/session-diary.sh` | saver_route | 43.0 | 43.5 | 0 | [0] | [0, 0] | yes |
| UserPromptSubmit | `…sers/master/BASE/projects/base-control-plane/base.py hook` | trivial | 81.9 | 91.6 | 0 | [0] | [0, 0] | yes |
| UserPromptSubmit | `…sers/master/BASE/projects/base-control-plane/base.py hook` | saver_route | 96.2 | 115.8 | 0 | [0] | [0, 0] | yes |
| UserPromptSubmit | `codegraph prompt-hook` | trivial | 63.3 | 78.7 | 0 | [0] | [0, 0] | yes |
| UserPromptSubmit | `codegraph prompt-hook` | saver_route | 64.1 | 74.2 | 0 | [0] | [0, 0] | yes |
| UserPromptSubmit | `…ers/master/.agent-token-saver/hooks/token-stack-prompt.py` | trivial | 30.6 | 30.8 | 0 | [0] | [0, 0] | yes |
| UserPromptSubmit | `…ers/master/.agent-token-saver/hooks/token-stack-prompt.py` | saver_route | 32.1 | 34.5 | 509 | [0] | [0, 0] | yes |

## Combined per event (sequential, config order)

| Event | hooks | chain ms | chain stdout B |
|---|---:|---:|---:|
| PostToolUse | 4 | 241.0 | 0 |
| PreToolUse | 7 | 253.0 | 339 |
| SessionEnd | 3 | 177.4 | 0 |
| SessionStart | 7 | 4827.5 | 79 |
| Stop | 4 | 233.8 | 4 |
| UserPromptSubmit | 6 | 379.7 | 0 |
