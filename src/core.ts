import { openSync, closeSync, fstatSync, readSync, mkdirSync, mkdtempSync } from "node:fs";
import { join, resolve } from "node:path";

export function object(value: unknown): Record<string, unknown> {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    throw new Error("Expected a JSON object");
  }
  return value as Record<string, unknown>;
}

export function count(value: unknown, name: string): number {
  if (typeof value !== "number" || !Number.isFinite(value) || value < 0) {
    throw new Error(`${name} must be a finite nonnegative number`);
  }
  return value;
}

export function positiveInteger(value: string, name: string): number {
  const result = Number(value);
  if (!Number.isSafeInteger(result) || result <= 0) throw new Error(`${name} must be a positive integer`);
  return result;
}

export function costReport(input: unknown) {
  const row = object(input);
  const usage = object(row.usage);
  const prices = object(row.prices_per_million);
  if (typeof row.currency !== "string" || !row.currency.trim() ||
      typeof row.price_source !== "string" || !row.price_source.trim()) {
    throw new Error("currency and price_source are required; ATS has no implicit current prices");
  }
  const keys = ["fresh_input", "cache_read", "cache_write", "output"] as const;
  const parts = Object.fromEntries(keys.map(key => {
    const tokens = count(usage[key], `usage.${key}`);
    if (!Number.isSafeInteger(tokens)) throw new Error(`usage.${key} must be an integer`);
    return [key, tokens * count(prices[key], `prices_per_million.${key}`) / 1_000_000];
  }));
  const total = Object.values(parts).reduce((a, b) => a + b, 0);
  if (!Number.isFinite(total)) throw new Error("Cost exceeds numeric range");
  return {
    kind: "supplied-price-estimate", currency: row.currency,
    price_source: row.price_source, parts, total,
    invoice: false,
    note: "Usage classes must be disjoint; normalize provider counters before comparison.",
  };
}

// Bound model-facing output without loading the complete artifact into memory.
export function tail(path: string, maxBytes = 16_384) {
  const fd = openSync(path, "r");
  try {
    const bytes = fstatSync(fd).size;
    const start = Math.max(0, bytes - maxBytes);
    const buffer = Buffer.alloc(Math.min(bytes, maxBytes));
    const read = readSync(fd, buffer, 0, buffer.length, start);
    const text = buffer.subarray(0, read).toString("utf8");
    return { bytes, omitted_bytes: start, text };
  } finally { closeSync(fd); }
}

export async function verify(command: string[], options: { directory: string; timeoutMs: number }) {
  if (!command.length) throw new Error("verify requires -- followed by a command");
  if (!Number.isSafeInteger(options.timeoutMs) || options.timeoutMs <= 0 || options.timeoutMs > 2_147_483_647) {
    throw new Error("timeout-ms must be an integer between 1 and 2147483647");
  }
  const directory = resolve(options.directory);
  mkdirSync(directory, { recursive: true, mode: 0o700 });
  const run = mkdtempSync(join(directory, "run-"));
  const stdoutPath = join(run, "stdout.log");
  const stderrPath = join(run, "stderr.log");
  const stdout = openSync(stdoutPath, "wx", 0o600);
  const stderr = openSync(stderrPath, "wx", 0o600);
  const started = performance.now();
  let exitCode = 127;
  let spawnError: string | null = null;
  let signal: string | null = null;
  let timedOut = false;
  try {
    // No shell interpolation, filter process or second invocation of the command.
    const child = Bun.spawn(command, { stdin: "ignore", stdout, stderr });
    const timer = setTimeout(() => { timedOut = true; child.kill("SIGKILL"); }, options.timeoutMs);
    try {
      const result = await child.exited;
      signal = child.signalCode === null ? null : String(child.signalCode);
      exitCode = timedOut ? 124 : result;
    } finally { clearTimeout(timer); }
  } catch (error) {
    spawnError = error instanceof Error ? error.message : String(error);
  } finally {
    closeSync(stdout);
    closeSync(stderr);
  }
  const out = tail(stdoutPath);
  const err = tail(stderrPath);
  const result = {
    schema: 1, passed: exitCode === 0 && spawnError === null && !timedOut,
    exit_code: exitCode, signal, timed_out: timedOut, spawn_error: spawnError,
    elapsed_ms: Math.round(performance.now() - started),
    stdout: { path: stdoutPath, bytes: out.bytes },
    stderr: { path: stderrPath, bytes: err.bytes },
    evidence: exitCode === 0 ? null : {
      kind: "tail-only", stdout: out, stderr: err,
      note: "Partial diagnostic view. Complete logs are the evidence; no failure-completeness claim.",
    },
  };
  await Bun.write(join(run, "result.json"), JSON.stringify(result, null, 2));
  return result;
}
