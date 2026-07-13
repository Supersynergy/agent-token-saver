# Output-filter benchmark

Identical fixtures, isolated HOME, UTF-8 bytes / 4 token proxy.
Acceptance requires every named signal and the original exit code.

| Fixture | Stack | Tokens | Saved | ms | Signal | Exit | Accepted |
|---|---|---:|---:|---:|---:|---:|:--:|
| pytest-failures | raw | 1,549 | 0.00% | 0 | 6/6 | 1/1 | yes |
| pytest-failures | ppgranger/token-saver | 382 | 75.34% | 69 | 6/6 | 1/1 | yes |
| pytest-failures | RTK | 185 | 88.06% | 23 | 6/6 | 1/1 | yes |
| git-diff | raw | 3,324 | 0.00% | 0 | 7/7 | 0/0 | yes |
| git-diff | ppgranger/token-saver | 3,046 | 8.36% | 70 | 7/7 | 0/0 | yes |
| git-diff | RTK | 1,695 | 49.01% | 4 | 5/7 | 0/0 | no |
| kubectl-pods | raw | 1,393 | 0.00% | 0 | 4/4 | 0/0 | yes |
| kubectl-pods | ppgranger/token-saver | 79 | 94.33% | 71 | 4/4 | 0/0 | yes |
| kubectl-pods | RTK | 1,411 | -1.29% | 24 | 4/4 | 0/0 | yes |
| npm-install | raw | 798 | 0.00% | 0 | 5/5 | 0/0 | yes |
| npm-install | ppgranger/token-saver | 4 | 99.50% | 71 | 0/5 | 0/0 | no |
| npm-install | RTK | 789 | 1.13% | 22 | 5/5 | 0/0 | yes |
| terraform-plan | raw | 3,268 | 0.00% | 0 | 4/4 | 0/0 | yes |
| terraform-plan | ppgranger/token-saver | 3,039 | 7.01% | 69 | 4/4 | 0/0 | yes |
| terraform-plan | RTK unsupported/raw | 3,268 | 0.00% | 0 | 4/4 | 0/0 | yes |

## Decision rule

A smaller rejected output does not win. Adopt into a default only when it beats the current accepted stack on representative workloads without adding a second always-on hook.

## Rejected outputs

- **git-diff / RTK**: missing tests/test_auth.py, config/settings.yaml; exit 0 expected 0.
- **npm-install / ppgranger/token-saver**: missing inflight@1.0.6, eslint@8.57.0, 847 packages, 3 moderate severity vulnerabilities, npm audit fix; exit 0 expected 0.
