# Codex explicit RTK end-to-end probe — 2026-07-13

This probe measures the reliable Codex strategy: ask the agent to execute RTK
explicitly. It does not rely on incomplete `PreToolUse` interception.

## Accepted runs

Both arms executed exactly one command, exited `0`, found the PID header and
returned exactly `YES`.

| Arm | Executed command | Input | Cached subset | Uncached input | Output |
|---|---|---:|---:|---:|---:|
| Raw | `/bin/zsh -lc 'ps aux'` | 25,210 | 19,968 | 5,242 | 78 |
| Explicit RTK | `/bin/zsh -lc 'rtk ps aux'` | 23,996 | 19,968 | 4,028 | 79 |

Result:

- **1,214 fewer full provider input tokens**.
- **4.82% lower complete input**.
- **23.16% lower uncached input**.

The reduction is smaller than the local raw-output compression ratio because
system instructions, tool schemas and cached input remain fixed.

One earlier warmup is retained as rejected evidence: Codex emitted no command
event and answered incorrectly. It consumed 22,570 input and 92 output tokens.
Failures and retries belong in experiment totals; they cannot be used as a
savings arm.

This result proves one explicit RTK workload only. It does not prove transparent
Codex hook rewriting or the same percentage on other commands.
