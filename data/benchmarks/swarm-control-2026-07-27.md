# Swarm control-plane context benchmark

As of: `2026-07-27T18:28:43.181907+00:00`

No provider call. Tokens are UTF-8 bytes / 4 visible-input proxies.

Controller dry run exposed `11` model lanes.

| Worker task | Selected route | Task capsule | Full hook contract | Compact hook delta |
|---|---|---:|---:|---:|
| source | local source | 70 | 243 | 109 |
| graph | impact graph | 69 | 238 | 104 |
| fresh | fresh external fact | 69 | 243 | 109 |

| Three-worker packet | Visible input tokens |
|---|---:|
| Naive: registry + same capsules + full hook | 3800 |
| Routed: same capsules + full hook | 932 |
| Routed: same capsules + compact hook | 530 |
| Routed full reduction vs naive | 75.5% |
| Routed compact reduction vs naive | 86.1% |
| Additional capsule-dedup saving | 402 (43.1% of complete routed packet) |

This is a projection-capacity comparison, not a provider-cost or quality claim.
