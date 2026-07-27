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
  parse?: (raw: string) => string;
};

const OR_FREE = [
  "nvidia/nemotron-3-super-120b-a12b:free",
  "nvidia/nemotron-3-ultra-550b-a55b:free",
  "nvidia/nemotron-3-nano-30b-a3b:free",
  "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
  "nvidia/nemotron-nano-9b-v2:free",
  "nvidia/nemotron-nano-12b-v2-vl:free",
  "openai/gpt-oss-20b:free",
  "google/gemma-4-31b-it:free",
  "google/gemma-4-26b-a4b-it:free",
  "inclusionai/ling-3.0-flash:free",
  "cohere/north-mini-code:free",
  "poolside/laguna-m.1:free",
  "poolside/laguna-s-2.1:free",
  "poolside/laguna-xs-2.1:free",
];
const OR_PAID = ["moonshotai/kimi-k3", "moonshotai/kimi-k2.7-code"];

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
  ...OR_FREE.map((m): Lane => ({ name: m.split("/")[1].replace(":free", ""), kind: "openrouter", class: "free", model: m })),
  ...OR_PAID.map((m): Lane => ({ name: m.split("/")[1], kind: "openrouter", class: "paid", model: m })),
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
      });
    }
  }
} catch { /* fail-open: no local lanes */ }

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

