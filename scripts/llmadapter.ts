#!/usr/bin/env bun
// llmadapter — one interface over every lane: OpenRouter, Ollama, CLI agents.
// Born from the 23-lane burst test 2026-07-24. Lanes carry their own quirks
// (some CLI lanes are single-flight or rate-limited) so callers do not have to.
// Integrates with agent-token-saver: per-call JSONL ledger + hermes-style
// usage files consumable by `agent-token-ledger --usage llmadapter=FILE`.

import { createHash } from "node:crypto";
import {
  appendFileSync,
  chmodSync,
  closeSync,
  constants,
  existsSync,
  fstatSync,
  lstatSync,
  mkdirSync,
  openSync,
  readdirSync,
  readFileSync,
  readSync,
  renameSync,
  unlinkSync,
  writeFileSync,
} from "node:fs";
import { homedir } from "node:os";
import { basename, dirname, join } from "node:path";

type Lane = {
  name: string;
  kind: "openrouter" | "ollama" | "cli";
  class: "free" | "paid" | "local" | "cli";
  model?: string;
  cmd?: (prompt: string) => string[];
  stdinCmd?: () => string[];
  localSafe?: boolean;
  tools?: boolean;
  serial?: boolean; // lane rejects concurrent sessions
  // Opt-in lanes are skipped by the class selectors and by `all`. A research
  // lane carries a scraping workload, so it must never join a swarm because
  // somebody asked for "cli". Select it by name.
  optIn?: boolean;
  // OpenRouter's unified reasoning control, sent verbatim as the `reasoning`
  // request field. `null` sends no field at all.
  reasoning?: Record<string, unknown> | null;
  // USD per million output tokens, for the `cheap` selector and for `lanes`.
  // Deliberately not in the result envelope: AgentMaster parses that with
  // deny_unknown_fields, and a price belongs to the lane table, not to a call.
  usdOut?: number;
  // Selector sugar only. The wire `class` stays free|paid|local|cli because
  // AgentMaster validates that set; `cheap` lanes are paid lanes that happen to
  // cost a rounding error.
  cheap?: boolean;
  parse?: (raw: string) => string;
};

// Two lanes were removed 2026-08-01. `poolside/laguna-m.1:free` is gone from
// the catalog ("No endpoints found"). `google/gemma-4-31b-it:free` is still IN
// the catalog with 18 endpoints but every free call returns "Provider returned
// error" — 8/8 across a session. Catalog presence is not availability; run
// `doctor --probe` before adding either back.
const OR_FREE = [
  "nvidia/nemotron-3-super-120b-a12b:free",
  "nvidia/nemotron-3-ultra-550b-a55b:free",
  "nvidia/nemotron-3-nano-30b-a3b:free",
  "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
  "nvidia/nemotron-nano-9b-v2:free",
  "nvidia/nemotron-nano-12b-v2-vl:free",
  "openai/gpt-oss-20b:free",
  "google/gemma-4-26b-a4b-it:free",
  "inclusionai/ling-3.0-flash:free",
  "cohere/north-mini-code:free",
  "poolside/laguna-s-2.1:free",
  "poolside/laguna-xs-2.1:free",
];
// The `cheap` band. Frontier-class output fell to free-lane money in 2026:
// `openai/gpt-5.6-luna` is $0.10/$0.60 per million with a 1.05M window, against
// `moonshotai/kimi-k3` at $3.00/$15.00. Measured 2026-08-01 over three
// closed-form reasoning tasks with a known answer (Kelly fraction, swarm cost,
// Laplace ranking), three samples each:
//
//   openai/gpt-oss-120b      9/9 correct   $0.00046 per 9 calls
//   openai/gpt-5.6-luna      9/9 correct   $0.00093
//   moonshotai/kimi-k2.5     8/9 correct   $0.00303
//   inclusionai/ling-2.6     7/9 correct   $0.00002
//   best free lanes        6-7/9 correct   $0
//
// Listed in measured quality order: array order is the tiebreak for lanes the
// ledger has not judged yet. `poolside/laguna-s-2.1` paid was in this band on a
// single sample and came out 5/9 over nine — worse than its own free variant,
// for money. One sample is not a measurement.
//
// [model, usd per million output tokens, optional lane name override].
const OR_CHEAP: [string, number, string?][] = [
  ["openai/gpt-oss-120b", 0.17],
  ["openai/gpt-5.6-luna", 0.60],
  ["inclusionai/ling-2.6-flash", 0.03],
];
const OR_PAID: [string, number, string?][] = [
  ["moonshotai/kimi-k2.5", 2.85],
  ["moonshotai/kimi-k2.7-code", 3.50],
  ["moonshotai/kimi-k3", 15.00],
];

// Free reasoning lanes emit their chain of thought as visible content, so at a
// 400-token ceiling they hand back a truncated deliberation instead of the
// worker contract. Measured 2026-08-01, 12 free lanes x 2 objectives: turning
// reasoning off cut median completion tokens from 400 to 39, truncation from
// 4/24 to 0/24, and lifted contract compliance from 25% to 88%.
//
// The two exceptions are measured too: gpt-oss-20b answers with an empty
// completion when it receives `enabled:false`, and nemotron-nano-9b-v2 needs
// `exclude` — it keeps reasoning either way, so the only useful setting is the
// one that stops the reasoning from eating the returned budget.
//
// LLMADAPTER_REASONING=on restores the old behaviour (no reasoning field).
const OR_REASONING_OFF = process.env.LLMADAPTER_REASONING !== "on";
const OR_REASONING_DEFAULT: Record<string, unknown> = { enabled: false };
const OR_REASONING_OVERRIDE: Record<string, Record<string, unknown> | null> = {
  "openai/gpt-oss-20b:free": null,
  "nvidia/nemotron-nano-9b-v2:free": { exclude: true },
  // The gpt-oss and luna families were benchmarked without a reasoning field
  // and scored 3/3; gpt-oss is already known to answer empty when it gets one.
  "openai/gpt-oss-120b": null,
  "openai/gpt-5.6-luna": null,
};
const orReasoning = (model: string): Record<string, unknown> | null => {
  if (!OR_REASONING_OFF) return null;
  return model in OR_REASONING_OVERRIDE ? OR_REASONING_OVERRIDE[model] : OR_REASONING_DEFAULT;
};

const ggcoderText = (raw: string) =>
  raw
    .split("\n")
    .map((l) => {
      try {
        const j = JSON.parse(l);
        return j.type === "text_delta" ? j.text : "";
      } catch {
        return "";
      }
    })
    .join("");

const LANES: Lane[] = [
  ...OR_FREE.map((m): Lane => ({ name: m.split("/")[1].replace(":free", ""), kind: "openrouter", class: "free", model: m, reasoning: orReasoning(m) })),
  ...OR_CHEAP.map(([m, usdOut, name]): Lane => ({ name: name ?? m.split("/")[1], kind: "openrouter", class: "paid", model: m, reasoning: orReasoning(m), usdOut, cheap: true })),
  ...OR_PAID.map(([m, usdOut, name]): Lane => ({ name: name ?? m.split("/")[1], kind: "openrouter", class: "paid", model: m, reasoning: orReasoning(m), usdOut })),
  { name: "ollama-gemma4", kind: "ollama", class: "local", model: "gemma4-31b-fast" },
  {
    name: "codex",
    kind: "cli",
    class: "cli",
    cmd: (p) => ["codex", "exec", "--skip-git-repo-check", p],
    stdinCmd: () => ["codex", "exec", "--skip-git-repo-check", "-"],
    tools: true,
  },
  { name: "agy", kind: "cli", class: "cli", cmd: (p) => ["agy", "-p", p, "--dangerously-skip-permissions"] },
  { name: "ggcoder", kind: "cli", class: "cli", cmd: (p) => ["ggcoder", "--json", p], parse: ggcoderText },
  {
    name: "claude-haiku",
    kind: "cli",
    class: "cli",
    cmd: (p) => ["claude", "-p", "--model", "haiku", p],
    stdinCmd: () => ["claude", "-p", "--model", "haiku"],
    tools: true,
  },
];

const BUILTIN_LANE_COUNT = LANES.length;

// Local-only extra lanes live OUTSIDE this repo in
// ~/.agent-token-saver/local-lanes.json so they are usable locally but never
// committed or deployed. Each has a cmd array with a "__PROMPT__" placeholder.
try {
  const lp = join(homedir(), ".agent-token-saver", "local-lanes.json");
  if (existsSync(lp)) {
    const before = lstatSync(lp);
    const currentUid = process.getuid?.();
    if (
      before.isSymbolicLink()
      || !before.isFile()
      || currentUid === undefined
      || before.uid !== currentUid
      || (before.mode & 0o077) !== 0
      || before.size > 64 * 1024
    ) {
      throw new Error("unsafe local lane configuration");
    }
    const fd = openSync(lp, constants.O_RDONLY | constants.O_NOFOLLOW);
    let parsed: any;
    try {
      const opened = fstatSync(fd);
      if (opened.dev !== before.dev || opened.ino !== before.ino) {
        throw new Error("local lane configuration changed while opening");
      }
      parsed = JSON.parse(readFileSync(fd, "utf8"));
    } finally {
      closeSync(fd);
    }
    const extra = parsed.llmadapter ?? [];
    for (const l of extra) {
      const tmpl: string[] = l.cmd;
      const stdinTmpl: string[] | undefined = l.stdin_cmd;
      LANES.push({
        name: l.name, kind: l.kind ?? "cli", class: l.class ?? "cli", serial: l.serial,
        cmd: (p: string) => tmpl.map((x) => (x === "__PROMPT__" ? p : x)),
        stdinCmd: stdinTmpl ? () => stdinTmpl : undefined,
        localSafe: l.local_safe === true,
        tools: l.tools === true,
        // `opt_in` keeps a heavy host lane (a scraper, a browser driver) out of
        // `all` and the class selectors. It is then reachable only by name.
        optIn: l.opt_in === true,
      });
    }
  }
} catch { /* fail-open: no local lanes */ }

// Two lanes under one name share a health record and make `--lanes <name>`
// ambiguous, which is how `poolside/laguna-s-2.1` and its `:free` twin nearly
// became one entry. A host lane may shadow a built-in on purpose, so only the
// built-in table is checked.
{
  const names = LANES.slice(0, BUILTIN_LANE_COUNT).map((l) => l.name);
  const duplicate = names.find((name, index) => names.indexOf(name) !== index);
  if (duplicate) throw new Error(`duplicate built-in lane name: ${duplicate}`);
}

const ATS_DIR = join(homedir(), ".agent-token-saver");
const CACHE_DIR = join(ATS_DIR, "cache", "llmadapter");
const LEDGER_DIR = join(ATS_DIR, "ledger");
const CACHE_TTL_MS = 24 * 3600 * 1000;
const KIND_TIMEOUT_MS: Record<Lane["kind"], number> = { openrouter: 90_000, ollama: 120_000, cli: 170_000 };
const OPENROUTER_URL = process.env.LLMADAPTER_OPENROUTER_URL ?? "https://openrouter.ai/api/v1/chat/completions";
const OLLAMA_URL = process.env.LLMADAPTER_OLLAMA_URL ?? "http://localhost:11434/api/generate";

// `ask` is useful for broad, explicit model comparisons. A swarm is different:
// it is delegated work, so each worker gets a small capsule and the controller
// owns synthesis. Keep the safety/cost boundary in this runtime too, not only
// in the Claude hook.
const SWARM_MAX_WORKERS = 3;
const SWARM_FANOUT_MAX_WORKERS = 64;
const SWARM_CAPSULE_MAX_BYTES = 2_800; // <= 700 UTF-8-bytes/4 visible-input proxy
const SWARM_MAX_RESULT_TOKENS = 500;
// Evidence and skill routing are opt-in extras. They widen the capsule, so they
// carry their own budget instead of eating the objective's. AgentMaster never
// passes the flags that switch them on, so its 2.8 KiB/1.8 KiB contract holds.
const EVIDENCE_MAX_BYTES = 4_000;
const EVIDENCE_DEFAULT_BYTES = 600;
const EVIDENCE_TIMEOUT_MS = 180_000;
const SKILL_ROUTE_MAX_BYTES = 400;
const SKILL_ROUTE_TIMEOUT_MS = 20_000;
// Same 2s ceiling AgentMaster uses: an oracle is a check, not a build step.
const ORACLE_TIMEOUT_MS = 2_000;
// The worker packet itself is capped at 2.8 KiB. Keep the v2 objective below
// that budget and reject instead of silently truncating controller input.
const V2_MAX_PROMPT_BYTES = 1800;
const V2_PROTOCOL = 2;
const V2_CAPSULE_VERSION = "worker-v2.1";
const SWARM_RESULT_CONTRACT =
  "Return only (max 500 tokens): STATUS: PASS|FAIL|BLOCKED; EVIDENCE: exact path or command+exit; HANDOFF: none or one precise question.";

type ToolRoute = { name: string; instruction: string };
const SWARM_TOOL_ROUTES: { pattern: RegExp; route: ToolRoute }[] = [
  {
    pattern: /\b(?:caller|callee|impact|dependency|dependencies|graph)\b/i,
    route: {
      name: "impact graph",
      instruction: "Start `synx ground`; use `graphify query` only when this repository already has graphify-out/graph.json.",
    },
  },
  {
    pattern: /\b(?:log|stack ?trace|stderr|stdout|noisy output)\b/i,
    route: {
      name: "noisy output",
      instruction: "Bound the command first; use `rtk` for supported projections and keep the raw artifact by path.",
    },
  },
  {
    pattern: /\b(?:file|source|code|function|test|bug|repo|repository|import|symbol)\b/i,
    route: {
      name: "local source",
      instruction: "Start with exact `rg`; for structural symbols or imports use scoped `tilth --budget 4000` on the concrete project only.",
    },
  },
  {
    pattern: /\b(?:fresh|latest|current|documentation|docs|research|recherche|api|package)\b/i,
    route: {
      name: "fresh external fact",
      instruction: "Use one bounded primary-source artifact supplied by the controller before making a version, API, price, or policy claim.",
    },
  },
];

function routeWorkerTool(objective: string): ToolRoute | undefined {
  return SWARM_TOOL_ROUTES.find(({ pattern }) => pattern.test(objective))?.route;
}

