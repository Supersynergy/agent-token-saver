import { afterEach, describe, expect, test } from "bun:test";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, realpathSync, rmSync, statSync, symlinkSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { costReport, tail, verify } from "../src/core.ts";
import { doctor, install, rollback } from "../src/install.ts";
import skills from "../data/skills-v5.json";

const temporary: string[] = [];
function folder() {
  const path = mkdtempSync(join(tmpdir(), "ats-v5-"));
  temporary.push(path); return path;
}
afterEach(() => { for (const path of temporary.splice(0)) rmSync(path, { recursive: true, force: true }); });
const runtime = process.execPath;
const root = join(import.meta.dir, "..");
const cli = join(root, "src", "cli.ts");

async function invoke(args: string[]) {
  const child = Bun.spawn([runtime, cli, "--json", ...args], { stdout: "pipe", stderr: "pipe" });
  const [stdout, stderr, code] = await Promise.all([new Response(child.stdout).text(), new Response(child.stderr).text(), child.exited]);
  return { stdout, stderr, code };
}

describe("acceptance survives projection", () => {
  test("nonstandard failure preserves exit, both raw streams and single execution", async () => {
    const directory = folder();
    const marker = join(directory, "marker");
    const result = await verify([runtime, "-e", `const f=${JSON.stringify(marker)}; require('node:fs').appendFileSync(f,'once'); console.log('x'.repeat(30000)); console.error('nonstandard verdict'); process.exit(23)`], { directory, timeoutMs: 5000 });
    expect(result.exit_code).toBe(23);
    expect(result.passed).toBe(false);
    expect(readFileSync(marker, "utf8")).toBe("once");
    expect(readFileSync(result.stdout.path, "utf8")).toHaveLength(30001);
    expect(readFileSync(result.stderr.path, "utf8")).toContain("nonstandard verdict");
    expect(result.evidence?.stdout.omitted_bytes).toBeGreaterThan(0);
    expect(result.evidence?.stderr.text).toContain("nonstandard verdict");
    expect(statSync(result.stdout.path).mode & 0o777).toBe(0o600);
    expect(JSON.parse(readFileSync(join(result.stdout.path, "..", "result.json"), "utf8")).passed).toBe(false);
  });

  test("silent failure never becomes success", async () => {
    const result = await verify([runtime, "-e", "process.exit(9)"], { directory: folder(), timeoutMs: 5000 });
    expect(result.exit_code).toBe(9);
    expect(result.passed).toBe(false);
    expect(result.evidence).not.toBeNull();
  });

  test("green output is stored without flooding the result", async () => {
    const result = await verify([runtime, "-e", "console.log('ok'.repeat(10000))"], { directory: folder(), timeoutMs: 5000 });
    expect(result.passed).toBe(true);
    expect(result.evidence).toBeNull();
    expect(result.stdout.bytes).toBe(20001);
  });

  test("missing executable reports unavailable as 127", async () => {
    const result = await verify([join(folder(), "does-not-exist")], { directory: folder(), timeoutMs: 5000 });
    expect(result.passed).toBe(false);
    expect(result.exit_code).toBe(127);
    expect(result.spawn_error).not.toBeNull();
  });

  test("timeout is explicit and cannot pass", async () => {
    const result = await verify([runtime, "-e", "setTimeout(()=>{},10000)"], { directory: folder(), timeoutMs: 50 });
    expect(result.exit_code).toBe(124);
    expect(result.timed_out).toBe(true);
    expect(result.passed).toBe(false);
  });

  test("CLI forwards a failing exit and does not interpret shell metacharacters", async () => {
    const directory = folder();
    const marker = join(directory, "should-not-exist");
    const result = await invoke(["verify", "--log-dir", directory, "--", runtime, "-e", "console.error(process.argv[1]); process.exit(17)", `$(touch ${marker})`]);
    expect(result.code).toBe(17);
    expect(existsSync(marker)).toBe(false);
    expect(JSON.parse(result.stdout).evidence.stderr.text).toContain("$(touch");
  });

  test("a tail explicitly exposes omitted bytes and keeps the original", () => {
    const path = join(folder(), "source.log");
    writeFileSync(path, "first error\n" + "a".repeat(200) + "last line");
    const projected = tail(path, 32);
    expect(projected.omitted_bytes).toBeGreaterThan(0);
    expect(projected.text.endsWith("last line")).toBe(true);
    expect(readFileSync(path, "utf8").startsWith("first error")).toBe(true);
  });
});

