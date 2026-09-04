# OmniRoute as an llmadapter lane — audit and PRD

Date: 2026-09-03 · Status: accepted, implemented behind an opt-in flag
Subject: [OmniRoute](https://github.com/diegosouzapw/OmniRoute) v3.8.51, MIT,
an OpenAI-compatible gateway fronting 352 providers and 1200+ models.

## 1. Why it is attractive

OmniRoute solves a problem this repo already has. `llmadapter` hard-codes its
free lanes, and the lane table carries a running commentary of slugs that
disappeared upstream (`poolside/laguna-m.1:free` delisted, two more slugs gone
by 2026-08-22). A gateway that tracks provider catalogs, stacks free tiers and
fails over on quota exhaustion is exactly the maintenance we keep paying by
hand. It is also OpenAI-compatible, so the wire format we already speak works
unchanged.

## 2. Audit

### 2.1 The finding that decides the design

**OmniRoute listens on loopback but is not a local lane.** This repo's trust
model asks one question — `isLoopbackUrl()` — to decide whether a prompt leaves
the machine, and that question returns the wrong answer for a forwarding proxy:

```
llmadapter.ts:1127   return { remote: !isLoopbackUrl(OLLAMA_URL), paid: false };
llmadapter.ts:1367   const shielded = await shieldPrompt(lane, prompt, trust.remote);
```

`trust.remote` gates the DSGVO/PII shield. Modelling OmniRoute the way Ollama is
modelled — `kind: "ollama"`, `http://localhost:20128` — yields `remote: false`
and therefore **silently disables PII masking on prompts that are then forwarded
to third-party providers.** The assumption "loopback means the data stays here"
holds for Ollama, which runs the weights locally, and breaks for a gateway,
which is a hop rather than a destination.

This is the single highest-severity item in this document, and it is a failure
mode of *our* code, not of OmniRoute.

**Decision.** OmniRoute lanes are always `remote: true`, independent of URL. The
existing `kind: "openrouter"` branch already returns `remote: true`
unconditionally, so reusing it is both the smallest diff and the safe default.
No new trust branch is introduced that could later be reasoned about wrongly.

### 2.2 Their guardrails are fail-open; ours are fail-closed

OmniRoute's `SECURITY.md` states the guardrail model plainly: *"exceptions never
block traffic"*, and its prompt-injection guard is documented as *"not a
complete prompt-injection firewall"* with known false negatives. Our shield is
the opposite — `shieldPrompt` throws rather than send unmasked text when the
shield module is missing.

Two fail-open layers and one fail-closed layer do not compose into two lines of
defence; the weakest one sets the floor unless ours runs first.

**Decision.** OmniRoute's guardrails are treated as defence in depth only. Our
shield runs before the request leaves the process, exactly as for any other
remote lane. We never disable our masking because the gateway claims to mask.

### 2.3 Blast radius of a local gateway holding every key

OmniRoute stores provider credentials and, per its own documentation, falls back
to **plaintext passthrough when `STORAGE_ENCRYPTION_KEY` is unset**. It also
serves a management dashboard. A gateway is therefore a single process holding
every provider credential, reachable from anything that can talk to the port.

**Decision.** The integration never writes, reads or manages credentials. It
sends a request and reads a response. Key management, encryption and dashboard
exposure stay the operator's responsibility, and the doctor output says so.

### 2.4 Supply chain and trust surface

352 providers behind one endpoint means the model that answers is chosen by the
gateway, not by us. `auto` is convenient and it is also an unpinned dependency
on a third party's routing decision. Free tiers in particular carry unclear
data-retention terms that vary per provider.

**Decision.** Lanes are **opt-in** (`optIn: true`), so no selector — `free`,
`cheap`, `all` — ever pulls OmniRoute into a swarm implicitly. A caller must
name the lane. The default lane pins an explicit model rather than `auto`; the
`auto` lane exists but must be chosen deliberately.

### 2.5 Availability

OmniRoute is not installed on this machine (`localhost:20128` refused the
connection while writing this). An integration that assumes a running gateway
would fail with a transport error indistinguishable from a network fault.

**Decision.** Absence is reported as a named, actionable failure
(`omniroute_gateway_unreachable`), never as a generic error, and the lane is
skipped rather than retried.

## 3. PRD

### Goal

Let a caller route an llmadapter lane through a local OmniRoute gateway to reach
free-tier capacity we do not maintain by hand, **without weakening any existing
safety property.**

### Non-goals

- Managing OmniRoute credentials, installation or configuration.
- Making OmniRoute a default, or including it in any class selector.
- Replacing our PII shield with the gateway's.
- Claiming a token saving from OmniRoute's own compression features.

### Requirements

| # | Requirement | Oracle |
|---|---|---|
| R1 | An OmniRoute lane is `remote: true` even on loopback | test asserts `laneTrustV2(...).remote === true` for a `localhost` gateway URL |
| R2 | The PII shield runs for OmniRoute lanes | test asserts shield failure propagates rather than being skipped |
| R3 | No class selector returns an OmniRoute lane | test asserts `free`/`cheap`/`all` exclude it |
| R4 | A missing gateway is a named failure | test asserts the reason string, not a stack trace |
| R5 | The gateway URL must be http(s) and carry no credentials in the URL | test asserts rejection of `file:`, userinfo forms |
| R6 | Existing OpenRouter behaviour is unchanged | full suite stays green |

### Out of scope for this change

Cost accounting per provider (OmniRoute reports its own usage numbers, which we
have not verified against a provider bill — see `docs/FULL_CONTEXT_MEASUREMENT.md`
on why unverified provider numbers are not recorded as measurements).

## 4. Rollout

Opt-in, off by default, no installer changes. `LLMADAPTER_OMNIROUTE_URL`
selects the gateway; without it the lanes stay listed but unusable, which is the
honest state on a machine where OmniRoute is not installed.