function truncateUtf8(text: string, maxBytes: number): string {
  if (Buffer.byteLength(text, "utf8") <= maxBytes) return text;
  let out = "";
  let used = 0;
  for (const char of text) {
    const size = Buffer.byteLength(char, "utf8");
    if (used + size > maxBytes) break;
    out += char;
    used += size;
  }
  return out;
}

type SkillRoute = { name: string; path: string };
type EvidenceBlock = {
  usable: boolean;
  source: string;
  sha256: string;
  fetched_at: number;
  text: string;
  note?: string;
  cached: boolean;
};
type CapsuleExtras = { evidence?: EvidenceBlock; skill?: SkillRoute };

// A wide fanout builds the same capsule for every lane. Rebuilding it is cheap
// string work — this memo removes the repeat, it does not remove tokens.
const capsuleMemo = new Map<string, string>();
const CAPSULE_MEMO_MAX = 256;

function evidenceText(evidence: EvidenceBlock): string {
  if (!evidence.usable) {
    return `Evidence: unavailable (${evidence.note ?? "not_fetched"}). Make no fresh-fact claim; report BLOCKED if the objective needs one.`;
  }
  // No wall-clock in the capsule: a timestamp would change the capsule hash on
  // every run and defeat the per-lane cache for identical evidence.
  return [
    `Evidence (controller-supplied, source ${evidence.source}, sha256 ${evidence.sha256.slice(0, 16)}):`,
    evidence.text,
    "Cite only from this evidence for fresh facts. A fresh claim it does not support is FAIL.",
  ].join("\n");
}

function workerCapsule(
  objective: string,
  maxResultTokens = SWARM_MAX_RESULT_TOKENS,
  toolsAvailable = true,
  rejectTruncation = false,
  extras: CapsuleExtras = {},
): string {
  const normalizedObjective = objective.trim();
  const memoKey = JSON.stringify([
    normalizedObjective,
    maxResultTokens,
    toolsAvailable,
    rejectTruncation,
    extras.skill?.path ?? null,
    extras.skill?.name ?? null,
    extras.evidence?.sha256 ?? null,
    extras.evidence?.usable ?? null,
    extras.evidence?.note ?? null,
  ]);
  const memoized = capsuleMemo.get(memoKey);
  if (memoized !== undefined) return memoized;
  const route = toolsAvailable ? routeWorkerTool(normalizedObjective) : undefined;
  const routeHint = toolsAvailable
    ? (route
      ? `Tool lane: ${route.name}. ${route.instruction}`
      : "Tool lane: available; use only the smallest check needed by the oracle.")
    : "Reasoning-only lane: use only controller-provided projected evidence. No tools are available; do not claim commands, file reads, or fresh-source checks.";
  const resultContract = SWARM_RESULT_CONTRACT.replace(
    "max 500 tokens",
    `max ${maxResultTokens} tokens`,
  );
  const skillHint = extras.skill
    ? `Skill route: read only \`${extras.skill.path}\` (${extras.skill.name}) before work; apply only its relevant instructions.`
    : undefined;
  const evidenceHint = extras.evidence ? evidenceText(extras.evidence) : undefined;
  const prefix = [
    `agent-token-saver worker capsule (${V2_CAPSULE_VERSION}).`,
    toolsAvailable
      ? "One closed objective. Do not request or repeat the controller transcript, peer output, or skill catalog. Zero or one routed primary skill. Do not mutate outside the stated objective."
      : "One closed objective. Do not request or repeat the controller transcript or peer output. Reason only from the supplied evidence.",
    "Oracle: report PASS only with direct evidence; otherwise FAIL or BLOCKED. Workers do not chat with peers; the controller may route one targeted handoff.",
    routeHint,
    ...(skillHint ? [skillHint] : []),
    ...(evidenceHint ? [evidenceHint] : []),
    "Objective:",
  ].join("\n");
  // `join("\n")` below contributes one separator on either side of the
  // objective, so budget both even when the objective is empty.
  const fixedPacket = `${prefix}\n\n${resultContract}`;
  // Opt-in extras carry their own budget. Adding them must never shrink the
  // objective budget, otherwise an objective that fit yesterday starts failing.
  const extrasBytes = (skillHint ? Buffer.byteLength(`${skillHint}\n`, "utf8") : 0)
    + (evidenceHint ? Buffer.byteLength(`${evidenceHint}\n`, "utf8") : 0);
  const objectiveBudget = Math.max(
    0,
    SWARM_CAPSULE_MAX_BYTES + extrasBytes - Buffer.byteLength(fixedPacket, "utf8"),
  );
  if (
    rejectTruncation
    && Buffer.byteLength(normalizedObjective, "utf8") > objectiveBudget
  ) {
    throw new V2UsageError("prompt_exceeds_capsule_budget");
  }
  const compactObjective = truncateUtf8(
    normalizedObjective,
    objectiveBudget,
  );
  const packet = [
    prefix,
    compactObjective,
    resultContract,
  ].join("\n");
  if (capsuleMemo.size >= CAPSULE_MEMO_MAX) capsuleMemo.clear();
  capsuleMemo.set(memoKey, packet);
  return packet;
}

function boundedSwarmLanes(lanes: Lane[], fanout: boolean): Lane[] {
  return fanout ? lanes : lanes.slice(0, SWARM_MAX_WORKERS);
}

// ------------------------------------------------------- bounded helper procs
// Skill routing, evidence gathering and oracles all shell out. Each call is
// bounded the same way a lane is: wall timeout, byte ceiling, process group
// kill, and fail-open. None of them may become a second unbounded input path.
type BoundedRun = { code: number | null; stdout: string; timedOut: boolean };

async function runBounded(
  command: string[],
  timeoutMs: number,
  maxBytes: number,
  stdinText?: string,
  env?: Record<string, string>,
): Promise<BoundedRun> {
  let proc: ReturnType<typeof Bun.spawn> | undefined;
  try {
    proc = Bun.spawn(command, {
      stdout: "pipe",
      stderr: "ignore",
      stdin: stdinText === undefined ? "ignore" : "pipe",
      detached: true,
      ...(env ? { env: { ...process.env, ...env } } : {}),
    });
  } catch {
    return { code: null, stdout: "", timedOut: false };
  }
  const child = proc;
  const kill = () => {
    try {
      if (child.pid > 1) process.kill(-child.pid, "SIGKILL");
    } catch {
      try { child.kill("SIGKILL"); } catch {}
    }
  };
  let timedOut = false;
  const timer = setTimeout(() => { timedOut = true; kill(); }, Math.max(1, timeoutMs));
  try {
    if (stdinText !== undefined) {
      child.stdin.write(stdinText);
      child.stdin.end();
    }
    let stdout = "";
    try {
      stdout = await readBoundedStream(child.stdout, maxBytes, kill);
    } catch {
      kill();
      stdout = "";
    }
    const code = await child.exited;
    return { code, stdout, timedOut };
  } catch {
    kill();
    return { code: null, stdout: "", timedOut };
  } finally {
    clearTimeout(timer);
  }
}

// ------------------------------------------------------------- skill routing
// The four built-in regex routes stay the default. `si` knows ~960 skills, so
// when the controller asks for it we let the router name ONE skill and pass the
// path into the capsule. Fail-open: no router, no hit, bad JSON -> no skill line.
async function siSkillRoute(objective: string): Promise<SkillRoute | undefined> {
  if (!Bun.which("si")) return undefined;
  const run = await runBounded(
    ["si", "route", objective, "--max", "1", "--json"],
    SKILL_ROUTE_TIMEOUT_MS,
    256 * 1024,
  );
  if (run.code !== 0 || !run.stdout) return undefined;
  try {
    const parsed = JSON.parse(run.stdout);
    const first = Array.isArray(parsed?.selected) ? parsed.selected[0] : undefined;
    const name = typeof first?.name === "string" ? first.name : undefined;
    const path = typeof first?.path === "string" ? first.path : undefined;
    if (!name || !path || !existsSync(path)) return undefined;
    const line = `Skill route: read only \`${path}\` (${name})`;
    if (Buffer.byteLength(line, "utf8") > SKILL_ROUTE_MAX_BYTES) return undefined;
    return { name, path };
  } catch {
    return undefined;
  }
}

// ------------------------------------------------------------------ evidence
// Most built-in lanes have no tools, and their capsule forbids fresh-fact
// claims. So the controller has to supply the fact. Order: url-cache (no
// network) -> provider -> project -> url-cache put.
//
// The provider is a host-supplied executable, never a bundled scraper:
//
//   $LLMADAPTER_EVIDENCE_CMD <research|mega|fetch>   # query on stdin
//
// It prints the artifact on stdout and exits 0. If it reports a bot wall
// (`page_status: challenge`), that is a hard stop: a challenge page is not
// evidence, and the capsule then tells the worker to report BLOCKED.
const EVIDENCE_CMD = process.env.LLMADAPTER_EVIDENCE_CMD;
const EVIDENCE_CACHE_SCHEME = "llmadapter://evidence/";
/// Providers use this exit code to say "I am busy", not "there is nothing".
const EVIDENCE_BUSY_EXIT = 4;

function evidenceCacheKey(mode: string, query: string): string {
  return `${EVIDENCE_CACHE_SCHEME}${mode}/${sha256(query)}`;
}

function projectEvidence(raw: string, maxBytes: number): string {
  const cleaned = raw
    .replace(/\r/g, "")
    .split("\n")
    .map((line) => line.replace(/[\u0000-\u0008\u000B-\u001F\u007F]/g, "").trimEnd())
    .filter((line) => line.length > 0)
    .join("\n");
  return truncateUtf8(cleaned, maxBytes).trim();
}

function evidenceIsChallenged(raw: string): boolean {
  return /"page_status"\s*:\s*"challenge"/.test(raw)
    || /\bbrowser_challenge:/.test(raw)
    || /\bpage_status:\s*challenge\b/.test(raw);
}

async function evidenceCacheGet(key: string): Promise<string | undefined> {
  if (!Bun.which("ats-url-cache")) return undefined;
  const run = await runBounded(["ats-url-cache", "get", key], 5_000, 4 * 1024 * 1024);
  return run.code === 0 && run.stdout.trim() ? run.stdout : undefined;
}

async function evidenceCachePut(key: string, body: string): Promise<void> {
  if (!Bun.which("ats-url-cache")) return;
  await runBounded(["ats-url-cache", "put", key], 5_000, 4 * 1024, body);
}

async function gatherEvidence(
  objective: string,
  mode: "research" | "mega" | "fetch" | "primary",
  target: string,
  maxBytes: number,
  useCache: boolean,
): Promise<EvidenceBlock> {
  const key = evidenceCacheKey(mode, target);
  const now = Date.now();
  // The envelope never echoes controller input — the prompt is hash-only, and
  // an evidence target is controller input too.
  const sourceLabel = `${mode}:${sha256(target).slice(0, 16)}`;
  if (useCache) {
    const hit = await evidenceCacheGet(key);
    if (hit) {
      const text = projectEvidence(hit, maxBytes);
      if (text) {
        return {
          usable: true,
          source: sourceLabel,
          sha256: sha256(hit),
          fetched_at: now,
          text,
          cached: true,
        };
      }
    }
  }
  if (!EVIDENCE_CMD || !existsSync(EVIDENCE_CMD)) {
    return { usable: false, source: sourceLabel, sha256: sha256(""), fetched_at: now, text: "", note: "evidence_provider_unset", cached: false };
  }
  const run = await runBounded(
    [EVIDENCE_CMD, mode],
    EVIDENCE_TIMEOUT_MS,
    4 * 1024 * 1024,
    target,
    // Tell the provider how long it has. A provider guessing its own deadline
    // either wastes the budget or gets killed mid-write, which reaches the
    // controller as "no evidence" for a query that had plenty.
    { LLMADAPTER_EVIDENCE_DEADLINE_MS: String(EVIDENCE_TIMEOUT_MS) },
  );
  if (run.timedOut) {
    return { usable: false, source: sourceLabel, sha256: sha256(""), fetched_at: now, text: "", note: "evidence_timeout", cached: false };
  }
  if (run.code === EVIDENCE_BUSY_EXIT) {
    // A provider that is busy has not told us the query has no evidence. The
    // difference matters: busy is worth retrying later, unavailable is not.
    return { usable: false, source: sourceLabel, sha256: sha256(""), fetched_at: now, text: "", note: "evidence_provider_busy", cached: false };
  }
  if (run.code !== 0 || !run.stdout.trim()) {
    return { usable: false, source: sourceLabel, sha256: sha256(""), fetched_at: now, text: "", note: "evidence_unavailable", cached: false };
  }
  if (evidenceIsChallenged(run.stdout)) {
    // A challenge page is a stop, not a source. Never a bypass attempt.
    return { usable: false, source: sourceLabel, sha256: sha256(run.stdout), fetched_at: now, text: "", note: "page_status_challenge", cached: false };
  }
  const text = projectEvidence(run.stdout, maxBytes);
  if (!text) {
    return { usable: false, source: sourceLabel, sha256: sha256(run.stdout), fetched_at: now, text: "", note: "evidence_empty", cached: false };
  }
  if (useCache) await evidenceCachePut(key, run.stdout);
  return {
    usable: true,
    source: sourceLabel,
    sha256: sha256(run.stdout),
    fetched_at: now,
    text,
    cached: false,
  };
}

// ------------------------------------------------------------------- oracle
// Same shape AgentMaster uses: the exit code is the decision, zero is PASS. The
// answer reaches the oracle as a private 0600 file, never as an argv string.
type OracleVerdict = { pass: boolean; code: number | null; timedOut: boolean };

async function runOracle(
  oracle: string,
  answerPath: string,
  runDir: string,
  envPrefix?: string,
): Promise<OracleVerdict> {
  // A controller usually already has an oracle written against its own variable
  // names. Without an alias that oracle reads an empty path here and silently
  // never passes, which turns --first-pass into an expensive no-op.
  const aliases = envPrefix
    ? { [`${envPrefix}_ANSWER_PATH`]: answerPath, [`${envPrefix}_RUN_DIR`]: runDir }
    : {};
  const proc = Bun.spawn(["/bin/sh", "-c", oracle], {
    stdout: "ignore",
    stderr: "ignore",
    stdin: "ignore",
    detached: true,
    env: {
      ...process.env,
      ...aliases,
      LLMADAPTER_ANSWER_PATH: answerPath,
      LLMADAPTER_RUN_DIR: runDir,
    },
  });
  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    try {
      if (proc.pid > 1) process.kill(-proc.pid, "SIGKILL");
    } catch {
      try { proc.kill("SIGKILL"); } catch {}
    }
  }, ORACLE_TIMEOUT_MS);
  try {
    const code = await proc.exited;
    return { pass: !timedOut && code === 0, code, timedOut };
  } finally {
    clearTimeout(timer);
  }
}

