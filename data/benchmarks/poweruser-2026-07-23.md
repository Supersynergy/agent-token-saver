# ATS Poweruser Benchmark (codex + kimi + hermes_luna, 10 real cases)

## Per-case token savings

| Case | Question | Baseline tok | ATS-recon tok | Saved | Saved % | Baseline wall | ATS wall |
|---|---|---|---|---|---|---|---|
| 01_usage_parsing | Where is usage parsing handled in agent- | 1586 | 220 | 1366 | 86.1% | 48.398s | 24.554s |
| 02_superweb_readme | What does the superweb README say about  | 94 | 74 | 20 | 21.3% | 36.079s | 57.95s |
| 03_chartlab_quantagent | How does chartlab's QuantAgent Durable O | 87 | 82 | 5 | 5.7% | 46.537s | 20.868s |
| 04_synapse_fts5 | Where is FTS5 search implemented in syna | 122 | 84 | 38 | 31.1% | 74.301s | 31.403s |
| 05_codex_pro_providers | Which LLM providers does codex-pro suppo | 87 | 88 | -1 | -1.1% | 30.11s | 13.433s |
| 06_token_cfo_pricing | What are the token-cfo pricing tiers? | 1369 | 75 | 1294 | 94.5% | 23.025s | 19.862s |
| 07_psi_schlafzimmer | What is the PSI Sanctuary product ladder | 2963 | 98 | 2865 | 96.7% | 20.929s | 74.066s |
| 08_ats_hooks | Which hooks does agent-token-saver insta | 101 | 265 | -164 | -162.4% | 28.009s | 25.35s |
| 09_example_scrape | What is the main heading of example.com? | 209 | 112 | 97 | 46.4% | 16.409s | 14.036s |
| 10_ats_recon_router | How does ats-recon auto-route between gm | 121 | 245 | -124 | -102.5% | 82.021s | 26.835s |

## Per-agent totals

| Agent | Cases | Baseline tok | ATS-recon tok | Saved | Saved % |
|---|---|---|---|---|---|
| codex | 10 | 6579 | 1269 | 5310 | 80.7% |
| kimi | 10 | 6604 | 1015 | 5589 | 84.6% |
| hermes_luna | 10 | 7049 | 1758 | 5291 | 75.1% |

## Per-agent/case detail

