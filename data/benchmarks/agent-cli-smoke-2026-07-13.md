# Agent CLI compatibility smoke — 2026-07-13

Prompt in every model arm:

```text
Use the installed agent-token-saver skill. Do not call tools. Reply exactly ATS_SMOKE_OK and nothing else.
```

| Agent | Version | Integration exercised | Result | Usage |
|---|---:|---|:---:|---|
| Codex CLI | 0.144.2 | installed skill + live JSON hooks | PASS | 16,747 input; 8,960 cached input; 101 output; 91 reasoning output |
| Claude Code | 2.1.207 | installed skill + `UserPromptSubmit`; existing native RTK hook preserved | PASS | 2 input; 41,757 cache creation; 21,242 cache read; 14 output |
| Hermes Agent | 0.18.2 | explicit `--skills agent-token-saver` | PASS | 12,208 input; 26 output; 16 reasoning; 12,234 total |
| GG Coder | 5.15.1 | native skill discovery + core JSON mode | PASS | 10,603 input; 8 output |

Commands:

```bash
codex exec --json -C . '<prompt>'
claude -p --output-format json '<prompt>'
hermes --skills agent-token-saver --usage-file /tmp/ats-hermes.json --oneshot '<prompt>'
ggcoder --json --provider openai --model gpt-5.5 --max-turns 1 '<prompt>'
```

The GG Coder package's core JSON entrypoint was used to bypass a machine-local
wrapper extension that swallowed stdout; native `discoverSkills()` independently
found the global `agent-token-saver` skill.

## Interpretation

This proves installation and agent compatibility. It does not prove the
2,768-token optimized workload fits inside a 2,768-token total request.

Each host adds its own system prompt, rules, tools, plugins and cache state. The
large numbers above are therefore evidence for the project's routing rule:
remove cold schemas and catalogs before trying to shorten good answers.

Claude's reported dollar estimate for this one configured smoke was $0.2571306.
Codex/Hermes used subscription-backed transports; marginal invoice cost was not
reported. Subscription price does not convert into a reliable per-token saving,
so this project reports tokens/quota and workload indices separately from money.
