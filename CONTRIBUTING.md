# Contributing

Improvements need evidence, not a larger tool list.

1. Start from an issue or a small benchmark question.
2. Preserve the accepted result in both benchmark arms.
3. Record raw tokens or the documented UTF-8-bytes/4 proxy, plus latency.
4. Keep optional tools optional and hooks fail-open.
5. Run:

```bash
uv run pytest
uv run ruff check scripts/install_agent_token_saver.py scripts/stack_doctor.py \
  scripts/news_projection.py scripts/token_stack_matrix_benchmark.py \
  tests/test_installer.py tests/test_stack_doctor.py tests/test_news_projection.py
bash -n install-universal.sh integration/hooks/rtk-rewrite.sh
```

A new dependency needs a reason, maintenance check and measured win over the
stdlib/CLI path. Never commit provider keys, private paths or full conversation
exports.