const costFixture = {
  currency: "USD", price_source: "synthetic test rates",
  usage: { fresh_input: 1000, cache_read: 9000, cache_write: 0, output: 100 },
  prices_per_million: { fresh_input: 1, cache_read: 0.1, cache_write: 1.25, output: 5 },
};
describe("cost claims", () => {
  test("prices disjoint classes and labels the answer as an estimate", () => {
    const result = costReport(costFixture);
    expect(result.total).toBeCloseTo(0.0024, 10);
    expect(result.invoice).toBe(false);
    expect(result.price_source).toBe("synthetic test rates");
  });
  test("missing, negative, fractional, string and nonfinite counters fail", () => {
    for (const invalid of [undefined, -1, 0.5, "9000", Infinity]) {
      expect(() => costReport({ ...costFixture, usage: { ...costFixture.usage, cache_read: invalid } })).toThrow();
    }
    expect(() => costReport({ ...costFixture, price_source: "" })).toThrow();
    expect(() => costReport({ ...costFixture, prices_per_million: { ...costFixture.prices_per_million, output: -1 } })).toThrow();
  });
});

describe("isolated adoption and rollback", () => {
  test("dry-run makes no install; installation preserves host files and a previous starter", async () => {
    const home = join(folder(), "home with space and 'quote");
    mkdirSync(join(home, ".local", "bin"), { recursive: true });
    mkdirSync(join(home, ".claude"));
    const config = join(home, ".claude", "settings.json");
    const launcher = join(home, ".local", "bin", "agent-token-saver");
    writeFileSync(config, '{"unrelated":true}\n');
    writeFileSync(launcher, "#!/bin/sh\nprintf old-starter\n", { mode: 0o700 });
    expect(install(home).dry_run).toBe(true);
    expect(existsSync(join(home, ".agent-token-saver-v5"))).toBe(false);
    const applied = install(home, false);
    if (!("rollback_id" in applied)) throw new Error("Missing rollback id");
    expect(applied.rollback_id).toBeTruthy();
    expect(readFileSync(config, "utf8")).toBe('{"unrelated":true}\n');
    expect(doctor(home).passed).toBe(true);
    // Run the installed shell launcher, not the checkout's entry point.
    const child = Bun.spawn([launcher, "--json", "doctor", "--home", home], { stdout: "pipe", stderr: "pipe" });
    expect(await child.exited).toBe(0);
    expect(JSON.parse(await new Response(child.stdout).text()).passed).toBe(true);
    const result = rollback(home, applied.rollback_id, true);
    expect(result.dry_run).toBe(false);
    expect(readFileSync(launcher, "utf8")).toContain("old-starter");
  });

  test("generation update retains old files; tampering fails the doctor", () => {
    const home = folder();
    install(home, false);
    const first = realpathSync(join(home, ".agent-token-saver-v5", "current"));
    install(home, false);
    const current = realpathSync(join(home, ".agent-token-saver-v5", "current"));
    expect(current).not.toBe(first);
    expect(existsSync(first)).toBe(true);
    writeFileSync(join(current, "src", "core.ts"), "tampered");
    expect(doctor(home).passed).toBe(false);
  });

  test("foreign or broken current links are never replaced", () => {
    for (const broken of [false, true]) {
      const home = folder();
      const store = join(home, ".agent-token-saver-v5");
      mkdirSync(store);
      const target = broken ? join(home, "missing") : folder();
      symlinkSync(target, join(store, "current"));
      expect(() => install(home, false)).toThrow();
      expect(existsSync(join(home, ".local", "bin", "agent-token-saver"))).toBe(false);
    }
  });
});

test("exactly 20 unique, sourced principles; both shipped skill copies agree", () => {
  expect(skills.skills).toHaveLength(20);
  expect(new Set(skills.skills.map(x => x.name)).size).toBe(20);
  for (const skill of skills.skills) {
    expect(skill.source_sha256).toMatch(/^[a-f0-9]{64}$/);
    expect(skill.application.length).toBeGreaterThan(15);
    expect(skill.guard.length).toBeGreaterThan(15);
  }
  expect(readFileSync(join(root, "skills/agent-token-saver/SKILL.md"), "utf8"))
    .toBe(readFileSync(join(root, ".agents/skills/agent-token-saver/SKILL.md"), "utf8"));
});

test("Bun installer uses maintained product; rejected v4 flags leave no installation", async () => {
  const home = folder();
  const child = Bun.spawn([runtime, join(root, "install.ts"), "--home", home, "--apply"], { stdout: "pipe", stderr: "pipe" });
  expect(await child.exited).toBe(0);
  expect(doctor(home).passed).toBe(true);
  const invalid = await invoke(["install", "--home", folder(), "--profile", "lean"]);
  expect(invalid.code).toBe(1);
  expect(JSON.parse(invalid.stdout).error).toContain("Unknown option");
});

test("project rejects invalid budgets rather than producing a misleading success", async () => {
  for (const value of ["0", "-1", "3.4", "NaN", "65537"]) {
    const result = await invoke(["project", "README.md", "--max-bytes", value]);
    expect(result.code).toBe(1);
    expect(JSON.parse(result.stdout).passed).toBe(false);
  }
});

