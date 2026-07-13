# v3.0.0 — agent-token-saver

The former Claude-focused toolkit is now an agent-neutral, measured token
routing stack.

## What changed

- One fail-safe installer for Codex CLI, Claude Code, Hermes Agent, GG Coder
  and repo-local agents.
- Native hooks only where the host exposes them; portable skills everywhere
  else.
- Four measured profiles instead of an always-on pile of tools.
- Reproducible matrix: 380,871 raw workload tokens versus 2,768 for the
  CLI-selective accepted path in the dated local benchmark.
- Public memory seam; unreleased Synapse is not required or bundled.
- Security policy, issue templates, CI and benchmark contribution contract.

## Upgrade

```bash
git pull
./install-universal.sh --profile lean --agent auto --dry-run
./install-universal.sh --profile lean --agent auto
agent-token-saver doctor --profile lean
```

GitHub redirects the old repository URL. Existing `cts` entrypoints remain for
compatibility.
