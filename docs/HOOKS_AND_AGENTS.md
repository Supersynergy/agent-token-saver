# Agent integration

| Host | Managed surface | Guarantee |
|---|---|---|
| Codex CLI | compact block in `~/.codex/AGENTS.md`; `UserPromptSubmit` prompt gate; `Stop` session guard | No transparent shell rewrite claim |
| Claude Code | compact block in `~/.claude/CLAUDE.md`; RTK for Bash when present; prompt gate; Stop guard; teams worker capsule | Worker hook only for `teams` |
| Hermes | compact block in an existing `~/.hermes/SOUL.md`; Agent Skill | Never create `SOUL.md` or mutate YAML |
| GG Coder | compact block in `~/AGENTS.md`; Markdown skill | Uses GG Coder's parent instruction discovery |
| Other agents | repo-local `SKILL.md` plus CLI/JSON | Explicit invocation |

## Contract

- Hooks read JSON stdin and emit valid JSON or nothing.
- Installation merges and backs up existing Codex/Claude JSON; repeated runs
  deduplicate managed commands.
- Lean/teams/heavy install one hash-verified compact default into each selected
  host's real instruction surface. Existing text is preserved and backed up;
  `minimal` removes only the marker-owned block.
- Prompt routing is strict: zero or one skill; explicit `$SkillName` wins.
- The normal route emits a compact policy. The full skill is explicit-only.
- The Stop guard validates transcript paths, keeps mode-0600 state and never
  continues or blocks a session. On escalation it requests one bounded,
  reference-only warm handoff with the next oracle and test checklist.
- The Stop guard also reads the outcome: the exit status of the last
  test/lint/typecheck command (Codex `exec_command`, Claude `Bash`). A red last
  run warns once — "not done, saving unproven" — and clears when a later run is
  green. It stores call ids only, never commands or output.
- Hooks never decide approval, sandbox or permissions.
- Codex only runs hooks it has persisted trust for, keyed by event position.
  The doctor reports that trust; re-approve in Codex after another tool
  reorders `~/.codex/hooks.json`.

Verify the active surface, not only copied files:

```bash
agent-token-saver doctor --profile teams --json
```
