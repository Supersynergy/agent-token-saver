# Spec: incremental Stop-session guard

Status: implementation-ready. Scope: `lean` and `teams` Stop guard only. No product code in this document.

## Evidence and proof boundary

Static inspection on 2026-07-29 establishes that `integration/hooks/token-session-guard.py:57` starts `agent-token-ledger` for the complete transcript on every Stop event, with a five-second subprocess timeout. `scripts/full_context_ledger.py:68` streams JSONL, but `inspect_usage_file()` still replays every record to recover cumulative usage and metadata. The hook writes only action, observed guard fields, reasons/warnings, a path hash, and transcript byte length to two private state files (`token-session-guard.py:167-180`). Existing tests cover private state, one-shot escalation, unsafe files, and symlink escape (`tests/test_session_guard_hook.py:59-130`).

No latency, RSS, swap, or I/O number was measured in this session. The current subprocess is the baseline; this spec makes no saving claim until the prescribed paired run passes.

## Goal and non-goals

Goal: make a safe Stop event whose transcript has only appended bytes take an incremental, bounded local path while preserving the exact current guard decision and fail-open Stop ownership. The incremental result must be semantically identical to a complete ledger replay of the same stable transcript.

Non-goals:

- Do not change thresholds, host approval/sandbox/Stop ownership, warning prose, provider accounting, team accounting, or public CLI output.
- Do not make a hidden provider-billing claim. Provider-reported cumulative totals remain the token oracle; local bytes/4 remains only a visible-context estimate.
- Do not cache transcript text, tool payloads, PII, raw records, or child transcripts in guard state.
- Do not add a daemon, watcher, database, dependency, background process, or cross-session global cache.

## Design contract

### Owned symbols and files

| Surface | Required change |
|---|---|
| `integration/hooks/token-session-guard.py` | Replace the direct-first `run_ledger(transcript, home)` call with an incremental attempt, then its existing complete-ledger fallback. Extend `record` with schema-v2 cursor/provenance fields only after a valid result. Keep `safe_file`, root checks, state permissions, `atomic_state`, and fail-open output behavior. |
| `scripts/full_context_ledger.py` | Extract a reusable record-to-metadata accumulator from `_update_source_metadata`; add a bounded JSONL suffix reader / incremental inspection API. Preserve `inspect_usage_file()`, CLI schema v3, and full-replay behavior. |
| `tests/test_session_guard_hook.py` | Add cursor, append, rotation/truncation, corruption, unsafe-file, and fallback tests. |
| `tests/test_full_context_ledger.py` | Add exact full-versus-incremental identity fixtures and accounting edge cases. |
| `docs/HOOKS_AND_AGENTS.md`, `CHANGELOG.md` | Document local-only state schema, fallback conditions, and proof result only after implementation. |

### State schema v2

Persist one 0600 JSON object per session key, atomically as today. It contains no transcript content, record text, tool output, absolute path, provider response, or value-derived identifiers.

```json
{
  "schema_version": 2,
  "transcript_fingerprint": "sha256(device,inode,path-hash)",
  "cursor": {"byte_offset": 1234, "prefix_sha256": "...", "tail_sha256": "..."},
  "accumulator": {"latest_codex_total": {"...numeric usage only...": 0}, "last_usage_candidate": {"...numeric usage only...": 0}, "metadata": {"records": 0, "token_count_events": 0, "compactions": 0, "tool_output_bytes": 0, "spawned_workers": 0, "shell_exec_calls": 0, "rtk_mentions": 0}},
  "guard": {"action": "continue", "observed": {}, "reasons": [], "warnings": []},
  "transcript_bytes": 1234,
  "timestamp_unix": 0
}
```

The stored `latest_codex_total` and `last_usage_candidate` must be the normalized integer fields already returned by `_normalize_usage()`, never raw usage JSON. `prefix_sha256` hashes a fixed first 4096 bytes and `tail_sha256` hashes up to the final 4096 bytes at the committed cursor. The implementation must use `os.stat()` identity fields plus these hashes; an offset alone is never trusted.

### Incremental algorithm

1. Validate the current transcript with the existing `safe_file()` and obtain one `fstat` snapshot. Load state only when it is a v2 dict, 0600, and its fingerprint, prefix hash, file size, and cursor offset are coherent.
2. If the file grew and the saved tail validates, open it once, seek to `cursor.byte_offset`, and parse only complete newline-delimited JSON values. Apply the same usage selection and `_update_source_metadata` semantics as a full replay. Do not accept a partially written last line: leave its bytes uncommitted and force full fallback on the next Stop if it persists or changes.
3. Rebuild `usage`, `team_accounting`, and `session_guard` through the existing canonical functions. This preserves the current precedence of Codex `total_token_usage` over the final generic candidate and the current incomplete-team checkpoint rule.
4. Re-stat the file before state commit. If size, device/inode, mode/owner, or committed-tail bytes changed, discard the incremental result and do one full replay. Never commit a cursor from an unstable file.
5. Commit v2 state only after a stable result. Compare action rank with the previous action exactly as current code does; emit only a higher-rank warning. A valid incremental result still writes `session-guard-latest.json`.
6. Full fallback is mandatory for absent/invalid/v1 state, rotation/replacement/truncation, malformed state, hash mismatch, non-JSONL input, partial trailing record, stat race, parser exception, accumulator invariant failure, or any result whose identity oracle fails. If fallback also fails, emit `{}` and exit 0 as today. On a successful fallback, replace stale state with v2.