test("default CLI is readable and --json after the command separator belongs to the child", async () => {
  const display = Bun.spawn([runtime, cli, "guide", "rtk"], { stdout: "pipe", stderr: "pipe" });
  expect(await display.exited).toBe(0);
  expect(await new Response(display.stdout).text()).toContain("RTK helps only");
  const home = folder();
  const child = Bun.spawn([runtime, cli, "verify", "--log-dir", home, "--", runtime, "-e", "console.log(process.argv[1])", "--json"], { stdout: "pipe", stderr: "pipe" });
  expect(await child.exited).toBe(0);
  const text = await new Response(child.stdout).text();
  expect(text.startsWith("PASS")).toBe(true);
  expect(text.includes('"passed"')).toBe(false);
});

test("rollback preserves pre-existing symlink starters and refuses later edits", () => {
  const home = folder();
  mkdirSync(join(home, ".local", "bin"), { recursive: true });
  const old = join(home, "older.ts");
  writeFileSync(old, "old");
  const launcher = join(home, ".local", "bin", "agent-token-saver");
  symlinkSync(old, launcher);
  const result = install(home, false);
  if (!("rollback_id" in result)) throw new Error("Missing id");
  expect(rollback(home, result.rollback_id, false).dry_run).toBe(true);
  rollback(home, result.rollback_id, true);
  expect(realpathSync(launcher)).toBe(realpathSync(old));
  const newer = install(home, false);
  if (!("rollback_id" in newer)) throw new Error("Missing id");
  rmSync(launcher);
  writeFileSync(launcher, "user edited after install");
  expect(() => rollback(home, newer.rollback_id, true)).toThrow("Starter changed");
  expect(readFileSync(launcher, "utf8")).toBe("user edited after install");
});

test("an old receipt cannot roll back a newer generation", () => {
  const home = folder();
  const first = install(home, false);
  install(home, false);
  if (!("rollback_id" in first)) throw new Error("Missing id");
  expect(() => rollback(home, first.rollback_id, true)).toThrow("newer or foreign");
});

test("a missing install is a useful doctor result rather than an exception", () => {
  const result = doctor(folder());
  expect(result.passed).toBe(false);
  expect(result.status).toBe("not-installed");
});

test("maintained product has no Python or shell source and current docs link locally", () => {
  const tracked = Bun.spawnSync(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], { cwd: root });
  expect(tracked.exitCode).toBe(0);
  const paths = tracked.stdout.toString().split("\0").filter(path => path && existsSync(join(root, path)));
  expect(paths.filter(path => /\.(py|sh)$/.test(path))).toEqual([]);
  for (const path of ["README.md", "docs/GUIDE.md", "docs/RTK.md", "docs/CONCEPT.md", "docs/SKILLS.md", "docs/MIGRATION.md"]) {
    const body = readFileSync(join(root, path), "utf8");
    for (const link of body.matchAll(/\]\(([^)]+)\)/g)) {
      const target = link[1]!.split("#")[0]!;
      if (!target || target.includes("://") || target.startsWith("#")) continue;
      expect(existsSync(join(root, path, "..", target))).toBe(true);
    }
  }
});

test("invalid timeouts fail before starting a command or making logs", async () => {
  const directory = join(folder(), "no-log-created");
  for (const timeoutMs of [0, -1, Infinity, 3.4, 2147483648]) {
    await expect(verify([runtime, "--version"], { directory, timeoutMs })).rejects.toThrow("timeout-ms");
  }
  expect(existsSync(directory)).toBe(false);
});

test("installed CLI has a runnable cost example without a checkout-relative input", async () => {
  const home = folder();
  install(home, false);
  const child = Bun.spawn([join(home, ".local", "bin", "ats"), "--json", "cost", "--example"], { cwd: home, stdout: "pipe", stderr: "pipe" });
  expect(await child.exited).toBe(0);
  expect(JSON.parse(await new Response(child.stdout).text()).total).toBeCloseTo(0.0024, 10);
});

test("every recorded retired surface is absent from the maintained checkout", () => {
  const manifest = JSON.parse(readFileSync(join(root, "docs/retired-surfaces.json"), "utf8")) as { files: { path: string; source_sha256: string }[] };
  expect(manifest.files.length).toBe(138);
  for (const file of manifest.files) {
    expect(file.source_sha256).toMatch(/^[a-f0-9]{64}$/);
    expect(existsSync(join(root, file.path))).toBe(false);
  }
});

test("installed speed guide is available and never promises an automatic daemon", async () => {
  const home = folder();
  install(home, false);
  const child = Bun.spawn([join(home, ".local", "bin", "ats"), "guide", "speed"], { cwd: home, stdout: "pipe", stderr: "pipe" });
  expect(await child.exited).toBe(0);
  const text = await new Response(child.stdout).text();
  expect(text).toContain("Separate model wait");
  expect(text).toContain("No universal turn cap");
  const release = realpathSync(join(home, ".agent-token-saver-v5", "current"));
  expect(existsSync(join(release, "docs", "SPEED.md"))).toBe(true);
});
