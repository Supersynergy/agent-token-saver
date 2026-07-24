#!/usr/bin/env bun
// llmadapter — one interface over every lane: OpenRouter, Ollama, CLI agents.
// Born from the 23-lane burst test 2026-07-24. Lanes carry their own quirks
// (some CLI lanes are single-flight or rate-limited) so callers do not have to.
// Integrates with agent-token-saver: per-call JSONL ledger + hermes-style
// usage files consumable by `agent-token-ledger --usage llmadapter=FILE`.

import { createHash } from "node:crypto";
import { appendFileSync, existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

type Lane = {
  name: string;
  kind: "openrouter" | "ollama" | "cli";
  class: "free" | "paid" | "local" | "cli";
  model?: string;
  cmd?: (prompt: string) => string[];
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
  { name: "codex", kind: "cli", class: "cli", cmd: (p) => ["codex", "exec", "--skip-git-repo-check", p] },
  { name: "agy", kind: "cli", class: "cli", cmd: (p) => ["agy", "-p", p, "--dangerously-skip-permissions"] },
  { name: "ggcoder", kind: "cli", class: "cli", cmd: (p) => ["ggcoder", "--json", p], parse: ggcoderText },
  { name: "claude-haiku", kind: "cli", class: "cli", cmd: (p) => ["claude", "-p", "--model", "haiku", p] },
];

// Local-only extra lanes live OUTSIDE this repo in
// ~/.agent-token-saver/local-lanes.json so they are usable locally but never
// committed or deployed. Each has a cmd array with a "__PROMPT__" placeholder.
try {
  const lp = join(homedir(), ".agent-token-saver", "local-lanes.json");
  if (existsSync(lp)) {
    const extra = JSON.parse(readFileSync(lp, "utf8")).llmadapter ?? [];
    for (const l of extra) {
      const tmpl: string[] = l.cmd;
      LANES.push({
        name: l.name, kind: l.kind ?? "cli", class: l.class ?? "cli", serial: l.serial,
        cmd: (p: string) => tmpl.map((x) => (x === "__PROMPT__" ? p : x)),
      });
    }
  }
} catch { /* fail-open: no local lanes */ }

const ATS_DIR = join(homedir(), ".agent-token-saver");
const CACHE_DIR = join(ATS_DIR, "cache", "llmadapter");
const LEDGER_DIR = join(ATS_DIR, "ledger");
const CACHE_TTL_MS = 24 * 3600 * 1000;
const KIND_TIMEOUT_MS: Record<Lane["kind"], number> = { openrouter: 90_000, ollama: 120_000, cli: 170_000 };

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
    let answer = "";
    let inTok: number | undefined, outTok: number | undefined, est = false;
    if (lane.kind === "openrouter") {
      let lastMsg = "";
      for (let attempt = 0; attempt < 2; attempt++) {
        if (attempt > 0) await sleep(/429|rate.?limit/i.test(lastMsg) ? 5000 : 2000 + Math.random() * 1000);
        const res = await fetch("https://openrouter.ai/api/v1/chat/completions", {
          method: "POST",
          headers: { Authorization: `Bearer ${orKey()}`, "Content-Type": "application/json" },
          body: JSON.stringify({ model: lane.model, max_tokens: maxTokens, messages: [{ role: "user", content: prompt }] }),
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
      const res = await fetch("http://localhost:11434/api/generate", {
        method: "POST",
        body: JSON.stringify({ model: lane.model, prompt, stream: false }),
        signal: AbortSignal.timeout(tmo),
      });
      const j: any = await res.json();
      answer = j.response ?? "";
      inTok = j.prompt_eval_count;
      outTok = j.eval_count;
    } else {
      const proc = Bun.spawn(lane.cmd!(prompt), { stdout: "pipe", stderr: "pipe", stdin: "ignore" });
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
      inTok = Math.round(prompt.length / 4); // ats convention: bytes/4 estimate
      outTok = Math.round(answer.length / 4);
      est = true;
    }
    const ms = Date.now() - t0;
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

// ---- CLI ----
const args = process.argv.slice(2);
const cmd = args[0];
const flag = (name: string, def?: string) => {
  const i = args.indexOf(`--${name}`);
  return i >= 0 ? (args[i + 1]?.startsWith("--") ? "true" : (args[i + 1] ?? "true")) : def;
};

if (cmd === "lanes") {
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
} else if (cmd === "ask") {
  const prompt = args.slice(1).find((a) => !a.startsWith("--") && a !== flag(a.replace(/^--/, "")))!;
  if (!prompt) { console.error("usage: llmadapter ask \"<prompt>\" [--lanes free|paid|local|cli|all|name,…] [--first N] [--tier] [--aggregate] [--verify] [--json] [--no-cache] [--usage-out PATH]"); process.exit(1); }
  // --tier: cheap proposers → strong aggregate → fresh verify (one flag).
  const tier = args.includes("--tier");
  const lanes = tier
    ? LANES.filter((l) => TIER_PROPOSERS.includes(l.name))
    : pickLanes(flag("lanes", "free")!);
  const timeoutMs = flag("timeout") ? Number(flag("timeout")) * 1000 : undefined;
  const cap = Number(flag("cap", "12"));
  const maxTokens = Number(flag("max-tokens", "2048"));
  const first = flag("first") ? Number(flag("first")) : undefined;
  const useCache = !args.includes("--no-cache");
  const t0 = Date.now();
  const serialLanes = lanes.filter((l) => l.serial);
  const parallelLanes = lanes.filter((l) => !l.serial);
  const thunks = parallelLanes.map((l) => () => runLane(l, prompt, timeoutMs, useCache, maxTokens));
  const results = first ? await race(thunks, cap, first) : await pool(thunks, cap);
  if (!first || results.filter((r) => r.ok).length < first)
    for (const l of serialLanes) results.push(await runLane(l, prompt, timeoutMs, useCache, maxTokens)); // single-flight lanes last, one at a time
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
  console.log("llmadapter — one interface over all 23 lanes\n  ask \"<prompt>\" [--lanes …] [--first N] [--aggregate] [--json] [--usage-out PATH]\n  lanes\n  doctor\n  stats");
}
