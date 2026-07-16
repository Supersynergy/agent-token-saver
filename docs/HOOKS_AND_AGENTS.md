# Agent integration matrix

Verified locally on 2026-07-13 with Codex CLI 0.144.2, Claude Code 2.1.207,
Hermes Agent 0.18.2 and GG Coder 5.15.1.

| Agent | Stable integration | What the installer does |
|---|---|---|
| Codex CLI | zero-hot prompt gate + Stop guard + CLI | hidden canonical skill; no visible catalog entry; removes obsolete repo RTK rewrite hooks |
| Claude Code | native RTK + prompt gate + Stop guard | `rtk hook claude` when present; hidden canonical skill activates only on demand |
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
support remains host-native through `rtk init --agent hermes --global`.

Hermes documents direct GitHub/URL skill installation, prompt-cache-friendly
skill invocation and the Agent Skills layout at
https://hermes-agent.nousresearch.com/docs/user-guide/features/skills.

Codex support is verified against the installed CLI and the official hook
contract at https://learn.chatgpt.com/docs/hooks. Current Codex `PreToolUse`
coverage does not intercept every newer `unified_exec` shell path, so this
release uses `UserPromptSubmit` plus skill/CLI guidance for RTK instead of
claiming transparent rewrite parity. GG Coder support is verified against its
installed skill discovery paths. The release does not claim a GG hook API that
its public CLI does not expose.

## Hook contract

- Hooks receive JSON on stdin and return either valid JSON or no output.
- Claude shell rewrites use RTK's own `rtk hook claude`; missing RTK means no rewrite.
- Codex shell compression is agent-guided until its unified shell hook coverage is complete.
- Automatic fuzzy routing is strict and limited to one primary skill; ambiguity returns no skill.
- Explicit `$SkillName` routing wins over context triggers.
- The token-saver route is pinned to the installed canonical skill, not a stale router copy.
- Automatic token tasks receive only the compact projection policy; the full canonical skill is read only for explicit `$agent-token-saver` use.
- Routed files must stay inside an allowed skill root, match their frontmatter name, be owned by the current user and reject group/world-writable or escaping symlink paths.
- The Stop guard validates the transcript path, delegates accounting to the installed ledger, stores private mode-0600 state and emits warnings without auto-continuing or blocking STOP.
- Existing settings are loaded, merged, backed up and atomically replaced.
- Repeated installation deduplicates agent-token-saver commands.
- Approval, sandbox and permission decisions remain owned by the host agent.