function orKey(): string {
  if (process.env.OPENROUTER_API_KEY) return process.env.OPENROUTER_API_KEY;
  const env = readFileSync(join(homedir(), ".hermes", ".env"), "utf8");
  const m = env.match(/^OPENROUTER_API_KEY=["']?([^"'\n]+)/m);
  if (!m) throw new Error("OPENROUTER_API_KEY not found (env or ~/.hermes/.env)");
  return m[1];
}

type Result = {
  lane: string;
  model?: string;
  ok: boolean;
  ms: number;
  answer?: string;
  error?: "quota" | "auth" | "timeout" | "empty" | "exec";
  detail?: string;
  cached?: boolean;
  in_tokens?: number;
  out_tokens?: number;
  est?: boolean; // tokens are bytes/4 estimates (cli lanes), not provider-reported
};

type V2Transport = "stdin" | "prompt_file" | "unknown";
type V2CapMode = "provider_server" | "local_native" | "advisory_only";
// "pruned" is emitted ONLY under --first-pass. AgentMaster's result validator
// accepts succeeded|failed|timeout|output_limit|cached and rejects anything
// else, and it never passes --first-pass, so its contract stays intact.
type V2Terminal = "succeeded" | "failed" | "timeout" | "output_limit" | "cached" | "pruned";
type V2TokenSource = "provider_reported" | "estimated" | "unknown";

type ResultV2 = {
  lane: string;
  model?: string;
  kind: Lane["kind"];
  class: Lane["class"];
  ok: boolean;
  terminal: V2Terminal;
  ms: number;
  answer?: string;
  error?: string;
  detail?: string;
  cached?: boolean;
  call_started: boolean;
  input_tokens: number | null;
  output_tokens: number | null;
  token_count_source: V2TokenSource;
  max_tokens: number;
  cap_mode: V2CapMode;
};

type InternalResultV2 = ResultV2;

type TokenCoverageV2 = {
  reported: number;
  estimated: number;
  unknown_calls: number;
};

type AccountingV2 = {
  schema: "llmadapter.accounting";
  schema_version: 2;
  status: "complete";
  terminal_records_complete: true;
  prompt_sha256: string;
  prompt_bytes: number;
  transport: V2Transport;
  stage: "worker";
  requested_lane_spec: string;
  selected_lane_count: number;
  lane_cap: number;
  fanout: boolean;
  max_tokens: number;
  calls_started: number;
  calls_completed: number;
  cache_hits: number;
  input_tokens: TokenCoverageV2;
  output_tokens: TokenCoverageV2;
  estimated_cost_usd: null;
  cost_status: "unknown";
  completed: true;
  failed: boolean;
};

type AskV2Output = {
  schema: "llmadapter.result";
  schema_version: 2;
  status: "ok" | "partial" | "failed" | "invalid";
  exit_code: number;
  prompt: { sha256: string; bytes: number; transport: V2Transport };
  stage: "worker";
  lanes: { requested: string; selected: number; cap: number; fanout: boolean };
  ok: number;
  total: number;
  results: ResultV2[];
  accounting: AccountingV2;
  error?: string;
  // Present only with --first-pass / --evidence / --skill-route. AgentMaster
  // parses this envelope with deny_unknown_fields, so these keys must stay
  // absent on the path it drives.
  first_pass?: FirstPassReport;
  evidence?: EvidenceReport;
  skill_route?: SkillRoute;
};

type FirstPassReport = {
  oracle: boolean;
  oracle_runs: number;
  winner: string | null;
  winner_oracle_exit: number | null;
  pruned: number;
  run_dir: string | null;
};

type EvidenceReport = {
  mode: "research" | "mega" | "fetch" | "primary";
  target_sha256: string;
  usable: boolean;
  cached: boolean;
  bytes: number;
  source: string;
  sha256: string;
  note?: string;
};

class V2UsageError extends Error {}
class V2OutputLimitError extends Error {}

function classify(msg: string): Result["error"] {
  if (/quota|rate.?limit|429|credits/i.test(msg)) return "quota";
  if (/unauthorized|401|403|login|IneligibleTier|auth/i.test(msg)) return "auth";
  return "exec";
}
// daily/credit quotas don't recover within a run; plain 429 rate-limits do
const isHardQuota = (msg: string) => /quota reached|upgrade|credits|resets in/i.test(msg);

// A dropped connection is the common failure when several lanes hit the same
// host at once — Bun reports it as "The socket connection was closed
// unexpectedly", other layers as ECONNRESET/EPIPE. It throws out of `fetch`
// rather than returning a response, so before 2026-08-01 it bypassed the
// per-lane retry entirely and one transient close killed the lane. Our own
// AbortSignal deadline and a first-pass prune are real decisions, never retried.
const isRetryableTransport = (msg: string) =>
  !/abort|timeout/i.test(msg)
  && /socket|econnreset|epipe|econnrefused|network|fetch failed|closed unexpectedly|stream/i.test(msg);

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
const normPrompt = (p: string) => p.trim().replace(/\s+/g, " ").toLowerCase();

function cachePath(lane: Lane, prompt: string): string {
  const h = createHash("sha256").update(`${lane.name}\0${normPrompt(prompt)}`).digest("hex").slice(0, 32);
  return join(CACHE_DIR, `${h}.json`);
}

function ledgerWrite(r: Result): void {
  try {
    mkdirSync(LEDGER_DIR, { recursive: true });
    const month = new Date().toISOString().slice(0, 7).replace("-", "");
    appendFileSync(join(LEDGER_DIR, `llmadapter-${month}.jsonl`), JSON.stringify({ ts: new Date().toISOString(), ...r, answer: undefined, detail: undefined }) + "\n");
  } catch {} // ledger is observability, never fails the call
}

// ---------------------------------------------------------------- PII shield
// Every lane except ollama sends the prompt to a third party. OpenRouter routes
// free models to providers that may train on prompts unless the account opts
// out, and that setting is separate for free and paid models. Measured
// 2026-07-25: leads-fanout-classifier.py pushed 301 German company names — for
// sole traders that is personal data — through free lanes with no masking.
//
// So: pseudonymise before the request leaves this machine, restore the tokens in
// the answer. The shield lives in ggadapter; it is loaded lazily so a machine
// without it only pays when a remote lane actually runs.
const SHIELD_PATH = process.env.ATS_SHIELD_PATH
  ?? join(homedir(), "BASE", "ggprojects", "ggadapter", "adapter", "dsgvo-shield.mjs");
const SHIELD_OFF = process.env.ATS_PII_SHIELD === "0";
const LOCAL_KINDS = new Set<Lane["kind"]>(["ollama"]);

let shieldMod: any; // undefined = not tried yet, null = unavailable
async function loadShield(): Promise<any> {
  if (shieldMod !== undefined) return shieldMod;
  try {
    shieldMod = await import(SHIELD_PATH);
  } catch {
    shieldMod = null;
  }
  return shieldMod;
}

type Shielded = { prompt: string; restore: (answer: string) => string; masked: number };

async function shieldPrompt(
  lane: Lane,
  prompt: string,
  remoteOverride?: boolean,
): Promise<Shielded> {
  const asIs: Shielded = { prompt, restore: (a) => a, masked: 0 };
  const remote = remoteOverride ?? !LOCAL_KINDS.has(lane.kind);
  if (SHIELD_OFF || !remote) return asIs;

  const mod = await loadShield();
  // Fail closed: a remote lane must not see raw text just because the shield is
  // missing. ATS_PII_SHIELD=0 is the deliberate, visible way to opt out.
  if (!mod) {
    throw new Error(
      `PII shield unavailable at ${SHIELD_PATH} — refusing to send to remote lane "${lane.name}". `
      + `Set ATS_SHIELD_PATH, or ATS_PII_SHIELD=0 to send unmasked on purpose.`,
    );
  }

  const policy = { dsgvoShield: { ...mod.DEFAULT_DSGVO_POLICY, enabled: true } };
  const res = mod.protectOutgoingText(prompt, policy, `llmadapter-${lane.name}`, { includeReplacementMap: true });
  if (!res.changed) return asIs;
  const map = res.replacementMap;
  return {
    prompt: res.text,
    masked: map?.entryCount ?? 0,
    restore: (answer) => {
      try {
        return mod.applyDsgvoRestoreMap(answer, map, { fillPlaceholders: false }).text;
      } catch {
        return answer; // a failed restore leaves tokens visible; it never leaks
      }
    },
  };
}

async function runLane(lane: Lane, prompt: string, timeoutMs: number | undefined, useCache: boolean, maxTokens: number): Promise<Result> {
  const tmo = timeoutMs ?? KIND_TIMEOUT_MS[lane.kind];
  const cp = cachePath(lane, prompt);
  if (useCache && existsSync(cp)) {
    const c = JSON.parse(readFileSync(cp, "utf8"));
    if (Date.now() - c.ts < CACHE_TTL_MS) {
      const r: Result = { lane: lane.name, model: lane.model, ok: true, ms: 0, answer: c.answer, cached: true, in_tokens: 0, out_tokens: 0 };
      ledgerWrite({ ...r, out_tokens: c.out_tokens ?? 0 }); // record what the cache saved
      return r;
    }
  }
  await sleep(Math.random() * 400); // jitter against thundering herd
  const t0 = Date.now();
  let result: Result;
  try {
    // `sent` is what actually leaves the machine; `prompt` stays local (cache
    // key, token estimate). A throw here aborts the lane before any egress.
    const shielded = await shieldPrompt(lane, prompt);
    const sent = shielded.prompt;
    let answer = "";
    let inTok: number | undefined, outTok: number | undefined, est = false;
    if (lane.kind === "openrouter") {
      let lastMsg = "";
      // Three attempts, not two: a dropped socket now costs a retry instead of
      // the whole lane, and it must not eat the retry a 429 needs.
      for (let attempt = 0; attempt < 3; attempt++) {
        if (attempt > 0) await sleep(/429|rate.?limit/i.test(lastMsg) ? 5000 : 2000 + Math.random() * 1000);
        let res: Response;
        let j: any;
        try {
          res = await fetch(OPENROUTER_URL, {
            method: "POST",
            headers: { Authorization: `Bearer ${orKey()}`, "Content-Type": "application/json" },
            body: JSON.stringify({
              model: lane.model,
              max_tokens: maxTokens,
              messages: [{ role: "user", content: sent }],
              ...(lane.reasoning ? { reasoning: lane.reasoning } : {}),
            }),
            signal: AbortSignal.timeout(tmo),
          });
          j = await res.json();
        } catch (e: any) {
          lastMsg = String(e);
          if (!isRetryableTransport(lastMsg)) throw e;
          continue;
        }
        if (res.ok && !j.error) {
          answer = j.choices?.[0]?.message?.content ?? "";
          inTok = j.usage?.prompt_tokens;
          outTok = j.usage?.completion_tokens;
          break;
        }
        lastMsg = j.error?.message ?? `HTTP ${res.status}`;
        if (classify(lastMsg) === "auth" || isHardQuota(lastMsg)) break;
      }
      if (!answer && lastMsg) {
        result = { lane: lane.name, model: lane.model, ok: false, ms: Date.now() - t0, error: classify(lastMsg), detail: lastMsg.slice(0, 160) };
        ledgerWrite(result);
        return result;
      }
    } else if (lane.kind === "ollama") {
      const res = await fetch(OLLAMA_URL, {
        method: "POST",
        body: JSON.stringify({ model: lane.model, prompt: sent, stream: false }),
        signal: AbortSignal.timeout(tmo),
      });
      const j: any = await res.json();
      answer = j.response ?? "";
      inTok = j.prompt_eval_count;
      outTok = j.eval_count;
    } else {
      const proc = Bun.spawn(lane.cmd!(sent), { stdout: "pipe", stderr: "pipe", stdin: "ignore" });
      const killer = setTimeout(() => proc.kill(), tmo);
      const [out, err] = await Promise.all([new Response(proc.stdout).text(), new Response(proc.stderr).text()]);
      const code = await proc.exited;
      clearTimeout(killer);
      const raw = out || err;
      if (code !== 0 && !out.trim()) {
        const msg = (err || out || `exit ${code}`).slice(0, 300);
        result = { lane: lane.name, ok: false, ms: Date.now() - t0, error: classify(msg), detail: msg.slice(0, 160) };
        ledgerWrite(result);
        return result;
      }
      answer = (lane.parse ? lane.parse(raw) : out).trim();
      inTok = Math.round(sent.length / 4); // ats convention: bytes/4 estimate
      outTok = Math.round(answer.length / 4);
      est = true;
    }
    const ms = Date.now() - t0;
    // Put the real values back before anything downstream (cache, caller) sees
    // the answer — the cache is keyed on the unmasked prompt, so it must hold
    // the unmasked answer to stay consistent.
    answer = shielded.restore(answer);
    if (!answer.trim()) {
      result = { lane: lane.name, model: lane.model, ok: false, ms, error: "empty" };
    } else {
      mkdirSync(CACHE_DIR, { recursive: true });
      writeFileSync(cp, JSON.stringify({ ts: Date.now(), answer, out_tokens: outTok }));
      result = { lane: lane.name, model: lane.model, ok: true, ms, answer, in_tokens: inTok, out_tokens: outTok, est: est || undefined };
    }
  } catch (e: any) {
    const timedOut = /timeout|abort/i.test(String(e));
    result = { lane: lane.name, model: lane.model, ok: false, ms: Date.now() - t0, error: timedOut ? "timeout" : classify(String(e)), detail: String(e).slice(0, 160) };
  }
  ledgerWrite(result);
  return result;
}

// v2 stays colocated while v1 and v2 share Lane and PII-shield semantics.
// Keep all v2 trust, I/O and cache boundaries in this block; split it only
// after the v1 CLI can import the same module without changing legacy output.
const V2_STDOUT_MAX_BYTES = 256 * 1024;
const V2_STDERR_MAX_BYTES = 16 * 1024;
const V2_HTTP_BODY_MAX_BYTES = 1024 * 1024;
const V2_CACHE_ANSWER_MAX_BYTES = V2_STDOUT_MAX_BYTES;

function sha256(text: string): string {
  return createHash("sha256").update(text, "utf8").digest("hex");
}

function v2CachePath(
  lane: Lane,
  promptHash: string,
  maxTokens: number,
  capsuleHash: string,
  commandHash: string,
): string {
  const key = [
    `llmadapter-v${V2_PROTOCOL}`,
    "worker",
    V2_CAPSULE_VERSION,
    capsuleHash,
    lane.name,
    lane.model ?? "",
    String(maxTokens),
    promptHash,
    commandHash,
  ].join("\0");
  return join(CACHE_DIR, `v2-${createHash("sha256").update(key).digest("hex").slice(0, 40)}.json`);
}

type LaneTrustV2 = { remote: boolean; paid: boolean };

function isLoopbackUrl(raw: string): boolean {
  try {
    const hostname = new URL(raw).hostname.replace(/^\[|\]$/g, "").toLowerCase();
    return hostname === "localhost"
      || hostname === "::1"
      || hostname === "0:0:0:0:0:0:0:1"
      || /^127(?:\.\d{1,3}){0,3}$/.test(hostname);
  } catch {
    return false;
  }
}

function laneTrustV2(lane: Lane): LaneTrustV2 {
  if (!["openrouter", "ollama", "cli"].includes(lane.kind)) {
    throw new V2UsageError("lane_kind_invalid");
  }
  if (!["free", "paid", "local", "cli"].includes(lane.class)) {
    throw new V2UsageError("lane_class_invalid");
  }
  if (lane.kind === "openrouter") {
    if (!lane.model || !["free", "paid"].includes(lane.class)) {
      throw new V2UsageError("openrouter_lane_config_invalid");
    }
    return { remote: true, paid: lane.class === "paid" };
  }
  if (lane.kind === "ollama") {
    if (!lane.model || lane.class !== "local") {
      throw new V2UsageError("ollama_lane_config_invalid");
    }
    return { remote: !isLoopbackUrl(OLLAMA_URL), paid: false };
  }
  // CLI agents may invoke a provider even when launched locally. Only a
  // private host lane carrying the explicit local_safe bit is treated local.
  return {
    remote: lane.localSafe !== true,
    paid: lane.class === "paid",
  };
}

function capMode(lane: Lane): V2CapMode {
  if (lane.kind === "openrouter") return "provider_server";
  if (lane.kind === "ollama") return "local_native";
  return "advisory_only";
}

function cleanResultV2(result: InternalResultV2): ResultV2 {
  return { ...result };
}

function boundedDetail(code: string): string {
  return code.replace(/[^a-z0-9_.:-]/gi, "_").slice(0, 80);
}

async function readBoundedStream(
  stream: ReadableStream<Uint8Array> | null,
  maxBytes: number,
  abort: () => void,
): Promise<string> {
  if (!stream) return "";
  const reader = stream.getReader();
  const chunks: Uint8Array[] = [];
  let bytes = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      bytes += value.byteLength;
      if (bytes > maxBytes) {
        abort();
        throw new V2OutputLimitError();
      }
      chunks.push(value);
    }
  } finally {
    reader.releaseLock();
  }
  const all = new Uint8Array(bytes);
  let offset = 0;
  for (const chunk of chunks) {
    all.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return new TextDecoder("utf-8", { fatal: false }).decode(all);
}

async function fetchJsonBounded(
  url: string,
  init: RequestInit,
  deadlineAt: number,
  externalSignal?: AbortSignal,
): Promise<{ response: Response; json: any }> {
  const remaining = deadlineAt - Date.now();
  if (remaining <= 0) throw new DOMException("deadline", "TimeoutError");
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), remaining);
  // A first-pass winner prunes its peers: the same abort has to reach the
  // in-flight socket, not just the bookkeeping.
  const onExternalAbort = () => controller.abort();
  externalSignal?.addEventListener("abort", onExternalAbort, { once: true });
  if (externalSignal?.aborted) controller.abort();
  try {
    const response = await fetch(url, {
      ...init,
      redirect: "error",
      signal: controller.signal,
    });
    const declaredLength = Number(response.headers.get("content-length"));
    if (
      Number.isFinite(declaredLength)
      && declaredLength > V2_HTTP_BODY_MAX_BYTES
    ) {
      controller.abort();
      throw new V2OutputLimitError();
    }
    const body = await readBoundedStream(
      response.body,
      V2_HTTP_BODY_MAX_BYTES,
      () => controller.abort(),
    );
    return { response, json: JSON.parse(body) };
  } finally {
    clearTimeout(timer);
    externalSignal?.removeEventListener("abort", onExternalAbort);
  }
}

