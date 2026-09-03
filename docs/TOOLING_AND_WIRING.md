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
| Verification wrapper | `ats-verify` | compact on green, complete on red; owns the exit code |
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

## Verification path

`ats-verify` runs one check, once, and passes its exit code through. It keeps
the full raw log on disk and prints a projection: a few lines when green, every
decisive line when red with a raw-tail floor so a red result is never empty.

When RTK is installed, its per-tool `pipe` filter is offered as a *second*
candidate projection of the already-captured output — the command is never
re-executed. Adoption is per run and by measurement: a candidate must still
contain a signal line, and the smallest surviving candidate wins.

No filter is adopted globally, because none wins globally. On this machine
`cargo-test` wins at every size, `pytest` wins on green runs and short red ones,
and `mypy`, `tsc` and `ruff-check` lose to the builtin on the shapes measured.
A red `mypy`/`tsc` run saves almost nothing by design: when every line is a
diagnostic, completeness beats compactness. See the addendum in
`TOKEN_SAVER_RESEARCH_2026-07-13.md` for the byte counts.

This ordering is deliberate. RTK's `pytest` **wrapper** was observed printing
zero bytes for a failing test while returning exit 1, so no filter is trusted
to own execution or to be the sole source of evidence.

The Stop guard counts `ats-verify` as a verification command and reads its
`ats-verify: red exit=N` verdict line, so wrapped checks still reach the
outcome ledger.

`doctor` validates installer-owned files, hooks and the exact managed default
blocks. It does not claim that an optional CLI, private lane or credential is
usable.