function workerCapsule(
  objective: string,
  maxResultTokens = SWARM_MAX_RESULT_TOKENS,
  toolsAvailable = true,
  rejectTruncation = false,
): string {
  const normalizedObjective = objective.trim();
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
  const prefix = [
    `agent-token-saver worker capsule (${V2_CAPSULE_VERSION}).`,
    toolsAvailable
      ? "One closed objective. Do not request or repeat the controller transcript, peer output, or skill catalog. Zero or one routed primary skill. Do not mutate outside the stated objective."
      : "One closed objective. Do not request or repeat the controller transcript or peer output. Reason only from the supplied evidence.",
    "Oracle: report PASS only with direct evidence; otherwise FAIL or BLOCKED. Workers do not chat with peers; the controller may route one targeted handoff.",
    routeHint,
    "Objective:",
  ].join("\n");
  // `join("\n")` below contributes one separator on either side of the
  // objective, so budget both even when the objective is empty.
  const fixedPacket = `${prefix}\n\n${resultContract}`;
  const objectiveBudget = Math.max(
    0,
    SWARM_CAPSULE_MAX_BYTES - Buffer.byteLength(fixedPacket, "utf8"),
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
  return [
    prefix,
    compactObjective,
    resultContract,
  ].join("\n");
}

function boundedSwarmLanes(lanes: Lane[], fanout: boolean): Lane[] {
  return fanout ? lanes : lanes.slice(0, SWARM_MAX_WORKERS);
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
type V2Terminal = "succeeded" | "failed" | "timeout" | "output_limit" | "cached";
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
      for (let attempt = 0; attempt < 2; attempt++) {
        if (attempt > 0) await sleep(/429|rate.?limit/i.test(lastMsg) ? 5000 : 2000 + Math.random() * 1000);
        const res = await fetch(OPENROUTER_URL, {
          method: "POST",
          headers: { Authorization: `Bearer ${orKey()}`, "Content-Type": "application/json" },
          body: JSON.stringify({ model: lane.model, max_tokens: maxTokens, messages: [{ role: "user", content: sent }] }),
          signal: AbortSignal.timeout(tmo),
        });
        const j: any = await res.json();
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
): Promise<{ response: Response; json: any }> {
  const remaining = deadlineAt - Date.now();
  if (remaining <= 0) throw new DOMException("deadline", "TimeoutError");
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), remaining);
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

async function runLaneV2(
  lane: Lane,
  prompt: string,
  promptHash: string,
  deadlineAt: number,
  useCache: boolean,
  maxTokens: number,
  trust: LaneTrustV2,
): Promise<InternalResultV2> {
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
    let answer = "";
    let inputTokens: number | null = null;
    let outputTokens: number | null = null;
    let tokenSource: V2TokenSource = "unknown";
    if (lane.kind === "openrouter") {
      const apiKey = orKey();
      callStarted = true;
      const { response: res, json } = await fetchJsonBounded(OPENROUTER_URL, {
        method: "POST",
        headers: { Authorization: `Bearer ${apiKey}`, "Content-Type": "application/json" },
        body: JSON.stringify({
          model: lane.model,
          max_tokens: maxTokens,
          messages: [{ role: "user", content: sent }],
        }),
      }, deadlineAt);
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
      answer = json.choices?.[0]?.message?.content ?? "";
      inputTokens = Number.isFinite(json.usage?.prompt_tokens) ? json.usage.prompt_tokens : null;
      outputTokens = Number.isFinite(json.usage?.completion_tokens) ? json.usage.completion_tokens : null;
      tokenSource = inputTokens !== null || outputTokens !== null ? "provider_reported" : "unknown";
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
      }, deadlineAt);
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
      const timer = setTimeout(() => {
        killedForDeadline = true;
        kill();
      }, Math.max(1, deadlineAt - Date.now()));
      let stdout = "";
      let stderr = "";
      try {
        [stdout, stderr] = await Promise.all([
          readBoundedStream(proc.stdout, V2_STDOUT_MAX_BYTES, kill),
          readBoundedStream(proc.stderr, V2_STDERR_MAX_BYTES, kill),
        ]);
      } catch (error) {
        kill();
        await proc.exited;
        clearTimeout(timer);
        if (error instanceof V2OutputLimitError) {
          return v2Failure(
            lane,
            maxTokens,
            "output_limit",
            "output_limit",
            Date.now() - t0,
            true,
          );
        }
        throw error;
      }
      const code = await proc.exited;
      clearTimeout(timer);
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

function pickLanes(spec: string): Lane[] {
  if (spec === "all") return LANES;
  const classes = ["free", "paid", "local", "cli"];
  const parts = spec.split(",").map((s) => s.trim());
  return LANES.filter((l) => parts.some((p) => (classes.includes(p) ? l.class === p : l.name === p || l.model === p)));
}

async function aggregate(prompt: string, results: Result[], maxTokens: number): Promise<string> {
  const okR = results.filter((r) => r.ok);
  const body = okR.map((r) => `[${r.lane}]: ${r.answer}`).join("\n");
  const agg = await runLane(LANES[0], // nemotron-super, fastest free quality rung
    `${okR.length} Modelle beantworteten parallel: "${prompt}". Dedupliziere zu den besten unterschiedlichen Punkten, je 1 Zeile deutsch, nach Praxiswert sortiert:\n${body}`,
    undefined, false, maxTokens * 2);
  return agg.ok ? agg.answer! : `(Aggregation fehlgeschlagen: ${agg.error})`;
}

// Fresh-context verifier (Anthropic Fable-5 multi-agent pattern: an
// independent fresh-context verifier beats self-critique). Runs one strong
// lane to check the answer; returns whether it passed + the verifier text.
// The verifier must be INDEPENDENT of the aggregator (LANES[0] = nemotron-super):
// a different model family gives a real cross-check and avoids rate-limiting the
// same lane twice back-to-back. Default gpt-oss-20b; override via env.
const VERIFY_DEFAULT = "gpt-oss-20b";
function strongLane(): Lane {
  const want = process.env.LLMADAPTER_VERIFY_LANE ?? VERIFY_DEFAULT;
  return LANES.find((l) => l.name === want) ?? LANES.find((l) => l.name === "gemma-4-31b-it") ?? LANES[1] ?? LANES[0];
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
  ]);
  const values = new Set([
    "--prompt-file",
    "--lanes",
    "--cap",
    "--max-tokens",
    "--deadline-secs",
    "--usage-out",
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
  const prompt = readPromptV2(options);
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
  const deadlineAt = Date.now() + options.deadlineSecs * 1000;
  const thunks = lanes.map((lane, index) => {
    const workerPrompt = workerCapsule(
      prompt,
      options.maxTokens,
      lane.tools === true,
      true,
    );
    return () => runLaneV2(
      lane,
      workerPrompt,
      promptHash,
      deadlineAt,
      options.useCache,
      options.maxTokens,
      laneTrust[index],
    );
  });
  const results = await pool(thunks, lanes.length);
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
  if (options.usageOut) atomicPrivateJson(options.usageOut, accounting);
  return output;
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
} else if (cmd === "lanes") {
  for (const l of LANES) console.log(`${l.class.padEnd(5)} ${l.name.padEnd(42)} ${l.model ?? l.cmd!("…").join(" ").slice(0, 50)}${l.serial ? "  [serial]" : ""}`);
  console.log(`total: ${LANES.length} lanes`);
} else if (cmd === "doctor") {
  for (const l of LANES.filter((x) => x.kind === "cli")) {
    const bin = l.cmd!("x")[0];
    console.log(`${Bun.which(bin) ? "ok " : "MISS"} ${l.name.padEnd(14)} ${bin}`);
  }
  console.log(`${(() => { try { orKey(); return "ok "; } catch { return "MISS"; } })()} openrouter-key`);
  try {
    await fetch("http://localhost:11434/api/tags", { signal: AbortSignal.timeout(1500) });
    console.log("ok  ollama :11434");
  } catch {
    console.log("MISS ollama :11434");
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
  console.log(JSON.stringify({
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
  }, null, 1));
} else if (cmd === "ask") {
  const prompt = args.slice(1).find((a) => !a.startsWith("--") && a !== flag(a.replace(/^--/, "")))!;
  if (!prompt) { console.error("usage: llmadapter ask \"<prompt>\" [--swarm] [--fanout] [--lanes free|paid|local|cli|all|name,…] [--first N] [--tier] [--aggregate] [--verify] [--json] [--no-cache] [--usage-out PATH]"); process.exit(1); }
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
  console.log("llmadapter — one interface over 21 built-in lanes plus host-local additions\n  ask-v2 (--stdin|--prompt-file PATH) --swarm [--lanes …] [--cap N] [--max-tokens N] [--deadline-secs N] [--usage-out PATH]\n  ask \"<prompt>\" [--swarm] [--fanout] [--lanes …] [--first N] [--aggregate] [--json] [--usage-out PATH]\n  contract \"<worker objective>\"\n  lanes\n  doctor\n  stats");
}