function v2Failure(
  lane: Lane,
  maxTokens: number,
  terminal: V2Terminal,
  error: string,
  ms: number,
  started: boolean,
): InternalResultV2 {
  return {
    lane: lane.name,
    model: lane.model,
    kind: lane.kind,
    class: lane.class,
    ok: false,
    terminal,
    ms,
    error: boundedDetail(error),
    input_tokens: null,
    output_tokens: null,
    token_count_source: "unknown",
    max_tokens: maxTokens,
    cap_mode: capMode(lane),
    call_started: started,
  };
}

type LaneRunOptions = {
  // Set only by --first-pass. An aborted lane is reported as `pruned`.
  signal?: AbortSignal;
  // Hard per-lane token ceiling. Unlike --max-tokens (a requested provider
  // ceiling) this one is enforced here: refuse before the call when the input
  // alone exceeds it, bound the CLI stream, and fail the record when the
  // reported total exceeds it.
  budgetTokens?: number;
};

async function runLaneV2(
  lane: Lane,
  prompt: string,
  promptHash: string,
  deadlineAt: number,
  useCache: boolean,
  maxTokens: number,
  trust: LaneTrustV2,
  options: LaneRunOptions = {},
): Promise<InternalResultV2> {
  if (options.signal?.aborted) {
    return v2Failure(lane, maxTokens, "pruned", "pruned_before_start", 0, false);
  }
  const command = lane.kind === "cli" && lane.stdinCmd ? lane.stdinCmd() : undefined;
  if (
    command
    && (
      !Array.isArray(command)
      || command.length === 0
      || command.some((part) => typeof part !== "string" || part.length === 0)
    )
  ) {
    return v2Failure(lane, maxTokens, "failed", "stdin_command_invalid", 0, false);
  }
  const capsuleHash = sha256(prompt);
  const commandHash = sha256(JSON.stringify(command ?? []));
  const cache = v2CachePath(
    lane,
    promptHash,
    maxTokens,
    capsuleHash,
    commandHash,
  );
  if (useCache && existsSync(cache)) {
    try {
      if (lstatSync(cache).isSymbolicLink()) throw new Error("unsafe cache entry");
      const saved = JSON.parse(readFileSync(cache, "utf8"));
      if (
        typeof saved === "object"
        && saved !== null
        && saved.schema === "llmadapter.cache"
        && saved.protocol === V2_PROTOCOL
        && saved.stage === "worker"
        && saved.capsule_version === V2_CAPSULE_VERSION
        && saved.capsule_sha256 === capsuleHash
        && saved.lane === lane.name
        && saved.model === (lane.model ?? null)
        && saved.max_tokens === maxTokens
        && saved.prompt_sha256 === promptHash
        && saved.stdin_command_sha256 === commandHash
        && Number.isFinite(saved.ts)
        && saved.ts <= Date.now()
        && Date.now() - saved.ts < CACHE_TTL_MS
        && typeof saved.answer === "string"
        && saved.answer.length > 0
        && Buffer.byteLength(saved.answer, "utf8") <= V2_CACHE_ANSWER_MAX_BYTES
      ) {
        return {
          lane: lane.name,
          model: lane.model,
          kind: lane.kind,
          class: lane.class,
          ok: true,
          terminal: "cached",
          ms: 0,
          answer: saved.answer,
          cached: true,
          input_tokens: 0,
          output_tokens: 0,
          token_count_source: "unknown",
          max_tokens: maxTokens,
          cap_mode: capMode(lane),
          call_started: false,
        };
      }
    } catch {
      // Corrupt cache entries are misses. The live call remains authoritative.
    }
  }

  const remaining = deadlineAt - Date.now();
  if (remaining <= 0) return v2Failure(lane, maxTokens, "timeout", "global_deadline", 0, false);

  const t0 = Date.now();
  let callStarted = false;
  try {
    const shielded = await shieldPrompt(lane, prompt, trust.remote);
    const sent = shielded.prompt;
    const budget = options.budgetTokens;
    if (budget !== undefined && Math.ceil(Buffer.byteLength(sent, "utf8") / 4) > budget) {
      // Refuse before spending: an input that already blows the budget cannot
      // produce a within-budget call.
      return v2Failure(lane, maxTokens, "failed", "budget_input_exceeds", Date.now() - t0, false);
    }
    let answer = "";
    let inputTokens: number | null = null;
    let outputTokens: number | null = null;
    let tokenSource: V2TokenSource = "unknown";
    if (lane.kind === "openrouter") {
      const apiKey = orKey();
      callStarted = true;
      const request: RequestInit = {
        method: "POST",
        headers: { Authorization: `Bearer ${apiKey}`, "Content-Type": "application/json" },
        body: JSON.stringify({
          model: lane.model,
          max_tokens: maxTokens,
          messages: [{ role: "user", content: sent }],
          ...(lane.reasoning ? { reasoning: lane.reasoning } : {}),
        }),
      };
      let res: Response;
      let json: any;
      for (let attempt = 0; ; attempt++) {
        try {
          ({ response: res, json } = await fetchJsonBounded(OPENROUTER_URL, request, deadlineAt, options.signal));
          break;
        } catch (error: any) {
          // One bounded retry for a dropped socket, and only while the
          // controller deadline still leaves room for a whole call. Everything
          // else — prune, deadline, body cap — stays a terminal decision.
          const retryable = attempt < 1
            && !options.signal?.aborted
            && isRetryableTransport(String(error))
            && deadlineAt - Date.now() > 5_000;
          if (!retryable) throw error;
          await sleep(1_000 + Math.random() * 1_000);
        }
      }
      if (!res.ok || json.error) {
        return v2Failure(
          lane,
          maxTokens,
          "failed",
          `provider_${res.status}`,
          Date.now() - t0,
          true,
        );
      }
      const choice = json.choices?.[0];
      answer = choice?.message?.content ?? "";
      inputTokens = Number.isFinite(json.usage?.prompt_tokens) ? json.usage.prompt_tokens : null;
      outputTokens = Number.isFinite(json.usage?.completion_tokens) ? json.usage.completion_tokens : null;
      tokenSource = inputTokens !== null || outputTokens !== null ? "provider_reported" : "unknown";
      // A provider that stopped at the token ceiling did not finish the worker
      // contract, so `succeeded` would make a truncated deliberation look like
      // a result. CLI lanes already report the same case as `output_limit`.
      if (choice?.finish_reason === "length") {
        return v2Failure(lane, maxTokens, "output_limit", "provider_finish_length", Date.now() - t0, true);
      }
    } else if (lane.kind === "ollama") {
      callStarted = true;
      const { response: res, json } = await fetchJsonBounded(OLLAMA_URL, {
        method: "POST",
        body: JSON.stringify({
          model: lane.model,
          prompt: sent,
          stream: false,
          options: { num_predict: maxTokens },
        }),
      }, deadlineAt, options.signal);
      if (!res.ok) {
        return v2Failure(
          lane,
          maxTokens,
          "failed",
          `ollama_${res.status}`,
          Date.now() - t0,
          true,
        );
      }
      answer = json.response ?? "";
      inputTokens = Number.isFinite(json.prompt_eval_count) ? json.prompt_eval_count : null;
      outputTokens = Number.isFinite(json.eval_count) ? json.eval_count : null;
      tokenSource = inputTokens !== null || outputTokens !== null ? "provider_reported" : "unknown";
    } else {
      if (!command) {
        return v2Failure(
          lane,
          maxTokens,
          "failed",
          "stdin_transport_unsupported",
          Date.now() - t0,
          false,
        );
      }
      const proc = Bun.spawn(command, {
        stdout: "pipe",
        stderr: "pipe",
        stdin: "pipe",
        detached: true,
      });
      callStarted = true;
      proc.stdin.write(sent);
      proc.stdin.end();
      let killedForDeadline = false;
      const kill = () => {
        try {
          if (proc.pid > 1) process.kill(-proc.pid, "SIGKILL");
        } catch {
          try { proc.kill("SIGKILL"); } catch {}
        }
      };
      let killedForPrune = false;
      const onPrune = () => {
        killedForPrune = true;
        kill();
      };
      options.signal?.addEventListener("abort", onPrune, { once: true });
      const timer = setTimeout(() => {
        killedForDeadline = true;
        kill();
      }, Math.max(1, deadlineAt - Date.now()));
      // With a budget the stream itself is the enforcement point: 4 bytes per
      // token is the same estimator the lane already uses for CLI accounting.
      const stdoutCap = budget !== undefined
        ? Math.min(V2_STDOUT_MAX_BYTES, Math.max(1, budget * 4))
        : V2_STDOUT_MAX_BYTES;
      let stdout = "";
      let stderr = "";
      try {
        [stdout, stderr] = await Promise.all([
          readBoundedStream(proc.stdout, stdoutCap, kill),
          readBoundedStream(proc.stderr, V2_STDERR_MAX_BYTES, kill),
        ]);
      } catch (error) {
        kill();
        await proc.exited;
        clearTimeout(timer);
        options.signal?.removeEventListener("abort", onPrune);
        if (killedForPrune) {
          return v2Failure(lane, maxTokens, "pruned", "pruned_in_flight", Date.now() - t0, true);
        }
        if (error instanceof V2OutputLimitError) {
          return v2Failure(
            lane,
            maxTokens,
            "output_limit",
            stdoutCap < V2_STDOUT_MAX_BYTES ? "budget_output_exceeds" : "output_limit",
            Date.now() - t0,
            true,
          );
        }
        throw error;
      }
      const code = await proc.exited;
      clearTimeout(timer);
      options.signal?.removeEventListener("abort", onPrune);
      if (killedForPrune) {
        return v2Failure(lane, maxTokens, "pruned", "pruned_in_flight", Date.now() - t0, true);
      }
      if (killedForDeadline || Date.now() >= deadlineAt) {
        return v2Failure(
          lane,
          maxTokens,
          "timeout",
          "global_deadline",
          Date.now() - t0,
          true,
        );
      }
      if (code !== 0) {
        return v2Failure(
          lane,
          maxTokens,
          "failed",
          `cli_exit_${code}`,
          Date.now() - t0,
          true,
        );
      }
      answer = (lane.parse ? lane.parse(stdout || stderr) : stdout).trim();
      inputTokens = Math.ceil(Buffer.byteLength(sent, "utf8") / 4);
      outputTokens = Math.ceil(Buffer.byteLength(answer, "utf8") / 4);
      tokenSource = "estimated";
    }

    answer = shielded.restore(answer).trim();
    if (!answer) {
      return v2Failure(lane, maxTokens, "failed", "empty", Date.now() - t0, true);
    }
    if (budget !== undefined && (inputTokens ?? 0) + (outputTokens ?? 0) > budget) {
      // The call already happened, so this is honest evidence of overspend, not
      // prevention. Prevention is the pre-flight check plus the CLI stream cap.
      return v2Failure(lane, maxTokens, "output_limit", "budget_exceeded", Date.now() - t0, true);
    }
    const result: InternalResultV2 = {
      lane: lane.name,
      model: lane.model,
      kind: lane.kind,
      class: lane.class,
      ok: true,
      terminal: "succeeded",
      ms: Date.now() - t0,
      answer,
      input_tokens: inputTokens,
      output_tokens: outputTokens,
      token_count_source: tokenSource,
      max_tokens: maxTokens,
      cap_mode: capMode(lane),
      call_started: callStarted,
    };
    if (useCache) {
      try {
        mkdirSync(CACHE_DIR, { recursive: true, mode: 0o700 });
        chmodSync(CACHE_DIR, 0o700);
        atomicPrivateJson(cache, {
          schema: "llmadapter.cache",
          protocol: V2_PROTOCOL,
          stage: "worker",
          capsule_version: V2_CAPSULE_VERSION,
          capsule_sha256: capsuleHash,
          lane: lane.name,
          model: lane.model ?? null,
          max_tokens: maxTokens,
          prompt_sha256: promptHash,
          stdin_command_sha256: commandHash,
          ts: Date.now(),
          answer,
        });
      } catch {
        // Cache is optional and never changes the live result.
      }
    }
    return result;
  } catch (error: any) {
    if (options.signal?.aborted) {
      return v2Failure(lane, maxTokens, "pruned", "pruned_in_flight", Date.now() - t0, callStarted);
    }
    if (error instanceof V2OutputLimitError) {
      return v2Failure(
        lane,
        maxTokens,
        "output_limit",
        "http_body_limit",
        Date.now() - t0,
        callStarted,
      );
    }
    const timedOut = Date.now() >= deadlineAt || /timeout|abort/i.test(String(error));
    return v2Failure(
      lane,
      maxTokens,
      timedOut ? "timeout" : "failed",
      timedOut ? "global_deadline" : "lane_error",
      Date.now() - t0,
      callStarted,
    );
  }
}

