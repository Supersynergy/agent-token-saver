# Subagent Capsule Template

> **Bounded context for `devin-goal-spawn`.** Replace ALL bracketed fields.
> Target: 300–700 tokens. Never include parent transcript.

## Goal

- **ID:** `<slug>` (matches `~/.synapse/goals/<slug>.json`)
- **Oracle:** `<one-line shell command returning 0 on success>`
- **Budget:** `<N> tokens`, deadline `<T>`
- **Your slice:** `<one independent closed objective>`

## Inputs

- **Files to read:** `<path1>, <path2>`
- **Skills allowed:** `<none | skill-name>` (at most one)
- **Prior decisions:** `synx hybrid "<topic> <repo> decisions" 8` (run once)

## Constraints

- No parent transcript. You see only this capsule + the goal JSON.
- No MCP server. CLI / file / JSON seams only.
- Fail-open: missing tools → proceed without them.
- Max 3 attempts. Stop when oracle passes OR budget exhausted.

## Output

Return a ≤500-token summary with:

1. **Oracle result:** PASS / FAIL (run `devin-goal-check <slug>`)
2. **Bottleneck:** root cause if FAIL, what fixed it if PASS
3. **Tokens spent:** approximate
4. **Files changed:** list with line counts
5. **Next step:** if FAIL, what the next subagent should do

## Close

```bash
devin-goal-check <slug>
devin-goal-close <slug> --summary "<one-line outcome>"
```

## Example (filled)

```markdown
# Subagent Capsule: extract compile errors

## Goal
- ID: fix-cargo-test
- Oracle: cargo test --workspace --no-run 2>&1 | tail -1 | grep -q 'Finished'
- Budget: 50000 tokens, deadline 1h
- Your slice: extract all compile errors with file:line refs

## Inputs
- Files to read: Cargo.toml, src/**/*.rs
- Skills allowed: none
- Prior decisions: synx hybrid "devin superweb cargo-test errors" 8

## Output
1. Oracle result: FAIL — 3 compile errors in src/parser.rs
2. Bottleneck: missing `use std::collections::HashMap` at src/parser.rs:14
3. Tokens spent: ~3200
4. Files changed: src/parser.rs (+1 line)
5. Next step: run cargo test --workspace to verify fix
```
