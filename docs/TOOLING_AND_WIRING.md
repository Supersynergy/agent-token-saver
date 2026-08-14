# Tooling and wiring

The core needs Python 3.11+. The installer copies only this repository's
doctor, ledger, compact default, skill and hooks. It never silently installs or
updates a third-party tool.

| Layer | Default | Purpose |
|---|---|---|
| Compact host policy | yes except `minimal` | preserve the same lean behavior across supported agents |
| Deterministic projection | yes | retain decisive lines before model context |
| Skill routing | prompt-gated | select zero or one relevant skill |
| RTK | Claude hook or explicit CLI | project noisy shell output |
| Structural source read | explicit/bounded | inspect code without a broad index |
| Ledger and audit | installed CLI | reconcile provider usage and visible layers |
| Graph, browser, remote fan-out | explicit session/spike | solve a concrete need, then leave |

## Host wiring

```text
Codex:  AGENTS default; prompt gate -> compact route; Stop -> session guard -> ledger
Claude: CLAUDE default; prompt gate -> compact route; Bash -> RTK; Agent -> worker capsule
Hermes: existing SOUL default; installed full skill
GG Coder: home AGENTS default; installed full skill
```

The `teams` profile adds the worker contract, not automatic fan-out. A prompt
hook must not launch a maintenance scan, broad index, browser or remote model.

## Update

1. Check release age and notes.
2. Install one tested update at a time.
3. Run the host smoke, `agent-token-saver doctor --profile teams --json`, and
   the repository checks.

`doctor` validates installer-owned files, hooks and the exact managed default
blocks. It does not claim that an optional CLI, private lane or credential is
usable.
