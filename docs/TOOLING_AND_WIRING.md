# Tooling and wiring

The core needs Python 3.11+. The installer copies only this repository's
doctor, ledger, skill and hooks. It never silently installs or updates a
third-party tool.

| Layer | Default | Purpose |
|---|---|---|
| Deterministic projection | yes | retain decisive lines before model context |
| Skill routing | prompt-gated | select zero or one relevant skill |
| RTK | Claude hook or explicit CLI | project noisy shell output |
| Structural source read | explicit/bounded | inspect code without a broad index |
| Ledger and audit | installed CLI | reconcile provider usage and visible layers |
| Graph, browser, remote fan-out | explicit session/spike | solve a concrete need, then leave |

## Host wiring

```text
Codex:  prompt gate -> compact policy; Stop -> session guard -> ledger
Claude: prompt gate -> compact policy; Bash -> RTK; Agent -> worker capsule
Hermes/GG Coder: installed skill
```

The `teams` profile adds the worker contract, not automatic fan-out. A prompt
hook must not launch a maintenance scan, broad index, browser or remote model.

## Update

1. Check release age and notes.
2. Install one tested update at a time.
3. Run the host smoke, `agent-token-saver doctor --profile teams --json`, and
   the repository checks.

`doctor` validates installer-owned files and hooks. It does not claim that an
optional CLI, private lane or credential is usable.
