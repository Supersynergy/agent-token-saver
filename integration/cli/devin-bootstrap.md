# Devin Bootstrap — Token-Saver Repo Instructions

Drop-in block for `AGENTS.md` or `.devin/instructions.md`. Devin reads this at
session start; no hook required. The block references the Devin-specific wrapper
`devin-token-saver.sh`, which sources the universal `agent-token-saver.sh` and
adds `devin-*` backward-compat aliases on top of the universal `ats-*` / `goal-*`
functions.

## Token-Saver (Devin profile)

**Source at session start:**
```bash
source scripts/devin-token-saver.sh   # sources agent-token-saver.sh + devin-* aliases
devin-token-doctor                     # alias for ats-doctor
```

**Before loading a skill:**
```bash
si route "<task>" --max 1 --strict --json
```
Load at most **one** primary skill. Never load the router skill itself. If `si`
returns nothing, proceed without a skill.

**Before spawning a Delegate subagent:**
- Write a 300–700-token capsule (see `ats-capsule-template`, alias: `devin-capsule-template`).
- One independent closed objective per worker.
- Zero or one routed skill per worker — never the controller's catalog.
- No parent transcript to children.
- Max **three** workers. Max **three** attempts per worker.
- Result: ≤500-token summary pointing to evidence (paths + line ranges).

**Shell aliases installed by the wrapper:**
- `ps` → `rtk ps` (fail-open pass-through if `rtk` missing)
- `gitdiff` → `rtk git diff`
- `gitlog` → `rtk git log --oneline -20`
- `dockerlogs` → `rtk docker logs`
- `journalctl` → `rtk journalctl`
- `catlog` → `rtk cat` (use for `*.log` files; do not alias `cat` globally)

**Post-session:**
```bash
devin-token-ledger run.jsonl delegate1.jsonl delegate2.jsonl   # alias for ats-token-ledger
```
This wraps `agent-token-ledger` with Devin defaults (`ATS_AGENT_NAME=devin`,
`ATS_ACTIVE_SKILL=.agents/skills/agent-token-saver-devin/SKILL.md`, provider codex,
`--require-complete-team`, `--require-within-guard`, AGENTS.md as component).
Inspect `unattributed_input_tokens` in the output — that is the host-instruction,
tool-schema and plugin-catalog tax.

## Rules

- **No MCP server in the default profile.** CLI / file / JSON seams only.
  `context-mode` and `Graphify` are on-demand for one session, never always-hot.
- **No auto-loading skills.** `si` is an explicit CLI call.
- **No Ponytail / Caveman** in the default profile — instruction tokens can
  cost more than they save on short answers.
- **Keep `AGENTS.md` slim.** Push deep content to Devin's Knowledge Base
  (`SKILL.md`, `SUBAGENT_CONTEXT_PROTOCOL.md`, `FULL_CONTEXT_MEASUREMENT.md`).
- **Fail-open.** Missing `rtk` / `si` / `agent-token-ledger` → skip silently,
  never block the task.

## Profile selection

| Profile | Use |
|---|---|
| `minimal` | Pure CLI / ledger, no skill. |
| `lean` | Default coding session. |
| `teams` | Delegate subagents (bounded controller/worker). |
| `heavy` | Large logs / deep code graph — `context-mode`, `Graphify`, `CodeGraph` on demand. |

## See also

- `.agents/skills/agent-token-saver-devin/SKILL.md` — full Devin profile.
- `docs/SUBAGENT_CONTEXT_PROTOCOL.md` — capsule format, break-even rule.
- `docs/CLI_FIRST_POLICY.md` — why CLI beats MCP by default.
