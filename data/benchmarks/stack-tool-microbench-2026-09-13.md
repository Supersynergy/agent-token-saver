# Stack Tool Micro-Benchmark — 2026-09-13

Token proxy: UTF-8 bytes / 4. `accepted` = oracle signal survived.
`kind=speed` tools change latency, not bytes — reported honestly.

| Case | Tool | Base tok | Opt tok | Saved | Base ms | Opt ms | OK |
|---|---|---:|---:|---:|---:|---:|:--:|
| rtk-git-log | rtk | 10,636 | 52 | 99.5% | 153 | 6 | yes |
| rtk-test-fail | rtk | 616 | 52 | 91.6% | 94 | 107 | yes |
| rtk-find | rtk | 16,477 | 74 | 99.5% | 24 | 6 | yes |
| rtk-grep | rtk | 15,745 | 4,929 | 68.7% | 19 | 6 | yes |
| rtk-ls | rtk | 61,005 | 866 | 98.6% | 136 | 41 | yes |
| rtk-err-build | rtk | 5,184 | 30 | 99.4% | 3028 | 29 | yes |
| tilth-grok | tilth | 7,142 | 476 | 93.3% | 21 | 31 | yes |
| tilth-read | tilth | 7,100 | 745 | 89.5% | 0 | 4 | yes |
| codegraph-explore | codegraph | 55,148 | 4,547 | 91.8% | 26 | 259 | yes |
| graphify-explain | graphify | 7,438 | 76 | 99.0% | 78 | 690 | yes |
| context-mode-search | context-mode | 300,110 | 138 | 100.0% | 0 | 105 | yes |
| synapse-recall | synapse | 639 | 351 | 45.1% | 238 | 6343 | yes |
| beads-ready | beads | 972 | 823 | 15.3% | 127 | 106 | yes |
| ats-verify-green | ats-verify | 2,576 | 66 | 97.4% | 112 | 62 | yes |
| jq-keys | jq | 48,487 | 582 | 98.8% | 13 | 16 | yes |
| qsv-stats | qsv | 220,825 | 174 | 99.9% | 13 | 89 | yes |
| ats-recall | ats-recall | 2,830 | 146 | 94.8% | 4437 | 4545 | yes |
| ats-cache-line | ats-cache | 31 | 35 | -12.9% | 13 | 54 | yes |
| ats-url-cache | ats-url-cache | 0 | 12 | 0.0% | 0 | 61 | yes |
| llmadapter-lanes | llmadapter | 0 | 987 | 0.0% | 0 | 27 | yes |
| fd-vs-find | fd | 11 | 11 | 0.0% | 17 | 21 | yes |
| rg-vs-grep | rg | 2,376 | 1,587 | 33.2% | 59 | 18 | yes |
| agent-token-ledger | ledger | 0 | 0 | 0.0% | 0 | 0 | yes |

## Details

- **rtk-git-log**: git log --stat -30 through rtk pipe -f git-log
- **rtk-test-fail**: 61-test fixture, one failing assert; rtk test keeps failure + exit
- **rtk-find**: 4000-entry fd listing via find filter
- **rtk-grep**: rg 'def' over scripts+integration via grep filter
- **rtk-ls**: ls /opt/homebrew/bin vs rtk ls (pre-route equivalent)
- **rtk-err-build**: 800-line failing build via rtk err; error line + exit preserved
- **tilth-grok**: rg+cat whole file vs tilth grok build_matrix_row (def+callers+tests in one call)
- **tilth-read**: full file vs 800-token structural read
- **codegraph-explore**: rg+cat vs codegraph explore apps/agent/quant-agent.ts (def+source+paths in one shot)
- **graphify-explain**: graphify explain median_ms() vs rg+cat-source baseline
- **context-mode-search**: 20k-line log: cat vs index+search (log indexes as one section; search returns matching chunk, oracle = an E-id + code=500 visible)
- **synapse-recall**: unbounded synx dump vs synxp top-8 recall
- **beads-ready**: bd list (300 lines, all states) vs bd ready (unblocked projection)
- **ats-verify-green**: 400-line green check vs ats-verify verdict (raw log stays on disk)
- **jq-keys**: cat vs jq 'keys[]' on .claude.json
- **qsv-stats**: 50k-row CSV: cat vs qsv count+stats head
- **ats-recall**: unbounded hybrid dump vs ats-recall deduped corpus+brain blocks
- **ats-cache-line**: raw usage.json vs ats-cache one-line weighted summary
- **ats-url-cache**: SQLite URL cache — saves a whole re-fetch per repeat hit; stats only here (no live fetch in bench)
- **llmadapter-lanes**: lane inventory — routing surface, not a saver itself
- **fd-vs-find**: same result set; fd wins on latency/gitignore, not output size
- **rg-vs-grep**: same match lines; rg wins on speed/gitignore, not output size
- **agent-token-ledger**: Accounting tool — reconciles usage, saves nothing itself
