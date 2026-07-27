# Agent integration

| Host | Managed surface | Guarantee |
|---|---|---|
| Codex CLI | `UserPromptSubmit` prompt gate; `Stop` session guard | No transparent shell rewrite claim |
| Claude Code | RTK for Bash when present; prompt gate; Stop guard; teams worker capsule | Worker hook only for `teams` |
| Hermes | Agent Skill | No YAML hook mutation |
| GG Coder | Markdown skill | No assumed hook API |
| Other agents | repo-local `SKILL.md` plus CLI/JSON | Explicit invocation |

## Contract

- Hooks read JSON stdin and emit valid JSON or nothing.
- Installation merges and backs up existing Codex/Claude JSON; repeated runs
  deduplicate managed commands.
- Prompt routing is strict: zero or one skill; explicit `$SkillName` wins.
- The normal route emits a compact policy. The full skill is explicit-only.
- The Stop guard validates transcript paths, keeps mode-0600 state and never
  continues or blocks a session.
- Hooks never decide approval, sandbox or permissions.

Verify the active surface, not only copied files:

```bash
agent-token-saver doctor --profile teams --json
```
