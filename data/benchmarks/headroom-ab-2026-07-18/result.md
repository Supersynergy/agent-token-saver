# Headroom proxy A/B — 2026-07-18 02:41:29 CEST

Fresh HOME per arm; same model, fixture and oracle. Both arms disable hooks and
rules; the only variable is routing through the local Headroom proxy. The proxy
arm ran first, so provider prompt-cache reuse favors the direct arm.

- Task: `large-git-diff`, expected `ATS_DIFF_OK`
- Model: `gpt-5.6-sol`, codex `codex-cli 0.144.3`, headroom `0.31.0`

| Arm | Input | Cached | Uncached | Output | Total | Elapsed | Accepted |
|---|---:|---:|---:|---:|---:|---:|:--:|
| headroom-off | 45,058 | 22,016 | 23,042 | 148 | 45,206 | 16,603 ms | yes |
| headroom-on | 20,244 | 8,960 | 11,284 | 354 | 20,598 | 14,699 ms | yes |

## Delta (on vs off)

- Input saved: **55.07%** (-24,814)
- Uncached input saved: **51.03%** (-11,758)
- Total saved: **54.44%** (-24,608)
- Oracle accepted in both arms: **yes**

## Proxy-side evidence (supporting only)

- Proxy requests during on-arm: **3**
- Proxy-claimed tokens saved during on-arm: **0**

A failed oracle invalidates the saving claim. One run per arm is fresh
evidence, not a statistical confidence interval; repeat ABBA before changing
defaults.
