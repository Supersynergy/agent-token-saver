import { afterEach, expect, test } from "bun:test";
import { chmodSync, existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { assess, benchmark, filterWithRtk, fixtures, matchView } from "../src/rtk.ts";

const directories: string[] = [];
function folder() { const dir = mkdtempSync(join(tmpdir(), "ats-rtk-")); directories.push(dir); return dir; }
afterEach(() => { for (const dir of directories.splice(0)) rmSync(dir, { recursive: true, force: true }); });

test("evidence loss vetoes even a large byte reduction", () => {
  const result = assess("prefix\nERROR TS2322 src/routes.ts:18\n" + "noise\n".repeat(100), "ERROR\n", ["TS2322", "routes.ts", "18"], 0);
  expect(result.status).toBe("rejected");
  expect(result.reason).toBe("lost-evidence");
  expect(result.missing).toContain("TS2322");
  expect(result.output).toContain("TS2322");
  expect(result.candidate).toBe("ERROR\n");
});

test("a nonzero filter exit rejects otherwise valid evidence", () => {
  const result = assess("noise\nERROR\n", "ERROR\n", ["ERROR"], 3);
  expect(result.status).toBe("rejected");
  expect(result.reason).toBe("filter-error");
  expect(result.output).toBe("noise\nERROR\n");
});

test("no gain means no extra layer; accepted output must be smaller", () => {
  expect(assess("OK\n", "OK\n", ["OK"], 0).reason).toBe("no-byte-gain");
  expect(assess("noise\nOK\n", "OK\n", ["OK"], 0).status).toBe("applied");
});

test("invalid oracles cannot make an empty projection pass", () => {
  expect(() => assess("raw", "", [], 0)).toThrow();
  expect(() => assess("raw", "", [""], 0)).toThrow();
  expect(() => assess("raw", "x", ["x"], 0)).toThrow();
});

test("every synthetic task has a valid raw and task-specific reference oracle", () => {
  const cases = fixtures();
  expect(cases).toHaveLength(8);
  for (const row of cases) {
    expect(row.required.length).toBeGreaterThan(0);
    for (const literal of row.required) {
      expect(row.raw.includes(literal)).toBe(true);
      expect(row.exact.includes(literal)).toBe(true);
    }
  }
  const inventory = cases.find(x => x.id === "find-inventory")!;
  expect(inventory.required).toHaveLength(240);
  expect(assess(inventory.raw, inventory.required[0]!, inventory.required, 0).status).toBe("rejected");
});

function fakeRtk(body: string) {
  const home = folder();
  const executable = join(home, "fake-rtk.ts");
  writeFileSync(executable, `#!/usr/bin/env bun\n${body}\n`, { mode: 0o700 });
  chmodSync(executable, 0o700);
  return { home, executable };
}

test("optional filter executes only stdin projection, never a producer command", async () => {
  const { home, executable } = fakeRtk(`const raw = await Bun.stdin.text(); console.log(raw.split('\\n').find(x=>x.includes('ERROR')));`);
  const result = await filterWithRtk("noise\nERROR TS2322\n", "tsc", ["TS2322"], { home, cwd: home, executable });
  expect(result.status).toBe("applied");
  expect(result.output.trim()).toBe("ERROR TS2322");
});

test("optional tool unavailability falls back to exact raw bytes", async () => {
  const home = folder();
  const result = await filterWithRtk("ERROR\n", "tsc", ["ERROR"], { home, cwd: home, executable: join(home, "missing") });
  expect(result.status).toBe("unavailable");
  expect(result.output).toBe("ERROR\n");
});

test("benchmark contains failed candidates, raw fallbacks and isolated settings", async () => {
  const { home, executable } = fakeRtk(`
if (Bun.argv[2] === 'telemetry') { await Bun.write(process.env.HOME+'/consent.txt','disabled'); }
else if (Bun.argv[2] === '--version') console.log('fake-rtk test');
else { await Bun.stdin.text(); console.log('lost everything'); }
`);
  const result = await benchmark(join(home, "report"), executable);
  expect(result.rows).toHaveLength(8);
  expect(result.rows.every(row => row.rtk_status === "rejected")).toBe(true);
  expect(result.rows.every(row => row.selected_bytes === row.raw_bytes)).toBe(true);
  expect(existsSync(join(home, "report", "isolated-home", "consent.txt"))).toBe(true);
  expect(readFileSync(join(home, "report", "typescript-errors.candidate.txt"), "utf8")).toContain("lost everything");
  expect(readFileSync(join(home, "report", "report.md"), "utf8")).toContain("not semantic equivalence or billing");
});

test("matching before the tail finds an early error with explicit coverage", () => {
  const path = join(folder(), "build.log");
  writeFileSync(path, "error TS2322\n" + "ok\n".repeat(20000) + "last line\n");
  const view = matchView(path, "TS2322", 100);
  expect(view.text).toBe("1:error TS2322");
  expect(view.complete_selection).toBe(true);
  expect(view.matched_lines).toBe(1);
});

test("many matches are never reported as complete after truncation", () => {
  const path = join(folder(), "build.log");
  writeFileSync(path, "ERROR first\nERROR second\nERROR third\n");
  const view = matchView(path, "ERROR", 15);
  expect(view.matched_lines).toBe(3);
  expect(view.shown_lines).toBe(1);
  expect(view.omitted_matches).toBe(2);
  expect(view.complete_selection).toBe(false);
  expect(() => matchView(path, "", 100)).toThrow();
});

test("files above the explicit preview ceiling require an exact search tool", () => {
  const home = folder(); mkdirSync(join(home, "logs"));
  const path = join(home, "logs", "large.log");
  writeFileSync(path, Buffer.alloc(8 * 1024 * 1024 + 1, 65));
  expect(() => matchView(path, "A", 100)).toThrow("rg --no-config");
});