async function pool<T>(items: (() => Promise<T>)[], cap: number): Promise<T[]> {
  const out: T[] = new Array(items.length);
  let i = 0;
  await Promise.all(
    Array.from({ length: Math.min(cap, items.length) }, async () => {
      while (i < items.length) {
        const idx = i++;
        out[idx] = await items[idx]();
      }
    }),
  );
  return out;
}

// hedged-request race: resolve as soon as `first` lanes answered ok
async function race(items: (() => Promise<Result>)[], cap: number, first: number): Promise<Result[]> {
  return new Promise((resolve) => {
    const done: Result[] = [];
    let ok = 0, settled = 0, i = 0, finished = false;
    const finish = () => { if (!finished) { finished = true; resolve(done); } };
    const next = () => {
      if (finished || i >= items.length) return;
      const idx = i++;
      items[idx]().then((r) => {
        settled++;
        done.push(r);
        if (r.ok) ok++;
        if (ok >= first || settled >= items.length) finish();
        else next();
      });
    };
    for (let k = 0; k < Math.min(cap, items.length); k++) next();
  });
}

// A class selector hands back more lanes than the worker cap takes, so the cap
// decides which lanes actually run — and in array order that was always the
// first three. Meanwhile the ledger already records ok/failed per lane on every
// call, so the health of every lane is on disk and was never read. Ordering the
// class selectors by it means a provider outage sinks that lane and a healthy
// one takes the slot, instead of the swarm losing a third of its capacity while
// ten working lanes sit unused.
//
// Only class selectors are reordered. `--lanes a,b,c` is the caller stating an
// order, and a controller comparing two named lanes must get those two lanes.
const LANE_HEALTH_WINDOW_MS = 7 * 24 * 3600 * 1000;
const LANE_HEALTH_MAX_RECORDS = 4_000;

function laneHealth(): Map<string, number> {
  const scores = new Map<string, number>();
  if (process.env.LLMADAPTER_LANE_HEALTH === "0") return scores;
  try {
    const month = new Date().toISOString().slice(0, 7).replace("-", "");
    const path = join(LEDGER_DIR, `llmadapter-${month}.jsonl`);
    if (!existsSync(path)) return scores;
    const lines = readFileSync(path, "utf8").trim().split("\n").slice(-LANE_HEALTH_MAX_RECORDS);
    const cutoff = Date.now() - LANE_HEALTH_WINDOW_MS;
    const tally = new Map<string, { calls: number; ok: number }>();
    for (const line of lines) {
      let row: any;
      try { row = JSON.parse(line); } catch { continue; }
      // A cache hit says nothing about whether the provider is up today.
      if (row.cached) continue;
      if (Date.parse(row.ts) < cutoff) continue;
      const t = tally.get(row.lane) ?? { calls: 0, ok: 0 };
      t.calls++;
      if (row.ok) t.ok++;
      tally.set(row.lane, t);
    }
    // Laplace smoothing, so one lucky call does not outrank a long good record
    // and a lane with no history lands at 0.5 — between proven-good and
    // proven-broken, which is exactly what "unknown" deserves.
    for (const [lane, t] of tally) scores.set(lane, (t.ok + 1) / (t.calls + 2));
  } catch {
    // Health is an optimisation. A missing or corrupt ledger means array order.
  }
  return scores;
}

// `cheap` is selector sugar over the paid class, not a fifth class: the wire
// `class` set is what AgentMaster validates. It still needs --allow-paid,
// because a rounding error is still money.
const laneMatchesSelector = (lane: Lane, part: string): boolean => {
  if (part === "cheap") return lane.cheap === true && !lane.optIn;
  if (["free", "paid", "local", "cli"].includes(part)) return lane.class === part && !lane.optIn;
  return lane.name === part || lane.model === part;
};

function pickLanes(spec: string): Lane[] {
  // `all` and the class selectors stay free of opt-in lanes: asking for "cli"
  // must not silently start a scraping workload. Naming the lane still works.
  const selectors = ["free", "cheap", "paid", "local", "cli"];
  const parts = spec.split(",").map((s) => s.trim());
  const selected = spec === "all"
    ? LANES.filter((l) => !l.optIn)
    : LANES.filter((l) => parts.some((p) => laneMatchesSelector(l, p)));
  if (spec !== "all" && !parts.every((p) => selectors.includes(p))) return selected;
  const health = laneHealth();
  if (health.size === 0) return selected;
  // Stable: equal scores keep their array order, so the same ledger always
  // yields the same lane list. Within the paid class array order is price
  // order, so an unproven expensive lane never outranks an unproven cheap one.
  return selected
    .map((lane, index) => ({ lane, index, score: health.get(lane.name) ?? 0.5 }))
    .sort((a, b) => (b.score - a.score) || (a.index - b.index))
    .map((entry) => entry.lane);
}

// The vendor prefix of an OpenRouter id ("nvidia/nemotron-…" -> "nvidia").
// Two lanes from one vendor share a family, a tokenizer and usually an outage,
// so they do not cross-check each other.
const laneFamily = (lane: Lane) => lane.model?.split("/")[0] ?? lane.name;

// Aggregation and verification are single-lane calls, so one dead lane loses the
// whole step — and both used to name a fixed lane. `gpt-oss-20b` was the pinned
// verifier while the ledger recorded it at 5/10. Pick by measured health
// instead, and let the caller pin one by name when they want a fixed comparison.
function healthiestLane(exclude?: Lane): Lane {
  const health = laneHealth();
  const candidates = LANES
    .filter((l) => l.class === "free" && l.kind === "openrouter")
    .filter((l) => !exclude || laneFamily(l) !== laneFamily(exclude))
    .map((lane, index) => ({ lane, index, score: health.get(lane.name) ?? 0.5 }))
    .sort((a, b) => (b.score - a.score) || (a.index - b.index));
  return candidates[0]?.lane ?? LANES[0];
}

async function aggregate(prompt: string, results: Result[], maxTokens: number): Promise<string> {
  const okR = results.filter((r) => r.ok);
  const body = okR.map((r) => `[${r.lane}]: ${r.answer}`).join("\n");
  const agg = await runLane(aggregatorLane(),
    `${okR.length} Modelle beantworteten parallel: "${prompt}". Dedupliziere zu den besten unterschiedlichen Punkten, je 1 Zeile deutsch, nach Praxiswert sortiert:\n${body}`,
    undefined, false, maxTokens * 2);
  return agg.ok ? agg.answer! : `(Aggregation fehlgeschlagen: ${agg.error})`;
}

function aggregatorLane(): Lane {
  const want = process.env.LLMADAPTER_AGGREGATE_LANE;
  return (want ? LANES.find((l) => l.name === want) : undefined) ?? healthiestLane();
}

// Fresh-context verifier (Anthropic Fable-5 multi-agent pattern: an
// independent fresh-context verifier beats self-critique). Runs one strong lane
// to check the answer; returns whether it passed + the verifier text. The
// verifier must be INDEPENDENT of the aggregator: a different model family gives
// a real cross-check and avoids rate-limiting the same lane twice back-to-back.
function strongLane(): Lane {
  const want = process.env.LLMADAPTER_VERIFY_LANE;
  return (want ? LANES.find((l) => l.name === want) : undefined) ?? healthiestLane(aggregatorLane());
}
async function verify(question: string, answer: string, maxTokens: number): Promise<{ ok: boolean; text: string }> {
  const p = `You are an independent verifier with fresh context. Check the proposed answer against the question. If it is correct and complete, reply exactly: VERIFIED. If it is wrong or incomplete, reply: CORRECTION: <the correct answer>.\n\nQuestion: ${question}\n\nProposed answer:\n${answer}`;
  const r = await runLane(strongLane(), p, undefined, false, maxTokens);
  const text = r.ok ? r.answer!.trim() : `(verify failed: ${r.error})`;
  return { ok: /^\s*VERIFIED/i.test(text), text };
}

// --tier: pilotfish/Anthropic tiered pattern — cheap fast lanes PROPOSE, one
// strong lane AGGREGATES, a fresh strong lane VERIFIES. Best quality per $.
const TIER_PROPOSERS = [
  "nemotron-3-nano-30b-a3b", "nemotron-nano-9b-v2", "nemotron-nano-12b-v2-vl",
  "gpt-oss-20b", "ling-3.0-flash",
];

function usageOut(path: string, results: Result[]): void {
  const okR = results.filter((r) => r.ok);
  writeFileSync(path, JSON.stringify({
    estimated_cost_usd: 0.0,
    cost_status: okR.some((r) => r.est) ? "estimated" : "unknown",
    cost_source: "llmadapter",
    input_tokens: results.reduce((s, r) => s + (r.cached ? 0 : (r.in_tokens ?? 0)), 0),
    output_tokens: results.reduce((s, r) => s + (r.cached ? 0 : (r.out_tokens ?? 0)), 0),
    cache_read_tokens: 0,
    cache_write_tokens: 0,
    reasoning_tokens: 0,
    total_tokens: results.reduce((s, r) => s + (r.cached ? 0 : (r.in_tokens ?? 0) + (r.out_tokens ?? 0)), 0),
    api_calls: results.filter((r) => !r.cached).length,
    model: "multi-lane",
    provider: "llmadapter",
    session_id: `${Date.now()}`,
    completed: true,
    failed: okR.length === 0,
    service_tier: null,
  }, null, 2));
}

type AskV2Options = {
  transport: Exclude<V2Transport, "unknown">;
  promptFile?: string;
  swarm: boolean;
  fanout: boolean;
  lanes: string;
  cap: number;
  maxTokens: number;
  deadlineSecs: number;
  useCache: boolean;
  allowRemote: boolean;
  allowPaid: boolean;
  usageOut?: string;
  // Opt-in extensions. AgentMaster passes none of them, so its contract holds.
  firstPass: boolean;
  oracle?: string;
  oracleEnvPrefix?: string;
  budgetTokens?: number;
  evidence: boolean;
  evidenceMode: "research" | "mega" | "fetch" | "primary";
  evidenceTarget?: string;
  evidenceBytes: number;
  skillRoute: boolean;
};

function parsePositiveInt(value: string | undefined, name: string, max: number): number {
  if (!value || !/^[1-9]\d*$/.test(value)) throw new V2UsageError(`${name}_invalid`);
  const parsed = Number(value);
  if (!Number.isSafeInteger(parsed) || parsed > max) throw new V2UsageError(`${name}_invalid`);
  return parsed;
}

