// Hyperstack: 4-stage escalation chain for extreme token savings
// curl_cffi -> camoufox -> domshell -> agent-browser (fallback)
// Each stage fails-forward only on block/JS-requirement.

import { spawn } from "node:child_process";
import { readFile, writeFile, mkdir } from "node:fs/promises";
import { createHash } from "node:crypto";
import { homedir } from "node:os";
import { join } from "node:path";

export type Stage = "curl_cffi" | "camoufox" | "domshell" | "browser";

export interface FetchResult {
  stage: Stage;
  status: number;
  url: string;
  bytes: number;
  latencyMs: number;
  contentHash: string;
  sandboxKey: string;
  summary?: string;
  tokenEstimate: number;
}

export interface HyperstackConfig {
  maxStage: Stage;
  useMlFilter: boolean;
  useGemmaGate: boolean;
  gemmaThresholdTokens: number;
  teamSandbox: boolean;
  teamNamespace: string;
}

const DEFAULT_CONFIG: HyperstackConfig = {
  maxStage: "browser",
  useMlFilter: true,
  useGemmaGate: true,
  gemmaThresholdTokens: 500,
  teamSandbox: false,
  teamNamespace: "default",
};

const CACHE_DIR = join(homedir(), ".cts", "hyperstack");
const PATCHES = join(homedir(), "patches");
const DOMSHELL = join(homedir(), "projects", "browser-tools", "domshell-lite.py");

function sha1(s: string): string {
  return createHash("sha1").update(s).digest("hex").slice(0, 16);
}

function estimateTokens(bytes: number): number {
  return Math.ceil(bytes / 3.5);
}

async function runPy(script: string, args: string[], timeoutMs = 30000): Promise<{ code: number; stdout: string; stderr: string }> {
  return new Promise((resolve) => {
    const child = spawn("uv", ["run", "python", script, ...args], { stdio: ["ignore", "pipe", "pipe"] });
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (c) => (stdout += c));
    child.stderr.on("data", (c) => (stderr += c));
    const timer = setTimeout(() => child.kill("SIGKILL"), timeoutMs);
    child.on("close", (code) => {
      clearTimeout(timer);
      resolve({ code: code ?? 1, stdout, stderr });
    });
  });
}

async function ensureCache(): Promise<void> {
  await mkdir(CACHE_DIR, { recursive: true });
}

async function checkTeamCache(url: string, ns: string): Promise<FetchResult | null> {
  const key = sha1(`${ns}:${url}`);
  try {
    const raw = await readFile(join(CACHE_DIR, `${key}.json`), "utf8");
    const cached = JSON.parse(raw) as FetchResult;
    const ageMs = Date.now() - (cached as any).cachedAt;
    if (ageMs < 3600_000) return cached;
  } catch {}
  return null;
}

async function writeTeamCache(url: string, ns: string, result: FetchResult): Promise<void> {
  const key = sha1(`${ns}:${url}`);
  const payload = { ...result, cachedAt: Date.now() };
  await writeFile(join(CACHE_DIR, `${key}.json`), JSON.stringify(payload));
}

async function stageCurlCffi(url: string): Promise<FetchResult | null> {
  const t0 = Date.now();
  const r = await runPy(join(PATCHES, "curl_cffi_patch.py"), ["--fetch", url], 15000);
  if (r.code !== 0) return null;
  try {
    const parsed = JSON.parse(r.stdout);
    if (parsed.status >= 400 || parsed.blocked) return null;
    const bytes = parsed.body?.length ?? 0;
    return {
      stage: "curl_cffi",
      status: parsed.status,
      url,
      bytes,
      latencyMs: Date.now() - t0,
      contentHash: sha1(parsed.body ?? ""),
      sandboxKey: "",
      tokenEstimate: estimateTokens(bytes),
    };
  } catch {
    return null;
  }
}