Never parse a suffix beginning in the middle of a line, follow a symlink, read outside allowed roots, or use state to bypass transcript validation.

## Resource and security budgets

These are reject gates, not measured current values.

| Quantity | Incremental target | Reject / fallback |
|---|---:|---|
| Persisted state | <= 16 KiB/session | > 16 KiB or any raw record/text field |
| Incremental input | bytes after validated cursor only | cursor invalid, last line incomplete, or > 8 MiB appended since cursor: full replay |
| Hook heap growth | <= 16 MiB over idle fixture median | > 16 MiB, swap delta > 0, or memory-pressure regression |
| Extra durable writes | two existing atomic state replacements; no ledger artifact | any transcript copy, log, or state expansion beyond budget |
| Stop latency | lower median and no worse p99 than full baseline | p99 worse by > 10% or timeout/failure rate increases |

Keep 0700 directory / 0600 state mode and `fsync` + rename in `atomic_state`. Hash only local structural bytes. State is integrity metadata, not an accounting authority: the transcript and canonical ledger remain authority.

## Phased Terra slices

### Terra 1 — pure incremental inspector

In `full_context_ledger.py`, introduce a small accumulator type plus pure `inspect_usage_suffix(path, cursor, accumulator)` and test fixtures. Use no hook changes. Oracle: full `inspect_usage_file()` and suffix result yield byte-for-byte equal normalized usage plus equal metadata for valid fixtures.

### Terra 2 — guarded hook integration

Add v2 load/validate/commit functions in the Stop hook. Default to full replay on every uncertainty. Preserve schema-v1 read compatibility only as "fallback then rewrite v2"; do not migrate state in place. Oracle: existing hook tests unchanged plus the identity matrix below.

### Terra 3 — resource proof and documentation

Run the paired benchmark, capture raw JSON and resource samples under a new ignored test-output path, summarize only aggregate non-transcript measurements in docs, then update public docs/changelog. Ship only if all gates pass.

## Tests, fixtures, and identity oracle

Add synthetic JSONL fixtures only; no copied real session. Cover: cumulative Codex total followed by generic usage; Claude cache fields; compactions/tool outputs; spawned-worker accounting; no append; one append; multiple appends; append ending without newline; malformed suffix; truncate; replace with same size; changed prefix; changed committed tail; v1/malformed state; world-writable transcript; symlink escape; ledger executable failure; race between two stats; and state size/mode.

The identity oracle is strict equality of `provider_usage`, `team_accounting`, and `session_guard` (including ordered reasons/warnings and every `observed` field) between a fresh full replay and the incremental route over the same immutable fixture. It also requires the same stdout object and action-rank behavior over repeated Stop calls. The cursor path must be rejected if it cannot establish this equality; it must not silently approximate totals.

## Benchmark and release gate

Create `tests/bench_session_guard_incremental.py` with a synthetic, owner-private 100,000-record JSONL fixture plus a 100-record append. Execute sequentially, same Python, isolated `HOME`, fixed `ATS_LEDGER_PATH` and state directory:

```sh
/usr/bin/time -lp python3 tests/bench_session_guard_incremental.py --mode full --runs 15 --json test-output/guard-full.json
/usr/bin/time -lp python3 tests/bench_session_guard_incremental.py --mode incremental --runs 15 --json test-output/guard-incremental.json
memory_pressure -Q; sysctl vm.swapusage
```

Record cold first Stop, warm unchanged Stop, appended Stop median/p95, max RSS, swap delta, memory-pressure status, hook CPU time, transcript read bytes attributed by a test wrapper, state bytes, durable write count, and subprocess count. Do not use device-wide I/O as process proof. Before/after comparison is valid only with identical fixture, thresholds, Python, and host load window.

Reject if identity differs; any unsafe transcript is accepted; full fallback is skipped on ambiguity; state stores content; hook ceases to be fail-open; budget is exceeded; or the resource vector violates the table. Back out by removing the incremental invocation/state-v2 fields and retaining current `run_ledger`; v1 state files remain harmless private leftovers and may be deleted manually, never scanned broadly.

## Terra build capsule (<=700 tokens)

Implement only this order. First refactor `scripts/full_context_ledger.py` so full replay and a suffix reader feed one accumulator; preserve the public CLI and v3 ledger JSON. Add synthetic identity tests before touching the hook. Next add v2 private state in `integration/hooks/token-session-guard.py`: device/inode/path-hash plus 4 KiB prefix/tail hashes, a byte cursor, normalized numeric usage candidates, and current metadata counters. Validate transcript/state before every read; parse appended complete JSONL lines only; re-stat before commit. On any mismatch, malformed value, partial line, race, or invariant failure, call the existing full ledger path once; if it fails, emit `{}`/exit 0. Keep `atomic_state`, permissions, warning rank, and no-Stop-blocking behavior. Add fixtures for append, no append, corrupt/truncated/replaced files, unsafe modes/symlink, partial line, and full-vs-incremental exact equality. Then run the specified sequential 15-run synthetic benchmark and publish only aggregate latency/RSS/swap/I-O values. No dependencies, watcher, daemon, transcript cache, or raw content in state.