function parseAskV2(argv: string[]): AskV2Options {
  const booleans = new Set([
    "--stdin",
    "--swarm",
    "--fanout",
    "--no-cache",
    "--allow-remote",
    "--allow-paid",
    "--first-pass",
    "--evidence",
    "--skill-route",
  ]);
  const values = new Set([
    "--prompt-file",
    "--lanes",
    "--cap",
    "--max-tokens",
    "--deadline-secs",
    "--usage-out",
    "--oracle",
    "--oracle-env-prefix",
    "--budget-tokens",
    "--evidence-mode",
    "--evidence-target",
    "--evidence-bytes",
  ]);
  const rejected = new Set(["--first", "--aggregate", "--verify", "--tier"]);
  const seen = new Set<string>();
  const parsed = new Map<string, string>();
  for (let index = 0; index < argv.length; index++) {
    const token = argv[index];
    if (rejected.has(token)) throw new V2UsageError(`${token.slice(2)}_unsupported`);
    if (booleans.has(token)) {
      if (seen.has(token)) throw new V2UsageError(`${token.slice(2)}_duplicate`);
      seen.add(token);
      continue;
    }
    if (values.has(token)) {
      if (seen.has(token)) throw new V2UsageError(`${token.slice(2)}_duplicate`);
      const value = argv[++index];
      if (!value || value.startsWith("--")) throw new V2UsageError(`${token.slice(2)}_missing`);
      seen.add(token);
      parsed.set(token, value);
      continue;
    }
    throw new V2UsageError(token.startsWith("--") ? "unknown_option" : "positional_prompt_forbidden");
  }
  const stdin = seen.has("--stdin");
  const promptFile = parsed.get("--prompt-file");
  if (Number(stdin) + Number(Boolean(promptFile)) !== 1) {
    throw new V2UsageError("prompt_transport_exactly_one");
  }
  const swarm = seen.has("--swarm");
  if (!swarm) throw new V2UsageError("swarm_required");
  const fanout = seen.has("--fanout");
  if (fanout && !swarm) throw new V2UsageError("fanout_requires_swarm");
  const cap = parsed.has("--cap")
    ? parsePositiveInt(parsed.get("--cap"), "cap", SWARM_FANOUT_MAX_WORKERS)
    : SWARM_MAX_WORKERS;
  const evidenceMode = parsed.get("--evidence-mode") ?? "research";
  if (!["research", "mega", "fetch", "primary"].includes(evidenceMode)) {
    throw new V2UsageError("evidence_mode_invalid");
  }
  if ((parsed.has("--evidence-mode") || parsed.has("--evidence-target") || parsed.has("--evidence-bytes"))
    && !seen.has("--evidence")) {
    throw new V2UsageError("evidence_flags_require_evidence");
  }
  if (evidenceMode === "fetch" && !parsed.has("--evidence-target")) {
    throw new V2UsageError("evidence_fetch_requires_target");
  }
  const oracle = parsed.get("--oracle");
  if (oracle !== undefined && !oracle.trim()) throw new V2UsageError("oracle_empty");
  const oracleEnvPrefix = parsed.get("--oracle-env-prefix");
  if (oracleEnvPrefix !== undefined) {
    if (oracle === undefined) throw new V2UsageError("oracle_env_prefix_requires_oracle");
    if (!/^[A-Z][A-Z0-9_]{0,31}$/.test(oracleEnvPrefix)) {
      throw new V2UsageError("oracle_env_prefix_invalid");
    }
  }
  return {
    transport: stdin ? "stdin" : "prompt_file",
    promptFile,
    swarm,
    fanout,
    lanes: parsed.get("--lanes") ?? "local",
    cap,
    maxTokens: parsed.has("--max-tokens")
      ? parsePositiveInt(parsed.get("--max-tokens"), "max_tokens", SWARM_MAX_RESULT_TOKENS)
      : SWARM_MAX_RESULT_TOKENS,
    deadlineSecs: parsed.has("--deadline-secs")
      ? parsePositiveInt(parsed.get("--deadline-secs"), "deadline_secs", 3600)
      : 120,
    useCache: !seen.has("--no-cache"),
    allowRemote: seen.has("--allow-remote"),
    allowPaid: seen.has("--allow-paid"),
    usageOut: parsed.get("--usage-out"),
    firstPass: seen.has("--first-pass"),
    oracle: parsed.get("--oracle"),
    oracleEnvPrefix,
    budgetTokens: parsed.has("--budget-tokens")
      ? parsePositiveInt(parsed.get("--budget-tokens"), "budget_tokens", 1_000_000)
      : undefined,
    evidence: seen.has("--evidence"),
    evidenceMode: evidenceMode as "research" | "mega" | "fetch" | "primary",
    evidenceTarget: parsed.get("--evidence-target"),
    evidenceBytes: parsed.has("--evidence-bytes")
      ? parsePositiveInt(parsed.get("--evidence-bytes"), "evidence_bytes", EVIDENCE_MAX_BYTES)
      : EVIDENCE_DEFAULT_BYTES,
    skillRoute: seen.has("--skill-route"),
  };
}

function readPromptFdV2(fd: number): Buffer {
  const chunks: Buffer[] = [];
  let total = 0;
  while (true) {
    const chunk = Buffer.allocUnsafe(Math.min(64 * 1024, V2_MAX_PROMPT_BYTES + 1));
    const bytes = readSync(fd, chunk, 0, chunk.length, null);
    if (bytes === 0) break;
    total += bytes;
    if (total > V2_MAX_PROMPT_BYTES) throw new V2UsageError("prompt_too_large");
    chunks.push(chunk.subarray(0, bytes));
  }
  return Buffer.concat(chunks, total);
}

function decodePromptV2(bytes: Buffer): string {
  try {
    const prompt = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
    if (!prompt.trim()) throw new V2UsageError("prompt_empty");
    return prompt;
  } catch (error) {
    if (error instanceof V2UsageError) throw error;
    throw new V2UsageError("prompt_invalid_utf8");
  }
}

function readPromptV2(options: AskV2Options): string {
  if (options.transport === "stdin") return decodePromptV2(readPromptFdV2(0));
  const path = options.promptFile!;
  let fd: number | undefined;
  try {
    const before = lstatSync(path);
    const currentUid = typeof process.getuid === "function" ? process.getuid() : undefined;
    if (
      before.isSymbolicLink()
      || !before.isFile()
      || (currentUid !== undefined && before.uid !== currentUid)
      || (before.mode & 0o077) !== 0
    ) {
      throw new V2UsageError("prompt_file_unsafe");
    }
    fd = openSync(path, constants.O_RDONLY | (constants.O_NOFOLLOW ?? 0));
    const opened = fstatSync(fd);
    if (
      !opened.isFile()
      || opened.dev !== before.dev
      || opened.ino !== before.ino
      || (currentUid !== undefined && opened.uid !== currentUid)
      || (opened.mode & 0o077) !== 0
    ) {
      throw new V2UsageError("prompt_file_unsafe");
    }
    return decodePromptV2(readPromptFdV2(fd));
  } catch (error) {
    if (error instanceof V2UsageError) throw error;
    throw new V2UsageError("prompt_file_unsafe");
  } finally {
    if (fd !== undefined) {
      try { closeSync(fd); } catch {}
    }
  }
}

function validateUsagePath(path: string): void {
  if (existsSync(path)) {
    const stat = lstatSync(path);
    if (stat.isSymbolicLink() || !stat.isFile()) throw new V2UsageError("usage_out_unsafe");
  }
}

function atomicPrivateJson(path: string, value: unknown): void {
  validateUsagePath(path);
  const parent = dirname(path);
  mkdirSync(parent, { recursive: true, mode: 0o700 });
  const temporary = join(
    parent,
    `.${basename(path)}.${process.pid}.${Date.now()}.${Math.random().toString(16).slice(2)}.tmp`,
  );
  let fd: number | undefined;
  try {
    fd = openSync(temporary, "wx", 0o600);
    writeFileSync(fd, `${JSON.stringify(value)}\n`, "utf8");
    closeSync(fd);
    fd = undefined;
    chmodSync(temporary, 0o600);
    renameSync(temporary, path);
    chmodSync(path, 0o600);
  } catch (error) {
    if (fd !== undefined) {
      try { closeSync(fd); } catch {}
    }
    try { unlinkSync(temporary); } catch {}
    throw error;
  }
}

// An oracle reads the answer from a private file, never from argv. Same rule
// the prompt already follows in both directions.
function atomicPrivateText(path: string, text: string): void {
  validateUsagePath(path);
  mkdirSync(dirname(path), { recursive: true, mode: 0o700 });
  const fd = openSync(path, "wx", 0o600);
  try {
    writeFileSync(fd, text, "utf8");
  } finally {
    closeSync(fd);
  }
  chmodSync(path, 0o600);
}

function privateRunDir(): string {
  const dir = join(ATS_DIR, "runs", `llmadapter-${process.pid}-${Date.now()}`);
  mkdirSync(dir, { recursive: true, mode: 0o700 });
  chmodSync(dir, 0o700);
  return dir;
}

// --first-pass: every lane starts at once, the oracle decides one at a time,
// and the first PASS prunes the rest. Without an oracle the first ok answer
// wins. Losers keep their record with terminal "pruned" — a pruned lane is
// evidence of a cheaper run, not a failure to hide.
type FirstPassOutcome = {
  results: InternalResultV2[];
  winner: string | null;
  winnerOracleExit: number | null;
  oracleRuns: number;
  runDir: string | null;
};

async function runFirstPass(
  lanes: Lane[],
  start: (lane: Lane, index: number, signal: AbortSignal) => Promise<InternalResultV2>,
  oracle: string | undefined,
  oracleEnvPrefix?: string,
): Promise<FirstPassOutcome> {
  const controller = new AbortController();
  const results: InternalResultV2[] = new Array(lanes.length);
  const runDir = oracle ? privateRunDir() : null;
  let winner: string | null = null;
  let winnerOracleExit: number | null = null;
  let oracleRuns = 0;
  // Serialize the decision so exactly one lane can win.
  let gate: Promise<void> = Promise.resolve();
  await Promise.all(lanes.map(async (lane, index) => {
    const result = await start(lane, index, controller.signal);
    results[index] = result;
    if (!result.ok || !result.answer || winner !== null) return;
    const decide = gate.then(async () => {
      if (winner !== null) return;
      if (!oracle) {
        winner = result.lane;
        controller.abort();
        return;
      }
      const answerPath = join(runDir!, `answer-${index}-${result.lane.replace(/[^a-z0-9_.-]/gi, "_")}.txt`);
      try {
        atomicPrivateText(answerPath, result.answer!);
      } catch {
        return;
      }
      oracleRuns++;
      const verdict = await runOracle(oracle, answerPath, runDir!, oracleEnvPrefix);
      if (verdict.pass) {
        winner = result.lane;
        winnerOracleExit = verdict.code;
        controller.abort();
      }
    });
    gate = decide;
    await decide;
  }));
  return { results, winner, winnerOracleExit, oracleRuns, runDir };
}

function tokenCoverage(results: InternalResultV2[], side: "input_tokens" | "output_tokens"): TokenCoverageV2 {
  const coverage: TokenCoverageV2 = { reported: 0, estimated: 0, unknown_calls: 0 };
  for (const result of results) {
    if (!result.call_started || result.cached) continue;
    const count = result[side];
    if (result.token_count_source === "provider_reported" && count !== null) {
      coverage.reported += count;
    } else if (result.token_count_source === "estimated" && count !== null) {
      coverage.estimated += count;
    } else {
      coverage.unknown_calls++;
    }
  }
  return coverage;
}

function accountingV2(
  promptHash: string,
  promptBytes: number,
  transport: V2Transport,
  requestedLanes: string,
  selectedLaneCount: number,
  laneCap: number,
  fanout: boolean,
  maxTokens: number,
  results: InternalResultV2[],
): AccountingV2 {
  return {
    schema: "llmadapter.accounting",
    schema_version: 2,
    status: "complete",
    terminal_records_complete: true,
    prompt_sha256: promptHash,
    prompt_bytes: promptBytes,
    transport,
    stage: "worker",
    requested_lane_spec: requestedLanes,
    selected_lane_count: selectedLaneCount,
    lane_cap: laneCap,
    fanout,
    max_tokens: maxTokens,
    calls_started: results.filter((result) => result.call_started).length,
    calls_completed: results.filter((result) => result.call_started).length,
    cache_hits: results.filter((result) => result.cached).length,
    input_tokens: tokenCoverage(results, "input_tokens"),
    output_tokens: tokenCoverage(results, "output_tokens"),
    estimated_cost_usd: null,
    cost_status: "unknown",
    completed: true,
    failed: results.length === 0 || results.every((result) => !result.ok),
  };
}

function emptyAskV2Output(error: string, exitCode = 64): AskV2Output {
  const hash = sha256("");
  const accounting = accountingV2(hash, 0, "unknown", "local", 0, 0, false, 0, []);
  return {
    schema: "llmadapter.result",
    schema_version: 2,
    status: "invalid",
    exit_code: exitCode,
    prompt: { sha256: hash, bytes: 0, transport: "unknown" },
    stage: "worker",
    lanes: { requested: "local", selected: 0, cap: 0, fanout: false },
    ok: 0,
    total: 0,
    results: [],
    accounting,
    error: boundedDetail(error),
  };
}

async function askV2(argv: string[]): Promise<AskV2Output> {
  const options = parseAskV2(argv);
  if (options.usageOut) validateUsagePath(options.usageOut);
  return askV2WithPrompt(options, readPromptV2(options));
}

