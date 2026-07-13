# Agent integration matrix

Verified locally on 2026-07-13 with Codex CLI 0.144.2, Claude Code 2.1.207,
Hermes Agent 0.18.2 and GG Coder 5.15.1.

| Agent | Stable integration | What the installer does |
|---|---|---|
| Codex CLI | native JSON hooks + skill | merges `~/.codex/hooks.json`; installs one skill |
| Claude Code | native JSON hooks + skill | merges `~/.claude/settings.json`; installs one skill |
| Hermes Agent | Agent Skills standard | installs under `~/.hermes/skills/` |
| GG Coder | global Markdown skill | installs under `~/.gg/skills/` |
| Other agents | repo skill + CLI/JSON | installs `.agents/skills/`; call projections directly |

Claude Code documents command hooks and the `SessionStart`,
`UserPromptSubmit`, `PreToolUse`, `PostToolUse`, compaction and session events at
https://code.claude.com/docs/en/hooks.

Hermes also exposes shell hooks through the `hooks:` block in
`~/.hermes/config.yaml`, with `pre_tool_call` and `pre_llm_call` events, explicit
first-use consent and `hermes hooks doctor`. This release uses the skill path by
default because it is zero-config and does not mutate YAML; native Hermes hook
support can be added later with a separate Hermes wire-protocol adapter.

Hermes documents direct GitHub/URL skill installation, prompt-cache-friendly
skill invocation and the Agent Skills layout at
https://hermes-agent.nousresearch.com/docs/user-guide/features/skills.

Codex support is verified against the installed CLI help and live
`~/.codex/hooks.json` wiring. GG Coder support is verified against its installed
skill discovery paths. The release does not claim a GG hook API that its public
CLI does not expose.

## Hook contract

- Hooks receive JSON on stdin and return either valid JSON or no output.
- Failure, missing optional binary or unsupported command means no rewrite.
- Existing settings are loaded, merged, backed up and atomically replaced.
- Repeated installation deduplicates agent-token-saver commands.
- Approval, sandbox and permission decisions remain owned by the host agent.
