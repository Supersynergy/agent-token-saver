# v3.0.1 — neutral-host proof and full-context ledger

This patch closes the largest credibility gap in v3.0.0.

- Fresh-HOME universal install now runs on a neutral GitHub-hosted Ubuntu runner.
- `doctor` distinguishes a usable portable core from a fully populated optional profile.
- `agent-token-ledger` reconciles provider usage with visible context layers.
- Hidden host overhead is reported as unattributed input, never counted as a saving.
- README labels 146.1x correctly as a dated accepted-payload benchmark.
- Clean Codex full-context control is published even though it is negative:
  +0.68% input on trivial work; the unverified shell arm is rejected.
- Claude uses RTK's native hook. Codex uses skill/CLI guidance until
  `unified_exec` hook coverage is complete.

Verification:

```bash
bash scripts/neutral_install_smoke.sh
bash scripts/remote_bootstrap_smoke.sh
uv run pytest
agent-token-saver doctor --profile lean --json
agent-token-ledger --help
```
