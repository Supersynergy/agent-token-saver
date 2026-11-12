import { mkdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { createHash } from "node:crypto";

export type FilterOutcome = {
  status: "applied" | "rejected" | "unavailable";
  reason: string;
  output: string;
  candidate: string | null;
  missing: string[];
  exit_code: number | null;
  elapsed_ms: number;
};

export function assess(raw: string, candidate: string, required: string[], exitCode: number): FilterOutcome {
  if (!required.length) throw new Error("At least one required evidence literal is necessary");
  if (required.some(text => !text || !raw.includes(text))) throw new Error("Invalid oracle: required evidence is absent from raw input");
  const missing = required.filter(text => !candidate.includes(text));
  const smaller = Buffer.byteLength(candidate) < Buffer.byteLength(raw);
  const accepted = exitCode === 0 && !missing.length && smaller;
  return {
    status: accepted ? "applied" : "rejected",
    reason: exitCode !== 0 ? "filter-error" : missing.length ? "lost-evidence" : !smaller ? "no-byte-gain" : "required-literals-preserved",
    output: accepted ? candidate : raw, candidate, missing, exit_code: exitCode, elapsed_ms: 0,
  };
}

export async function filterWithRtk(raw: string, filter: string, required: string[], options: { executable?: string; cwd: string; home: string }): Promise<FilterOutcome> {
  if (!required.length || required.some(text => !text || !raw.includes(text))) throw new Error("Invalid required evidence");
  const executable = options.executable ?? Bun.which("rtk");
  if (!executable) return { status: "unavailable", reason: "rtk-not-installed", output: raw, candidate: null, missing: [], exit_code: null, elapsed_ms: 0 };
  const start = performance.now();
  try {
    const child = Bun.spawn([executable, "pipe", "--filter", filter], {
      cwd: options.cwd,
      env: isolatedEnvironment(options.home),
      stdin: new TextEncoder().encode(raw), stdout: "pipe", stderr: "pipe",
    });
    const timer = setTimeout(() => child.kill("SIGKILL"), 5000);
    try {
      const [candidate, , code] = await Promise.all([new Response(child.stdout).text(), new Response(child.stderr).text(), child.exited]);
      return { ...assess(raw, candidate, required, code), elapsed_ms: Math.round((performance.now() - start) * 100) / 100 };
    } finally { clearTimeout(timer); }
  } catch {
    return { status: "unavailable", reason: "rtk-start-failed", output: raw, candidate: null, missing: [], exit_code: null, elapsed_ms: Math.round(performance.now() - start) };
  }
}

export type BenchCase = { id: string; question: string; filter: string; raw: string; required: string[]; exact: string };
export function fixtures(): BenchCase[] {
  const noise = Array.from({ length: 180 }, (_, i) => `info: compiled module-${i}.ts successfully`).join("\n");
  const diagnostics = ["src/routes.ts(18,7): error TS2322: Type 'string' is not assignable to type 'number'.", "src/client.ts(31,3): error TS2554: Expected 2 arguments, but got 1."];
  const matches = Array.from({ length: 180 }, (_, i) => `src/routes/route-${String(i).padStart(3, "0")}.ts:12:export const handler${i} = true;`);
  const files = Array.from({ length: 240 }, (_, i) => `src/features/feature-${String(i).padStart(3, "0")}.ts`);
  const history = Array.from({ length: 60 }, (_, i) => `${(0xabcdef0 + i).toString(16)} fix: preserve event ${i}\n src/event-${i}.ts | 12 ++++++------\n 1 file changed, 6 insertions(+), 6 deletions(-)`);
  const panic = "thread 'auth::reject_expired' panicked at src/auth.rs:88:\nassertion `left == right` failed\n  left: 401\n right: 200\ntest result: FAILED. 17 passed; 1 failed; 0 ignored\n";
  const stderrReason = "nonstandard verdict: ROUTE_GUARD_EXPIRED retry_after=17";
  return [
    { id: "short-success", question: "Did this already short check pass?", filter: "tsc", raw: "All checks passed!\n", required: ["All checks passed!"], exact: "All checks passed!\n" },
    { id: "typescript-errors", question: "Which files and error codes need fixing?", filter: "tsc", raw: noise + "\n" + diagnostics.join("\n") + "\nFound 2 errors in 2 files.\n", required: ["routes.ts", "18", "TS2322", "client.ts", "31", "TS2554"], exact: diagnostics.join("\n") + "\n" },
    { id: "grep-inventory", question: "List every matching route with its line number.", filter: "grep", raw: matches.join("\n") + "\n", required: matches.map(x => x.split(":export")[0]!), exact: matches.join("\n") + "\n" },
    { id: "grep-one-answer", question: "Show only route-179.ts and its line number.", filter: "grep", raw: matches.join("\n") + "\n", required: ["route-179.ts", "12"], exact: matches[179]! + "\n" },
    { id: "find-inventory", question: "Return the complete path list for a downstream parser.", filter: "find", raw: files.join("\n") + "\n", required: files, exact: files.join("\n") + "\n" },
    { id: "git-latest-five", question: "What are the latest five commit subjects?", filter: "git-log", raw: history.join("\n") + "\n", required: Array.from({ length: 5 }, (_, i) => `fix: preserve event ${i}`), exact: history.slice(0, 5).map(x => x.split("\n")[0]).join("\n") + "\n" },
    { id: "cargo-failure-detail", question: "Which test failed, where, and which values differed?", filter: "cargo-test", raw: "running 18 tests\n" + "test auth::valid ... ok\n".repeat(17) + panic, required: ["reject_expired", "auth.rs", "88", "401", "200"], exact: panic },
    { id: "unusual-failure", question: "Preserve the exact nonstandard failure reason.", filter: "tsc", raw: noise + "\n" + stderrReason + "\n", required: ["ROUTE_GUARD_EXPIRED", "retry_after=17"], exact: stderrReason + "\n" },
  ];
}

export async function benchmark(out: string, executable?: string) {
  const directory = resolve(out);
  mkdirSync(directory, { recursive: true, mode: 0o700 });
  const home = join(directory, "isolated-home");
  mkdirSync(home, { recursive: true, mode: 0o700 });
  const binary = executable ?? Bun.which("rtk") ?? undefined;
  let version = "unavailable";
  let telemetryDisabled = false;
  if (binary) {
    try {
      // Disable tracking consent in the temporary home, never in the user's configuration.
      const consent = Bun.spawn([binary, "telemetry", "disable"], { cwd: home, env: isolatedEnvironment(home), stdout: "pipe", stderr: "pipe", signal: AbortSignal.timeout(5000) });
      const [, , consentCode] = await Promise.all([new Response(consent.stdout).text(), new Response(consent.stderr).text(), consent.exited]);
      telemetryDisabled = consentCode === 0;
      const p = Bun.spawn([binary, "--version"], { cwd: home, stdout: "pipe", stderr: "pipe", env: isolatedEnvironment(home), signal: AbortSignal.timeout(5000) });
      const [text, , code] = await Promise.all([new Response(p.stdout).text(), new Response(p.stderr).text(), p.exited]);
      if (code === 0) version = text.trim();
    } catch { version = "unavailable"; }
  }
  const rows = [];
  for (const fixture of fixtures()) {
    const hash = createHash("sha256").update(fixture.raw).digest("hex");
    const result: FilterOutcome = telemetryDisabled ? await filterWithRtk(fixture.raw, fixture.filter, fixture.required, { executable: binary, cwd: home, home }) : {
      status: "unavailable", reason: binary ? "rtk-preflight-failed" : "rtk-not-installed", output: fixture.raw, candidate: null, missing: [], exit_code: null, elapsed_ms: 0,
    };
    writeFileSync(join(directory, `${fixture.id}.raw.txt`), fixture.raw, { mode: 0o600 });
    writeFileSync(join(directory, `${fixture.id}.selected.txt`), result.output, { mode: 0o600 });
    if (result.candidate !== null) writeFileSync(join(directory, `${fixture.id}.candidate.txt`), result.candidate, { mode: 0o600 });
    const exactPassed = fixture.required.every(x => fixture.exact.includes(x));
    rows.push({ id: fixture.id, question: fixture.question, filter: fixture.filter, source_sha256: hash,
      raw_bytes: Buffer.byteLength(fixture.raw), exact_bytes: Buffer.byteLength(fixture.exact), exact_accepted: exactPassed,
      candidate_bytes: result.candidate === null ? null : Buffer.byteLength(result.candidate),
      selected_bytes: Buffer.byteLength(result.output), rtk_status: result.status, reason: result.reason,
      missing: result.missing, filter_exit: result.exit_code, filter_ms: result.elapsed_ms,
      reduction_percent: Math.round((1 - Buffer.byteLength(result.output) / Buffer.byteLength(fixture.raw)) * 10000) / 100,
    });
  }
  const report = { schema: 1, runner_sha256: createHash("sha256").update(readFileSync(import.meta.path)).digest("hex"), as_of: new Date().toISOString(), runtime: `bun ${Bun.version}`, rtk: version, telemetry_disabled_in_isolated_home: telemetryDisabled,
    method: "Eight synthetic tasks, one filter process per task. Exact projection is an in-process task-specific reference, not a general compressor. Required literals test declared evidence only; not semantic equivalence or billing. Rejected/unavailable RTK results use raw output. No provider calls.",
    rows,
  };
  writeFileSync(join(directory, "report.json"), JSON.stringify(report, null, 2));
  writeFileSync(join(directory, "report.md"), renderBenchmark(report));
  return { ...report, report_path: join(directory, "report.json") };
}

export function renderBenchmark(report: { as_of: string; rtk: string; method: string; rows: { id: string; raw_bytes: number; exact_bytes: number; selected_bytes: number; rtk_status: string; reason: string; filter_ms: number; reduction_percent: number }[] }): string {
  return `# RTK task contract comparison\n\n${report.as_of} · ${report.rtk}\n\n${report.method}\n\n| Task | Raw B | Exact B | Selected B | RTK decision | Reason | Filter ms | Reduction |\n|---|---:|---:|---:|---|---|---:|---:|\n` + report.rows.map(x => `| ${x.id} | ${x.raw_bytes} | ${x.exact_bytes} | ${x.selected_bytes} | ${x.rtk_status} | ${x.reason} | ${x.filter_ms} | ${x.reduction_percent}% |`).join("\n") + "\n\nFilter time includes process startup; no latency comparison against in-process projections. Exact projections answer narrower declared questions. Complete inventories require every path. A recovered raw result counts as zero reduction.\n";
}

export function matchView(path: string, needle: string, budget: number) {
  if (!needle) throw new Error("--match cannot be empty");
  if (statSync(path).size > 8 * 1024 * 1024) throw new Error("Exact preview supports files up to 8 MiB; use scoped rg --no-config for larger files");
  const text = readFileSync(path, "utf8");
  const matching = text.split(/\r?\n/).flatMap((line, index) => line.includes(needle) ? [`${index + 1}:${line}`] : []);
  const shown: string[] = [];
  let bytes = 0;
  for (const line of matching) {
    const size = Buffer.byteLength(line + "\n");
    if (bytes + size > budget) break;
    shown.push(line); bytes += size;
  }
  return { kind: "literal-match", file: path, matched_lines: matching.length, shown_lines: shown.length,
    complete_selection: shown.length === matching.length, omitted_matches: matching.length - shown.length,
    text: shown.join("\n"), note: "Complete selection means all literal matches in this file, not all project evidence." };
}

function isolatedEnvironment(home: string) {
  return { PATH: process.env.PATH ?? "/usr/bin:/bin", HOME: home,
    XDG_CONFIG_HOME: join(home, "config"), XDG_DATA_HOME: join(home, "data"), XDG_STATE_HOME: join(home, "state"),
    LANG: "C.UTF-8", DO_NOT_TRACK: "1" };
}
