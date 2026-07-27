# Swarm control-plane context benchmark

As of: `2026-07-27T12:12:08.994202+00:00`

No provider call. Tokens are UTF-8 bytes / 4 visible-input proxies.

| Worker task | Selected compact route | Visible input tokens |
|---|---|---:|
| source | local source | 243 |
| graph | impact graph | 238 |
| fresh | fresh external fact | 239 |

| Three-worker packet | Visible input tokens |
|---|---:|
| Naive: full model registry + contract per worker | 3588 |
| Routed: contract + one task-specific tool hint | 720 |
| Avoided projection | 2868 (79.9%) |

Controller dry-run acceptance passed: model registry non-empty; three routes
present; lane plan present. Raw registry and plan text are intentionally not
published.

This is a projection-capacity comparison, not a provider-cost or quality claim.
