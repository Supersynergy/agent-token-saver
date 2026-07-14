# Released CLI selection — 2026-07-14

Scope: installed public CLIs only. No private host tools, web-fetch runtime or
new package installation. These are task-routing probes, not provider-billing
claims.

## Results

| Need | Probe and observed result | Default decision |
|---|---|---|
| Exact local symbol | `rg -n "def inspect_tool" scripts/stack_doctor.py` returned the one exact line. | **rg**. Lowest-friction exact search. |
| Known JSON fields | `jq -c '{profiles, tool_names:(.tools \| keys)}' stack/catalog.json` returned one compact object. | **jq**. Deterministic projection before a model. |
| Structural code neighbourhood | `tilth inspect_tool --scope . --budget 400 --json` returned two relationships and an estimated 171-token outline. | **Tilth** after exact search misses. |
| Syntax-aware local pattern | `ast-grep run --lang python --pattern 'subprocess.run($$$)' scripts/stack_doctor.py` returned the complete call range. | **ast-grep** (full binary name) for a concrete AST pattern. |
| Security/static pattern | Semgrep found the same `subprocess.run(...)` call; `--json` projected through jq became one compact finding. | **Semgrep + jq** only for a stated security/quality rule. |
| Noisy test output | Plain pytest printed the session header, environment and progress; `rtk pytest tests/test_stack_doctor.py -q` returned `Pytest: 6 passed` plus a raw-log pointer. | **RTK** for noisy builds/tests/logs, not for tiny output. |
| Public GitHub metadata | `gh api repos/rtk-ai/rtk/releases/latest --jq '.tag_name, .published_at, (.assets \| length)'` returned `v0.43.0`, `2026-06-28T08:55:20Z`, `10`. | **gh** with explicit fields for GitHub-only facts. |

## Rejected defaults

- `sg` is not safe as a portable alias on this host: `sg run --lang ...` was
  delegated to a different wrapper and failed with an `rg` flag error. Invoke
  the released `ast-grep` binary by its full name.
- Comby produced no Python match for the simple function template used here,
  even with an explicit Python matcher. Keep it opt-in for a tested rewrite
  template, never the default structural reader.
- Semgrep's unprojected JSON is much larger than its one finding. It belongs in
  a security lane with a specific rule and a JSON projection, not every coding
  prompt.
- Aider, OpenCode, Codex and Claude Code are agent runtimes, not pre-context
  reducers. They do not replace `rg`/`jq`/RTK/Tilth in the saver ladder.

## Resulting public ladder

```text
exact local fact       -> rg / jq
noisy command output   -> rtk
large skill catalog    -> optional si (0/1 route)
structural code        -> tilth; ast-grep for one known AST rule
security-specific rule -> semgrep output projected by jq
GitHub-only fact       -> gh with narrow fields
agent team             -> no new runtime; capsule + 0/1 skill + <=3 workers
```

`agent-token-saver` installs and measures the ladder. The separately published
`agent-token-saver-skill-router` is optional and is never downloaded by the
main installer.
