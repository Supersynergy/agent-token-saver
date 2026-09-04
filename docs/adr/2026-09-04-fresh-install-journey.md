# The fresh-install journey — analysis and plan

Date: 2026-09-04 · Status: accepted; fixes landed the same day
Method: a clean `HOME`, a PATH with no version manager, both installers run
the way the READMEs say. Nothing below is inferred from reading code; every
finding was observed on that run.

## 1. What a new user gets today

`agent-token-saver` (ATS) installs in one line and is honest about what it did
not install. Its `doctor` runs at the end of the install, prints one line per
layer, and names the exact command for each missing optional tool. That part
of the journey is good and is not changed here.

What the user gets, per host, with the `lean` profile and no optional tools:

| Host | Installed | What it does from the first prompt |
|---|---|---|
| Codex CLI | prompt hook, Stop hook, compact policy block in `~/.codex/AGENTS.md` | compact-output policy on every prompt; outcome guard on Stop |
| Claude Code | same, plus the RTK `PreToolUse` hook *if* RTK is present | same, plus shell-output compression |
| Hermes | the skill only | nothing automatic; the skill loads when named |
| GG Coder | managed block in `~/AGENTS.md` | policy only |

That is the "core-ready, 50% coverage" state the doctor reports. It is a
truthful number.

## 2. What breaks, in the order a new user hits it

### 2.1 The bootstrap picks the wrong Python and stops

macOS ships `python3` = 3.9 at `/usr/bin/python3`. `install-universal.sh`
execs `python3` blindly, the installer's own floor check fires, and the user
reads *"needs Python 3.11+, but this is 3.9"* — while `/opt/homebrew/bin/python3.12`
sits on the same PATH. The README's one-liner fails on a stock Mac with
Homebrew Python installed. That is the first thing a new user sees.

**Fix.** The bootstrap searches for the newest interpreter that satisfies the
floor (`python3.14` … `python3.11`, then `python3`) before executing anything.
Only when none qualifies does it print the requirement, and then it says what
it found.

### 2.2 The hooks get pinned to an interpreter that cannot run the CLI

Yesterday's change pins a real interpreter in front of each hook so no call
pays a version-manager shim. On the fresh machine it pinned `/usr/bin/python3`
— 3.9. The hooks happened to work because every hook file carries
`from __future__ import annotations`, but the `agent-token-saver` CLI itself
imports `tomllib` (3.11+) and would not. A floor the installer enforces on
itself and then ignores when choosing the runtime for its own hooks is a
contradiction that only shows on a machine unlike the developer's.

**Fix.** `hook_interpreter()` requires the same floor the installer does. It
prefers the interpreter running the installer — which by construction already
passed the check — and otherwise probes candidates by asking each for its
version. The doctor verifies the pinned interpreter still exists *and* still
meets the floor, so a Python upgrade that removes it is reported, not silent.

### 2.3 The skill router is a second install nobody is told about

The catalog lists `skill-router` as an optional, prompt-gated layer of the
`lean` profile, and the prompt hook looks for it at `~/.local/bin/si`. But:

- the doctor's MISSING lines cover three recon tools and **not** the router,
  so a user following "install MISSING lines above, then rerun" never learns
  it exists;
- the router's own `install.sh` writes files but does **not** register its
  observer hook — `si install-hooks --target all` is a second, undocumented
  step, and without it the router never learns which skills get used;
- on a fresh machine `si route` scans **2** skills, both of them ours. The
  router is only as useful as the catalog behind it, and nothing says so.

**Fix.** The doctor reports the router like every other optional tool, with
its install line and, once present, whether the observer hook is registered
and how many skills are indexed. The router's `install.sh` registers the hook
in the same run. The ATS README states in one sentence what the router adds
and what it needs (skills to index).

### 2.4 Hermes gets a skill and nothing else, silently

Without a `SOUL.md` the installer prints *"kept Hermes built-in identity"* and
moves on. The README's badge says Hermes is supported. Both are true, and the
user is left to guess what "supported" means: no policy is active until the
skill is named explicitly.

**Fix.** The doctor says it plainly: *"hermes: skill installed; policy is
explicit-only until a SOUL.md exists"*. A docs line explains the two states.

### 2.5 RTK drifted again

`rtk 0.47.0` on the fresh machine; yesterday's addendum pinned 0.46.0. The
version tracking keeps proving its own necessity. No code change: the
measured filter selection is per run and does not depend on the version. The
research doc gets a one-line note that the pin is a snapshot and the doctor
is the live source.

## 3. What a user needs, per host, stated once

| Need | Codex | Claude Code | Hermes | GG Coder |
|---|---|---|---|---|
| Python 3.11+ on PATH (any name) | required | required | required | required |
| `git` | for the one-line bootstrap | same | same | same |
| RTK (`cargo install rtk` or release binary) | optional, agent-guided | optional, **native hook** | optional | optional |
| skill router (`curl … skill-router/install.sh \| bash`) | optional | optional | optional | optional |
| Skills to route (any `SKILL.md` tree in a known root) | for the router to be useful | same | same | same |
| `SOUL.md` | — | — | for automatic policy | — |
| Bun (for `llmadapter`) | optional | optional | optional | optional |

## 4. What is deliberately *not* done

- **Auto-installing the router or RTK.** The AGENTS.md rule stands: third-party
  tools are detected, never silently installed. The fix is to *say* what is
  missing and how to get it, in the one place the user already reads.
- **Merging the two repos.** The router is useful without ATS (any agent with
  a skills tree) and ATS is useful without the router. Two installs with one
  doctor that sees both is the right shape.
- **Lowering the ATS floor to 3.9.** `tomllib` is the honest reason; a
  backport dependency would break "standard library only".

## 5. Oracles

| Fix | Oracle |
|---|---|
| 2.1 | `install-universal.sh` with `python3`=3.9 and `python3.12` on PATH installs; with only 3.9 it names what it found |
| 2.2 | installer test: pinned interpreter satisfies the floor; doctor test: a pinned 3.9 is an error |
| 2.3 | doctor output on a HOME without `si` contains the install line; router `install.sh` leaves an observer hook registered |
| 2.4 | doctor output for Hermes without `SOUL.md` names the explicit-only state |
| all | both suites green as single plain commands |