| Agent | Case | Path | wall_s | tool_tok | agent_tok | total |
|---|---|---|---|---|---|---|
| codex | 01_usage_parsing | baseline | 49.46 | 1464 | 106 | 1570 |
| codex | 01_usage_parsing | ats_recon | 12.303 | 133 | 77 | 210 |
| codex | 02_superweb_readme | baseline | 70.283 | 31 | 56 | 87 |
| codex | 02_superweb_readme | ats_recon | 61.096 | 0 | 85 | 85 |
| codex | 03_chartlab_quantagent | baseline | 109.318 | 0 | 124 | 124 |
| codex | 03_chartlab_quantagent | ats_recon | 41.548 | 0 | 109 | 109 |
| codex | 04_synapse_fts5 | baseline | 130.794 | 0 | 132 | 132 |
| codex | 04_synapse_fts5 | ats_recon | 80.297 | 0 | 118 | 118 |
| codex | 05_codex_pro_providers | baseline | 58.581 | 0 | 57 | 57 |
| codex | 05_codex_pro_providers | ats_recon | 21.52 | 0 | 64 | 64 |
| codex | 06_token_cfo_pricing | baseline | 28.894 | 1251 | 69 | 1320 |
| codex | 06_token_cfo_pricing | ats_recon | 29.363 | 0 | 45 | 45 |
| codex | 07_psi_schlafzimmer | baseline | 31.991 | 2832 | 146 | 2978 |
| codex | 07_psi_schlafzimmer | ats_recon | 163.702 | 0 | 110 | 110 |
| codex | 08_ats_hooks | baseline | 17.564 | 14 | 43 | 57 |
| codex | 08_ats_hooks | ats_recon | 22.607 | 168 | 71 | 239 |
| codex | 09_example_scrape | baseline | 14.245 | 139 | 27 | 166 |
| codex | 09_example_scrape | ats_recon | 12.161 | 42 | 27 | 69 |
| codex | 10_ats_recon_router | baseline | 133.485 | 0 | 88 | 88 |
| codex | 10_ats_recon_router | ats_recon | 50.896 | 135 | 85 | 220 |
| kimi | 01_usage_parsing | baseline | 75.369 | 1464 | 159 | 1623 |
| kimi | 01_usage_parsing | ats_recon | 38.35 | 133 | 120 | 253 |
| kimi | 02_superweb_readme | baseline | 11.858 | 31 | 0 | 31 |
| kimi | 02_superweb_readme | ats_recon | 103.454 | 0 | 4 | 4 |
| kimi | 03_chartlab_quantagent | baseline | 23.553 | 0 | 4 | 4 |
| kimi | 03_chartlab_quantagent | ats_recon | 8.982 | 0 | 4 | 4 |
| kimi | 04_synapse_fts5 | baseline | 67.331 | 0 | 100 | 100 |
| kimi | 04_synapse_fts5 | ats_recon | 0.282 | 0 | 0 | 0 |
| kimi | 05_codex_pro_providers | baseline | 24.432 | 0 | 71 | 71 |
| kimi | 05_codex_pro_providers | ats_recon | 10.504 | 0 | 67 | 67 |
| kimi | 06_token_cfo_pricing | baseline | 32.646 | 1251 | 150 | 1401 |
| kimi | 06_token_cfo_pricing | ats_recon | 12.342 | 0 | 47 | 47 |
| kimi | 07_psi_schlafzimmer | baseline | 22.488 | 2832 | 114 | 2946 |
| kimi | 07_psi_schlafzimmer | ats_recon | 47.688 | 0 | 51 | 51 |
| kimi | 08_ats_hooks | baseline | 53.673 | 14 | 85 | 99 |
| kimi | 08_ats_hooks | ats_recon | 41.999 | 168 | 85 | 253 |
| kimi | 09_example_scrape | baseline | 15.317 | 139 | 49 | 188 |
| kimi | 09_example_scrape | ats_recon | 15.091 | 42 | 49 | 91 |
| kimi | 10_ats_recon_router | baseline | 105.923 | 0 | 141 | 141 |
| kimi | 10_ats_recon_router | ats_recon | 13.853 | 135 | 110 | 245 |
| hermes_luna | 01_usage_parsing | baseline | 20.366 | 1464 | 103 | 1567 |
| hermes_luna | 01_usage_parsing | ats_recon | 23.009 | 133 | 65 | 198 |
| hermes_luna | 02_superweb_readme | baseline | 26.096 | 31 | 135 | 166 |
| hermes_luna | 02_superweb_readme | ats_recon | 9.301 | 0 | 135 | 135 |
| hermes_luna | 03_chartlab_quantagent | baseline | 6.741 | 0 | 135 | 135 |
| hermes_luna | 03_chartlab_quantagent | ats_recon | 12.074 | 0 | 135 | 135 |
| hermes_luna | 04_synapse_fts5 | baseline | 24.778 | 0 | 135 | 135 |
| hermes_luna | 04_synapse_fts5 | ats_recon | 13.631 | 0 | 135 | 135 |
| hermes_luna | 05_codex_pro_providers | baseline | 7.318 | 0 | 135 | 135 |
| hermes_luna | 05_codex_pro_providers | ats_recon | 8.274 | 0 | 135 | 135 |
| hermes_luna | 06_token_cfo_pricing | baseline | 7.536 | 1251 | 135 | 1386 |
| hermes_luna | 06_token_cfo_pricing | ats_recon | 17.881 | 0 | 135 | 135 |
| hermes_luna | 07_psi_schlafzimmer | baseline | 8.309 | 2832 | 135 | 2967 |
| hermes_luna | 07_psi_schlafzimmer | ats_recon | 10.808 | 0 | 135 | 135 |
| hermes_luna | 08_ats_hooks | baseline | 12.79 | 14 | 135 | 149 |
| hermes_luna | 08_ats_hooks | ats_recon | 11.443 | 168 | 135 | 303 |
| hermes_luna | 09_example_scrape | baseline | 19.665 | 139 | 135 | 274 |
| hermes_luna | 09_example_scrape | ats_recon | 14.856 | 42 | 135 | 177 |
| hermes_luna | 10_ats_recon_router | baseline | 6.654 | 0 | 135 | 135 |
| hermes_luna | 10_ats_recon_router | ats_recon | 15.755 | 135 | 135 | 270 |