// Split out so `council` can run the identical worker stage and then add one
// synthesis pass, instead of growing a second worker code path.
async function askV2WithPrompt(options: AskV2Options, prompt: string): Promise<AskV2Output> {
  const promptHash = sha256(prompt);
  const promptBytes = Buffer.byteLength(prompt, "utf8");
  const requested = pickLanes(options.lanes);
  if (!requested.length) throw new V2UsageError("no_lanes_matched");
  const effectiveCap = Math.min(
    options.cap,
    options.fanout ? SWARM_FANOUT_MAX_WORKERS : SWARM_MAX_WORKERS,
  );
  const lanes = requested.slice(0, effectiveCap);
  const laneTrust = lanes.map((lane) => laneTrustV2(lane));
  const hasRemote = laneTrust.some((trust) => trust.remote);
  const hasPaid = laneTrust.some((trust) => trust.paid);
  if (hasRemote && !options.allowRemote) throw new V2UsageError("remote_requires_allow_remote");
  if (hasPaid && (!options.allowRemote || !options.allowPaid)) {
    throw new V2UsageError("paid_requires_allow_remote_and_allow_paid");
  }
  if (options.allowPaid && !options.allowRemote) {
    throw new V2UsageError("allow_paid_requires_allow_remote");
  }
  // Extras run before the lane deadline starts: gathering evidence must not
  // eat the workers' wall clock. Both are fail-open by construction.
  const skill = options.skillRoute ? await siSkillRoute(prompt) : undefined;
  const evidence = options.evidence
    ? await gatherEvidence(
      prompt,
      options.evidenceMode,
      options.evidenceTarget ?? prompt,
      options.evidenceBytes,
      options.useCache,
    )
    : undefined;
  const extras: CapsuleExtras = { skill, evidence };
  const deadlineAt = Date.now() + options.deadlineSecs * 1000;
  const laneRunOptions = (signal?: AbortSignal): LaneRunOptions => ({
    signal,
    budgetTokens: options.budgetTokens,
  });
  const startLane = (lane: Lane, index: number, signal?: AbortSignal) => runLaneV2(
    lane,
    workerCapsule(prompt, options.maxTokens, lane.tools === true, true, extras),
    promptHash,
    deadlineAt,
    options.useCache,
    options.maxTokens,
    laneTrust[index],
    laneRunOptions(signal),
  );
  let results: InternalResultV2[];
  let firstPass: FirstPassOutcome | undefined;
  if (options.firstPass) {
    firstPass = await runFirstPass(
      lanes,
      (lane, index, signal) => startLane(lane, index, signal),
      options.oracle,
      options.oracleEnvPrefix,
    );
    results = firstPass.results;
  } else {
    results = await pool(
      lanes.map((lane, index) => () => startLane(lane, index)),
      lanes.length,
    );
  }
  const ok = results.filter((result) => result.ok).length;
  const accounting = accountingV2(
    promptHash,
    promptBytes,
    options.transport,
    options.lanes,
    lanes.length,
    effectiveCap,
    options.fanout,
    options.maxTokens,
    results,
  );
  // status/exit describe LANE outcomes, and the v2 contract fixes the mapping:
  // exit 0 exactly when the status is ok or partial. The oracle verdict is a
  // different question and lives in `first_pass.winner` — folding it into the
  // exit code would produce partial+1, which a strict controller rejects.
  const status = ok === 0 ? "failed" : ok === results.length ? "ok" : "partial";
  const exitCode = ok === 0 ? 1 : 0;
  const output: AskV2Output = {
    schema: "llmadapter.result",
    schema_version: 2,
    status,
    exit_code: exitCode,
    prompt: { sha256: promptHash, bytes: promptBytes, transport: options.transport },
    stage: "worker",
    lanes: {
      requested: options.lanes,
      selected: lanes.length,
      cap: effectiveCap,
      fanout: options.fanout,
    },
    ok,
    total: results.length,
    results: results.map(cleanResultV2),
    accounting,
  };
  if (firstPass) {
    output.first_pass = {
      oracle: Boolean(options.oracle),
      oracle_runs: firstPass.oracleRuns,
      winner: firstPass.winner,
      winner_oracle_exit: firstPass.winnerOracleExit,
      pruned: results.filter((result) => result.terminal === "pruned").length,
      run_dir: firstPass.runDir,
    };
  }
  if (evidence) {
    output.evidence = {
      mode: options.evidenceMode,
      target_sha256: sha256(options.evidenceTarget ?? prompt),
      usable: evidence.usable,
      cached: evidence.cached,
      bytes: Buffer.byteLength(evidence.text, "utf8"),
      source: evidence.source,
      sha256: evidence.sha256,
      ...(evidence.note ? { note: evidence.note } : {}),
    };
  }
  if (skill) output.skill_route = skill;
  if (options.usageOut) atomicPrivateJson(options.usageOut, accounting);
  return output;
}

// ------------------------------------------------------------------ council
// `--tier` aggregates, `--verify` checks one answer. A council does the third
// thing: N independent workers, then ONE fresh-context lane that names the
// consensus AND the dissent. Dissent is the product — a swarm that only ever
// reports agreement is a swarm you cannot audit.
const COUNCIL_ANSWER_MAX_BYTES = 1_500;
const COUNCIL_SYNTH_MAX_TOKENS = 1_000;

type CouncilSynthesis = {
  lane: string;
  ok: boolean;
  terminal: V2Terminal;
  ms: number;
  text?: string;
  error?: string;
};

type CouncilOutput = {
  schema: "llmadapter.council";
  schema_version: 1;
  status: "ok" | "partial" | "failed" | "invalid";
  exit_code: number;
  question_sha256: string;
  synth_lane: string;
  workers: AskV2Output;
  synthesis: CouncilSynthesis | null;
  error?: string;
};

async function councilRun(argv: string[]): Promise<CouncilOutput> {
  // Synthesis is a single call, so a pinned dead lane loses the whole council.
  // Same measured pick as the verifier, and still overridable by name.
  let synthLaneName = process.env.LLMADAPTER_COUNCIL_LANE ?? strongLane().name;
  const passthrough: string[] = [];
  for (let index = 0; index < argv.length; index++) {
    if (argv[index] === "--synth-lane") {
      const value = argv[++index];
      if (!value || value.startsWith("--")) throw new V2UsageError("synth_lane_missing");
      synthLaneName = value;
      continue;
    }
    passthrough.push(argv[index]);
  }
  if (!passthrough.includes("--swarm")) passthrough.push("--swarm");
  const options = parseAskV2(passthrough);
  if (options.usageOut) validateUsagePath(options.usageOut);
  const prompt = readPromptV2(options);
  const synthLane = LANES.find((lane) => lane.name === synthLaneName);
  if (!synthLane) throw new V2UsageError("synth_lane_unknown");
  const synthTrust = laneTrustV2(synthLane);
  // Gate the synthesis lane before spending a single worker call.
  if (synthTrust.remote && !options.allowRemote) {
    throw new V2UsageError("remote_requires_allow_remote");
  }
  if (synthTrust.paid && (!options.allowRemote || !options.allowPaid)) {
    throw new V2UsageError("paid_requires_allow_remote_and_allow_paid");
  }
  const workers = await askV2WithPrompt(options, prompt);
  const answers = workers.results.filter((result) => result.ok && result.answer);
  if (!answers.length) {
    return {
      schema: "llmadapter.council",
      schema_version: 1,
      status: "failed",
      exit_code: 1,
      question_sha256: sha256(prompt),
      synth_lane: synthLane.name,
      workers,
      synthesis: null,
      error: "no_worker_answers",
    };
  }
  const body = answers
    .map((result) => `[${result.lane}]\n${truncateUtf8(result.answer!.trim(), COUNCIL_ANSWER_MAX_BYTES)}`)
    .join("\n\n");
  const synthPrompt = [
    `${answers.length} independent workers answered the same objective. You did not see their work; judge only the text below.`,
    "Return exactly these three lines and nothing else:",
    "CONSENSUS: the answer the worker evidence actually supports.",
    "DISSENT: one line per real disagreement, or `none`.",
    "CONFIDENCE: high|medium|low + the single fact that decides it.",
    "",
    `Objective:\n${truncateUtf8(prompt.trim(), V2_MAX_PROMPT_BYTES)}`,
    "",
    `Worker answers:\n${body}`,
  ].join("\n");
  const synthDeadline = Date.now() + options.deadlineSecs * 1000;
  const synthResult = await runLaneV2(
    synthLane,
    synthPrompt,
    sha256(synthPrompt),
    synthDeadline,
    false, // synthesis is over this run's fresh answers; a cache hit would lie
    Math.min(COUNCIL_SYNTH_MAX_TOKENS, options.maxTokens * 2),
    synthTrust,
    { budgetTokens: options.budgetTokens },
  );
  const synthesis: CouncilSynthesis = {
    lane: synthResult.lane,
    ok: synthResult.ok,
    terminal: synthResult.terminal,
    ms: synthResult.ms,
    ...(synthResult.answer ? { text: synthResult.answer } : {}),
    ...(synthResult.error ? { error: synthResult.error } : {}),
  };
  return {
    schema: "llmadapter.council",
    schema_version: 1,
    status: synthResult.ok ? "ok" : "partial",
    exit_code: synthResult.ok ? 0 : 1,
    question_sha256: sha256(prompt),
    synth_lane: synthLane.name,
    workers,
    synthesis,
  };
}

// ------------------------------------------------------------- cache export
// The llmadapter cache stays where it is: private 0600 files under
// ~/.agent-token-saver. This exports a snapshot for replay/analysis, optionally
// into DuckDB. Answers are hashed unless --with-answers is passed explicitly.
function cacheExport(outPath: string, withAnswers: boolean): { rows: number; bytes: number } {
  const rows: string[] = [];
  if (existsSync(CACHE_DIR)) {
    for (const name of readdirSync(CACHE_DIR)) {
      const file = join(CACHE_DIR, name);
      try {
        if (lstatSync(file).isSymbolicLink() || !lstatSync(file).isFile()) continue;
        const saved = JSON.parse(readFileSync(file, "utf8"));
        if (saved?.schema !== "llmadapter.cache") continue;
        rows.push(JSON.stringify({
          lane: saved.lane,
          model: saved.model ?? null,
          max_tokens: saved.max_tokens,
          prompt_sha256: saved.prompt_sha256,
          capsule_sha256: saved.capsule_sha256,
          capsule_version: saved.capsule_version,
          ts: saved.ts,
          answer_sha256: sha256(String(saved.answer ?? "")),
          answer_bytes: Buffer.byteLength(String(saved.answer ?? ""), "utf8"),
          ...(withAnswers ? { answer: saved.answer } : {}),
        }));
      } catch {
        // A corrupt cache entry is skipped, never fatal.
      }
    }
  }
  const payload = rows.length ? `${rows.join("\n")}\n` : "";
  mkdirSync(dirname(outPath), { recursive: true, mode: 0o700 });
  writeFileSync(outPath, payload, { mode: 0o600 });
  chmodSync(outPath, 0o600);
  return { rows: rows.length, bytes: Buffer.byteLength(payload, "utf8") };
}

// ---- CLI ----
const args = process.argv.slice(2);
const cmd = args[0];
const flag = (name: string, def?: string) => {
  const i = args.indexOf(`--${name}`);
  return i >= 0 ? (args[i + 1]?.startsWith("--") ? "true" : (args[i + 1] ?? "true")) : def;
};