async function stageCamoufox(url: string): Promise<FetchResult | null> {
  const t0 = Date.now();
  const r = await runPy(join(PATCHES, "camoufox_patch.py"), ["--fetch", url], 45000);
  if (r.code !== 0) return null;
  try {
    const parsed = JSON.parse(r.stdout);
    const bytes = parsed.body?.length ?? 0;
    return {
      stage: "camoufox",
      status: parsed.status ?? 200,
      url,
      bytes,
      latencyMs: Date.now() - t0,
      contentHash: sha1(parsed.body ?? ""),
      sandboxKey: "",
      tokenEstimate: estimateTokens(bytes),
    };
  } catch {
    return null;
  }
}

async function stageDomshell(url: string, selector: string = "body"): Promise<FetchResult | null> {
  const t0 = Date.now();
  const r = await runPy(DOMSHELL, ["--url", url, "--select", selector], 30000);
  if (r.code !== 0) return null;
  const bytes = r.stdout.length;
  return {
    stage: "domshell",
    status: 200,
    url,
    bytes,
    latencyMs: Date.now() - t0,
    contentHash: sha1(r.stdout),
    sandboxKey: "",
    tokenEstimate: estimateTokens(bytes),
  };
}

async function stageBrowser(url: string): Promise<FetchResult | null> {
  const t0 = Date.now();
  const r = await runPy(join(PATCHES, "camoufox_patch.py"), ["--snapshot", url, "--interactive-only"], 60000);
  if (r.code !== 0) return null;
  const bytes = r.stdout.length;
  return {
    stage: "browser",
    status: 200,
    url,
    bytes,
    latencyMs: Date.now() - t0,
    contentHash: sha1(r.stdout),
    sandboxKey: "",
    tokenEstimate: estimateTokens(bytes),
  };
}

async function mlFilter(content: string): Promise<{ keep: boolean; category: string; confidence: number }> {
  const r = await runPy(join(homedir(), "agent-token-saver", "core", "ml-filter.py"), ["--classify"], 5000);
  try {
    return JSON.parse(r.stdout);
  } catch {
    return { keep: true, category: "unknown", confidence: 0 };
  }
}

async function gemmaGate(content: string, thresholdTokens: number): Promise<string | null> {
  if (estimateTokens(content.length) < thresholdTokens) return null;
  const r = await runPy(join(homedir(), "agent-token-saver", "core", "gemma-gate.py"), ["--summarize"], 10000);
  if (r.code !== 0) return null;
  return r.stdout.trim();
}

export async function hyperfetch(url: string, userCfg: Partial<HyperstackConfig> = {}): Promise<FetchResult> {
  const cfg = { ...DEFAULT_CONFIG, ...userCfg };
  await ensureCache();

  if (cfg.teamSandbox) {
    const cached = await checkTeamCache(url, cfg.teamNamespace);
    if (cached) return { ...cached, stage: cached.stage };
  }

  const stages: Array<(u: string) => Promise<FetchResult | null>> = [
    stageCurlCffi,
    stageCamoufox,
    stageDomshell,
    stageBrowser,
  ];
  const stageNames: Stage[] = ["curl_cffi", "camoufox", "domshell", "browser"];
  const maxIdx = stageNames.indexOf(cfg.maxStage);

  let result: FetchResult | null = null;
  for (let i = 0; i <= maxIdx; i++) {
    result = await stages[i](url);
    if (result) break;
  }
  if (!result) throw new Error(`All stages failed for ${url}`);

  if (cfg.useGemmaGate) {
    const summary = await gemmaGate("", cfg.gemmaThresholdTokens);
    if (summary) {
      result.summary = summary;
      result.tokenEstimate = estimateTokens(summary.length);
    }
  }

  result.sandboxKey = sha1(`${cfg.teamNamespace}:${url}:${result.contentHash}`);

  if (cfg.teamSandbox) {
    await writeTeamCache(url, cfg.teamNamespace, result);
  }

  return result;
}

export async function hyperfetchBatch(urls: string[], cfg: Partial<HyperstackConfig> = {}): Promise<FetchResult[]> {
  return Promise.all(urls.map((u) => hyperfetch(u, cfg)));
}
