# Contributing

Improvements need evidence, not a larger tool list.

1. Start from an issue or a small benchmark question.
2. Preserve the accepted result in both benchmark arms.
3. Record raw tokens or the documented UTF-8-bytes/4 proxy, plus latency.
4. Keep optional tools optional and hooks fail-open.
5. Run:

```bash
uv run pytest
uv run ruff check scripts integration tests
bash -n install-universal.sh integration/cli/codex-heavy-context \
  scripts/neutral_install_smoke.sh scripts/remote_bootstrap_smoke.sh
bash scripts/neutral_install_smoke.sh
```

A new dependency needs a reason, maintenance check and measured win over the
stdlib/CLI path. Never commit provider keys, private paths or full conversation
exports.