if (cmd === "ask-v2") {
  let output: AskV2Output;
  try {
    output = await askV2(args.slice(1));
  } catch (error: any) {
    output = emptyAskV2Output(
      error instanceof V2UsageError ? error.message : "internal_error",
      error instanceof V2UsageError ? 64 : 70,
    );
  }
  console.log(JSON.stringify(output));
  process.exit(output.exit_code);
} else if (cmd === "evidence") {
  // Gather only. No lane runs, no model token is spent: this is the
  // "gather once, reference N times" primitive a controller needs before it
  // fans out. The artifact goes to a private file; stdout carries the report.
  const mode = flag("mode", "research")!;
  if (!["research", "mega", "fetch", "primary"].includes(mode)) {
    console.error("usage: llmadapter evidence [--mode research|mega|fetch|primary] (--target X | --stdin) [--bytes N] [--out PATH] [--no-cache]");
    process.exit(64);
  }
  const target = args.includes("--stdin")
    ? new TextDecoder().decode(readPromptFdV2(0)).trim()
    : flag("target");
  if (!target || target === "true") {
    console.error("evidence needs --target \"<query|url>\" or --stdin");
    process.exit(64);
  }
  const bytes = Number(flag("bytes", String(EVIDENCE_DEFAULT_BYTES)));
  if (!Number.isSafeInteger(bytes) || bytes < 1 || bytes > EVIDENCE_MAX_BYTES) {
    console.error(`--bytes must be 1..${EVIDENCE_MAX_BYTES}`);
    process.exit(64);
  }
  const block = await gatherEvidence(
    target,
    mode as "research" | "mega" | "fetch" | "primary",
    target,
    bytes,
    !args.includes("--no-cache"),
  );
  const out = flag("out");
  let artifact: string | null = null;
  if (out && out !== "true" && block.usable) {
    try {
      atomicPrivateText(out, `${block.text}\n`);
      artifact = out;
    } catch (error: any) {
      console.error(`evidence artifact not written: ${boundedDetail(String(error?.message ?? "write_failed"))}`);
    }
  }
  const report = {
    schema: "llmadapter.evidence",
    schema_version: 1,
    mode,
    target_sha256: sha256(target),
    usable: block.usable,
    cached: block.cached,
    bytes: Buffer.byteLength(block.text, "utf8"),
    source: block.source,
    sha256: block.sha256,
    ...(block.note ? { note: block.note } : {}),
    artifact,
    model_tokens_spent: 0,
  };
  console.log(JSON.stringify(report, null, 1));
  process.exit(block.usable ? 0 : 1);
} else if (cmd === "council") {
  let output: CouncilOutput;
  try {
    output = await councilRun(args.slice(1));
  } catch (error: any) {
    const detail = error instanceof V2UsageError ? error.message : "internal_error";
    output = {
      schema: "llmadapter.council",
      schema_version: 1,
      status: "invalid",
      exit_code: error instanceof V2UsageError ? 64 : 70,
      question_sha256: sha256(""),
      synth_lane: "none",
      workers: emptyAskV2Output(detail, error instanceof V2UsageError ? 64 : 70),
      synthesis: null,
      error: boundedDetail(detail),
    };
  }
  console.log(JSON.stringify(output));
  process.exit(output.exit_code);
} else if (cmd === "cache-export") {
  const out = flag("out");
  if (!out) {
    console.error("usage: llmadapter cache-export --out PATH.jsonl [--with-answers] [--duckdb PATH]");
    process.exit(64);
  }
  const summary = cacheExport(out, args.includes("--with-answers"));
  const duckdb = flag("duckdb");
  let loaded = false;
  if (duckdb && duckdb !== "true") {
    if (!Bun.which("duckdb")) {
      console.error("duckdb not on PATH; JSONL snapshot was still written");
    } else if (summary.rows > 0) {
      const load = Bun.spawnSync([
        "duckdb",
        duckdb,
        "-c",
        `CREATE OR REPLACE TABLE llmadapter_cache AS SELECT * FROM read_json_auto('${out.replace(/'/g, "''")}');`,
      ], { stdout: "ignore", stderr: "ignore" });
      loaded = load.exitCode === 0;
    }
  }
  console.log(JSON.stringify({
    schema: "llmadapter.cache_export",
    schema_version: 1,
    out,
    rows: summary.rows,
    bytes: summary.bytes,
    answers_included: args.includes("--with-answers"),
    duckdb: duckdb && duckdb !== "true" ? duckdb : null,
    duckdb_loaded: loaded,
  }, null, 1));
} else if (cmd === "lanes") {
  for (const l of LANES) {
    const tier = l.cheap ? "cheap" : l.class;
    const price = l.usdOut === undefined ? "" : `  $${l.usdOut.toFixed(2)}/Mout`;
    console.log(`${tier.padEnd(5)} ${l.name.padEnd(42)} ${l.model ?? l.cmd!("…").join(" ").slice(0, 50)}${price}${l.serial ? "  [serial]" : ""}`);
  }
  const cheap = LANES.filter((l) => l.cheap).length;
  console.log(`total: ${LANES.length} lanes · \`cheap\` selects ${cheap} paid lanes under $0.60/Mout (needs --allow-paid)`);
} else if (cmd === "doctor") {
  for (const l of LANES.filter((x) => x.kind === "cli")) {
    const bin = l.cmd!("x")[0];
    console.log(`${Bun.which(bin) ? "ok " : "MISS"} ${l.name.padEnd(14)} ${bin}`);
  }
  console.log(`${(() => { try { orKey(); return "ok "; } catch { return "MISS"; } })()} openrouter-key`);
  // A model id that quietly leaves the catalog only fails at call time, inside
  // a swarm, as a generic provider error. `laguna-m.1` sat dead in the lane
  // table until 2026-08-01 for exactly that reason. Name it here instead.
  try {
    const catalog: any = await (await fetch("https://openrouter.ai/api/v1/models", {
      signal: AbortSignal.timeout(15_000),
    })).json();
    const ids = new Set<string>((catalog.data ?? []).map((m: any) => m.id));
    const remote = LANES.filter((l) => l.kind === "openrouter" && l.model);
    const dead = remote.filter((l) => !ids.has(l.model!));
    console.log(
      `${dead.length === 0 ? "ok " : "MISS"} openrouter models ${remote.length - dead.length}/${remote.length} in catalog`
      + (dead.length ? ` — gone: ${dead.map((l) => l.model).join(", ")}` : ""),
    );
  } catch {
    console.log("MISS openrouter catalog (unreachable; model ids unverified)");
  }
  // Catalog presence is not availability: `google/gemma-4-31b-it:free` sat in
  // the catalog on 2026-08-01 while every free call to it returned "Provider
  // returned error". `--probe` spends one 32-token call per free lane to say
  // which lanes actually answer today. Opt-in, because plain doctor is a
  // filesystem check that must stay instant and free. 32 and not 4: a lane that
  // opens with a short preamble is alive, and a 4-token ceiling would report it
  // as empty.
  if (flag("probe") === "true") {
    console.log("--- live probe (one 32-token call per free lane, single sample) ---");
    const probes = await Promise.all(
      LANES.filter((l) => l.kind === "openrouter" && l.class === "free").map(async (l) => {
        const r = await runLane(l, "Reply with the single character: 1", 45_000, false, 32);
        return `${r.ok ? "ok " : "FAIL"} ${l.name.padEnd(40)} ${r.ok ? `${r.ms}ms` : (r.detail ?? r.error ?? "").slice(0, 60)}`;
      }),
    );
    for (const line of probes) console.log(line);
  }
  // The order a class selector will actually use, so "why did my swarm pick
  // those three lanes" has an answer that does not require reading the ledger.
  const health = laneHealth();
  if (health.size > 0) {
    const ranked = pickLanes("free").slice(0, SWARM_MAX_WORKERS);
    console.log(
      `ok  lane health from ledger (${health.size} lanes, ${LANE_HEALTH_WINDOW_MS / 86_400_000}d) `
      + `— \`--lanes free\` runs: ${ranked.map((l) => l.name).join(", ")}`,
    );
  } else {
    console.log("ok  lane health: no ledger records yet, class selectors use table order");
  }
  try {
    await fetch("http://localhost:11434/api/tags", { signal: AbortSignal.timeout(1500) });
    console.log("ok  ollama :11434");
  } catch {
    console.log("MISS ollama :11434");
  }
  // Optional integrations: absent means the matching flag stays off, never an error.
  for (const [label, present] of [
    ["evidence provider (LLMADAPTER_EVIDENCE_CMD)", Boolean(EVIDENCE_CMD && existsSync(EVIDENCE_CMD))],
    ["si (--skill-route)", Boolean(Bun.which("si"))],
    ["ats-url-cache", Boolean(Bun.which("ats-url-cache"))],
    ["duckdb (cache-export)", Boolean(Bun.which("duckdb"))],
  ] as [string, boolean][]) {
    console.log(`${present ? "ok " : "MISS"} ${label}`);
  }
} else if (cmd === "stats") {
  const month = new Date().toISOString().slice(0, 7).replace("-", "");
  const lp = join(LEDGER_DIR, `llmadapter-${month}.jsonl`);
  if (!existsSync(lp)) { console.log(`Kein Ledger für ${month} (${lp})`); process.exit(0); }
  const rows = readFileSync(lp, "utf8").trim().split("\n").map((l) => JSON.parse(l));
  const byLane = new Map<string, { calls: number; ok: number; cached: number; inT: number; outT: number; ms: number }>();
  for (const r of rows) {
    const s = byLane.get(r.lane) ?? { calls: 0, ok: 0, cached: 0, inT: 0, outT: 0, ms: 0 };
    s.calls++; if (r.ok) s.ok++; if (r.cached) s.cached++;
    s.inT += r.in_tokens ?? 0; s.outT += r.out_tokens ?? 0; s.ms += r.ms ?? 0;
    byLane.set(r.lane, s);
  }
  console.log("lane                                     calls  ok  cache    in-tok   out-tok   avg-ms");
  for (const [lane, s] of [...byLane].sort((a, b) => b[1].calls - a[1].calls))
    console.log(`${lane.padEnd(40)} ${String(s.calls).padStart(5)} ${String(s.ok).padStart(3)} ${String(s.cached).padStart(6)} ${String(s.inT).padStart(9)} ${String(s.outT).padStart(9)} ${String(Math.round(s.ms / s.calls)).padStart(8)}`);
  const t = [...byLane.values()].reduce((a, s) => ({ calls: a.calls + s.calls, ok: a.ok + s.ok, cached: a.cached + s.cached, inT: a.inT + s.inT, outT: a.outT + s.outT }), { calls: 0, ok: 0, cached: 0, inT: 0, outT: 0 });
  console.log(`total: ${t.calls} calls · ${t.ok} ok · ${t.cached} cache-hits · ${t.inT + t.outT} tokens (Monat ${month})`);
} else if (cmd === "contract") {
  const objective = args.slice(1).find((a) => !a.startsWith("--"));
  if (!objective) {
    console.error("usage: llmadapter contract \"<worker objective>\"");
    process.exit(1);
  }
  const packet = workerCapsule(
    objective,
    SWARM_MAX_RESULT_TOKENS,
    false,
  );
  // AgentMaster parses this with deny_unknown_fields. The default shape is the
  // capability contract and must not grow; --extended is for humans and for
  // controllers that opt into the newer flags.
  const contract: Record<string, unknown> = {
    schema_version: 2,
    ask_v2: true,
    mode: "swarm",
    default_max_workers: SWARM_MAX_WORKERS,
    max_workers: SWARM_MAX_WORKERS,
    fanout_max_workers: SWARM_FANOUT_MAX_WORKERS,
    max_result_tokens: SWARM_MAX_RESULT_TOKENS,
    max_result_tokens_semantics: "requested_ceiling_by_capability",
    max_prompt_bytes: V2_MAX_PROMPT_BYTES,
    tools_available: false,
    capsule_visible_input_tokens_proxy: Math.ceil(Buffer.byteLength(packet, "utf8") / 4),
    route: routeWorkerTool(objective)?.name ?? "none",
    packet,
  };
  if (args.includes("--extended")) {
    contract.extensions = {
      first_pass: true,
      oracle: true,
      budget_tokens: true,
      evidence: ["research", "mega", "fetch", "primary"],
      evidence_max_bytes: EVIDENCE_MAX_BYTES,
      evidence_provider: Boolean(EVIDENCE_CMD && existsSync(EVIDENCE_CMD)),
      skill_route: Boolean(Bun.which("si")),
      council: true,
      opt_in_lanes: LANES.filter((l) => l.optIn).map((l) => l.name),
      terminal_values_extended: ["pruned"],
      note: "Extensions are off unless their flag is passed; the default envelope is unchanged.",
    };
  }
  console.log(JSON.stringify(contract, null, 1));
} else if (cmd === "ask") {
  const prompt = args.slice(1).find((a) => !a.startsWith("--") && a !== flag(a.replace(/^--/, "")))!;
  if (!prompt) { console.error("usage: llmadapter ask \"<prompt>\" [--swarm] [--fanout] [--lanes free|cheap|paid|local|cli|all|name,…] [--first N] [--tier] [--aggregate] [--verify] [--json] [--no-cache] [--usage-out PATH]"); process.exit(1); }
  // --tier: cheap proposers → strong aggregate → fresh verify (one flag).
  const tier = args.includes("--tier");
  const swarm = args.includes("--swarm");
  const fanout = args.includes("--fanout");
  if (fanout && !swarm) {
    console.error("--fanout only applies to --swarm; plain ask already keeps its requested lane set.");
    process.exit(1);
  }
  const requestedLanes = tier
    ? LANES.filter((l) => TIER_PROPOSERS.includes(l.name))
    : pickLanes(flag("lanes", "free")!);
  const lanes = swarm ? boundedSwarmLanes(requestedLanes, fanout) : requestedLanes;
  if (swarm && !fanout && requestedLanes.length > lanes.length) {
    console.error(`· swarm mode: using ${lanes.length}/${requestedLanes.length} lanes (pass --fanout only for an explicit wide benchmark)`);
  }
  if (swarm && tier) {
    console.error("--tier is a controller workflow and cannot be combined with --swarm; use --aggregate/--verify after bounded workers instead.");
    process.exit(1);
  }
  if (!lanes.length) {
    console.error("No lanes matched --lanes.");
    process.exit(1);
  }
  const workerPrompt = swarm ? workerCapsule(prompt) : prompt;
  const timeoutMs = flag("timeout") ? Number(flag("timeout")) * 1000 : undefined;
  const cap = Number(flag("cap", "12"));
  const requestedMaxTokens = Number(flag("max-tokens", "2048"));
  const maxTokens = swarm
    ? Math.min(requestedMaxTokens, SWARM_MAX_RESULT_TOKENS)
    : requestedMaxTokens;
  if (swarm && requestedMaxTokens > maxTokens) {
    console.error(`· swarm mode: provider output cap ${maxTokens} tokens`);
  }
  const first = flag("first") ? Number(flag("first")) : undefined;
  const useCache = !args.includes("--no-cache");
  const t0 = Date.now();
  const serialLanes = lanes.filter((l) => l.serial);
  const parallelLanes = lanes.filter((l) => !l.serial);
  const thunks = parallelLanes.map((l) => () => runLane(l, workerPrompt, timeoutMs, useCache, maxTokens));
  const results = first ? await race(thunks, cap, first) : await pool(thunks, cap);
  if (!first || results.filter((r) => r.ok).length < first)
    for (const l of serialLanes) results.push(await runLane(l, workerPrompt, timeoutMs, useCache, maxTokens)); // single-flight lanes last, one at a time
  const ok = results.filter((r) => r.ok);
  const up = flag("usage-out");
  if (up) usageOut(up, results);
  if (args.includes("--json")) {
    console.log(JSON.stringify({ prompt, wall_ms: Date.now() - t0, ok: ok.length, total: results.length, results }, null, 1));
  } else {
    for (const r of results) console.log(r.ok ? `✅ ${r.lane} (${r.ms}ms${r.cached ? ", cache" : ""}${r.est ? ", est" : ""}): ${r.answer!.replace(/\n/g, " ").slice(0, 200)}` : `❌ ${r.lane}: ${r.error} ${r.detail ?? ""}`);
    console.log(`\n${ok.length}/${results.length} ok · wall ${((Date.now() - t0) / 1000).toFixed(1)}s${first ? ` · race first=${first}` : ""}`);
  }
  // Final answer: aggregate when asked (or in --tier), else the best single.
  let finalAnswer = ok.length ? ok[0].answer! : "";
  if ((args.includes("--aggregate") || tier) && ok.length > 1) {
    finalAnswer = await aggregate(prompt, results, maxTokens);
    console.log(`\n— Aggregat (${LANES[0].name}) —\n${finalAnswer}`);
  }
  // --verify (implied by --tier): a fresh strong lane checks the final answer.
  if ((args.includes("--verify") || tier) && finalAnswer) {
    const v = await verify(prompt, finalAnswer, maxTokens);
    console.log(`\n— Verify (${v.ok ? "✓ VERIFIED" : "⚠ CORRECTION"}) —\n${v.text}`);
  }
  process.exit(0); // race mode may have stragglers; exiting kills them deliberately
} else {
  console.log([
    "llmadapter — one interface over the built-in lanes plus host-local additions",
    "",
    "  ask-v2 (--stdin|--prompt-file PATH) --swarm [--lanes …] [--cap N] [--max-tokens N]",
    "         [--deadline-secs N] [--usage-out PATH] [--allow-remote] [--allow-paid] [--no-cache]",
    "         [--first-pass] [--oracle 'CMD'] [--oracle-env-prefix NAME] [--budget-tokens N]",
    "         [--evidence [--evidence-mode research|mega|fetch|primary] [--evidence-target X] [--evidence-bytes N]]",
    "         [--skill-route]",
    "  evidence [--mode research|mega|fetch|primary] (--target X | --stdin) [--bytes N] [--out PATH]",
    "  council (--stdin|--prompt-file PATH) [--synth-lane NAME] + every ask-v2 flag",
    "  ask \"<prompt>\" [--swarm] [--fanout] [--lanes …] [--first N] [--aggregate] [--verify] [--tier] [--json]",
    "  contract \"<worker objective>\" [--extended]",
    "  cache-export --out PATH.jsonl [--with-answers] [--duckdb PATH]",
    "  lanes | doctor [--probe] | stats",
    "",
    "  --oracle: exit 0 = PASS. Gets LLMADAPTER_ANSWER_PATH + LLMADAPTER_RUN_DIR;",
    "            --oracle-env-prefix NAME also exports NAME_ANSWER_PATH/NAME_RUN_DIR",
    "            so a controller's existing oracle string keeps working.",
    "  --first-pass: all lanes start, first PASS wins, the rest are pruned.",
    "  --evidence: $LLMADAPTER_EVIDENCE_CMD supplies the fresh fact tool-less lanes cite.",
    "  host lanes marked opt_in stay out of `all`/class selectors; name them in --lanes.",
  ].join("\n"));
}
