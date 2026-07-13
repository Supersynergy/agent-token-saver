# Clean CODEX_HOME full-context probe — 2026-07-13

Codex CLI 0.144.2. Each arm used a new `CODEX_HOME` containing authentication
only. User configuration, rules, hooks and history were ignored. Provider usage
comes from the final `turn.completed` JSONL event.

## Warm no-tool control

Same exact-answer oracle in every arm: `ATS_NEUTRAL_OK`.

| Arm | Input runs | Median input | Cached subset | Output | Accepted |
|---|---:|---:|---:|---:|:---:|
| Auth-only baseline | 11,365 / 11,355 | 11,360 | 8,960 | 9 | yes |
| Installed saver skill, hooks off | 11,440 / 11,434 | 11,437 | 8,960 | 9 | yes |

The saver arm used **77 more input tokens (+0.68%)**. This is the expected
backfire boundary: a trivial no-tool task has nothing large to project, so even
a small skill description costs more than it saves.

## Tool-output probe

The prompt required one process-list command plus the exact success response.
The baseline reported 22,878 input tokens. The attempted transparent rewrite
arm reported 23,040 input tokens, but no command-execution event was observable
for the required path. The acceptance oracle therefore failed.

Current Codex documentation notes incomplete `PreToolUse` coverage for newer
`unified_exec` shell paths. The release does not claim transparent Codex RTK
rewrite parity. Codex uses skill/CLI guidance; Claude uses RTK's native hook.

## Verdict

- Neutral installation: proven separately by the fresh-HOME CI smoke.
- Trivial full-provider turn: **no saving; +0.68% overhead**.
- Context-heavy provider end-to-end saving: **not yet proven on neutral Codex**.
- The 146.1x result remains a dated accepted-payload/component benchmark, not a
  complete provider-request multiplier.
