#!/usr/bin/env bun
import { homedir } from "node:os";
import { join } from "node:path";
import { costReport, positiveInteger, tail, verify } from "./core.ts";
import { doctor, install, rollback } from "./install.ts";
import { benchmark, matchView } from "./rtk.ts";
import { guides } from "./guide.ts";
import skills from "../data/skills-v5.json";
import metadata from "../package.json";
import exampleUsage from "../examples/usage.json";

const help = `ats ${metadata.version} — keep the answer, skip the noise

  verify [--log-dir DIR] [--timeout-ms N] -- COMMAND [ARG...]
  project FILE [--match TEXT] [--max-bytes N]
  cost FILE|-|--example
  bench --out DIR [--rtk PATH]
  guide [start|rtk|checks|cache|handoff|speed|migration]
  skills [NAME]
  install [--home DIR] [--apply]
  rollback --id ID [--home DIR] [--apply]
  doctor [--home DIR]

Use --json before -- for machine output. Human-readable output is the default.
Try: ats guide              ats verify -- bun test
No hooks, command rewriting, paid model calls or mandatory RTK.`;

function options(args: string[], allowed: string[], flags: string[] = []) {
  const values: Record<string, string> = {};
  const positional: string[] = [];
  for (let i = 0; i < args.length; i++) {
    const value = args[i]!;
    if (flags.includes(value)) { values[value] = "true"; continue; }
    if (value.startsWith("--")) {
      if (!allowed.includes(value)) throw new Error(`Unknown option ${value}`);
      const next = args[++i];
      if (next === undefined || next.startsWith("--")) throw new Error(`Missing value for ${value}`);
      values[value] = next;
    } else positional.push(value);
  }
  return { values, positional };
}

export async function main(input: string[]): Promise<number> {
  const separator = input.indexOf("--");
  const head = separator < 0 ? input : input.slice(0, separator);
  const json = head.includes("--json");
  const args = [...head.filter(x => x !== "--json"), ...(separator < 0 ? [] : input.slice(separator))];
  const [command, ...rest] = args;
  const print = (value: unknown, human: string) => console.log(json ? JSON.stringify(value, null, 2) : human);
  switch (command) {
    case undefined: case "--help": case "-h": case "help": console.log(help); return 0;
    case "--version": console.log(metadata.version); return 0;
    case "verify": {
      const split = rest.indexOf("--");
      if (split < 0) throw new Error("verify requires -- COMMAND (example: ats verify -- bun test)");
      const { values, positional } = options(rest.slice(0, split), ["--log-dir", "--timeout-ms"]);
      if (positional.length) throw new Error("Unexpected verify arguments");
      const result = await verify(rest.slice(split + 1), {
        directory: values["--log-dir"] ?? join(homedir(), ".local", "state", "agent-token-saver", "runs"),
        timeoutMs: positiveInteger(values["--timeout-ms"] ?? "120000", "timeout-ms"),
      });
      const evidence = result.evidence ? `\n${result.evidence.stdout.text}${result.evidence.stderr.text}\nTail only; omitted ${result.evidence.stdout.omitted_bytes + result.evidence.stderr.omitted_bytes} bytes.` : "";
      print(result, `${result.passed ? "PASS" : "FAIL"} · exit ${result.exit_code} · ${result.elapsed_ms} ms${result.timed_out ? " · timed out" : ""}${result.spawn_error ? `\n${result.spawn_error}` : ""}\nFull stdout: ${result.stdout.path}\nFull stderr: ${result.stderr.path}${evidence}`);
      return result.exit_code;
    }
    case "project": {
      const { values, positional } = options(rest, ["--max-bytes", "--match"]);
      if (positional.length !== 1) throw new Error("project requires one file");
      const limit = positiveInteger(values["--max-bytes"] ?? "4096", "max-bytes");
      if (limit > 65536) throw new Error("max-bytes cannot exceed 65536");
      if (values["--match"] !== undefined) {
        const result = matchView(positional[0]!, values["--match"], limit);
        print(result, `${result.text}\n${result.shown_lines}/${result.matched_lines} matching lines shown · ${result.omitted_matches} omitted`);
      } else {
        const result = tail(positional[0]!, limit);
        print({ kind: "tail-only", file: positional[0], complete: result.omitted_bytes === 0, ...result }, `${result.text}\nTail only · ${result.omitted_bytes} bytes omitted · ${positional[0]}`);
      }
      return 0;
    }
    case "cost": {
      if (rest.length !== 1) throw new Error("cost requires one JSON file or -");
      const data: unknown = rest[0] === "--example" ? exampleUsage : JSON.parse(rest[0] === "-" ? await Bun.stdin.text() : await Bun.file(rest[0]!).text());
      const result = costReport(data);
      print(result, `${result.total.toFixed(6)} ${result.currency} · supplied-price estimate, not an invoice\nPrices: ${result.price_source}\n${result.note}`); return 0;
    }
    case "bench": {
      const { values, positional } = options(rest, ["--out", "--rtk"]);
      if (positional.length || !values["--out"]) throw new Error("bench requires --out DIR");
      const result = await benchmark(values["--out"], values["--rtk"]);
      print(result, `${result.rtk} · ${result.rows.length} synthetic cases\n` + result.rows.map(x => `${x.id}: ${x.rtk_status} (${x.reason}) · ${x.reduction_percent}% selected-byte reduction`).join("\n") + `\nReport: ${result.report_path}\nNo provider-cost or general speed claim.`);
      return 0;
    }
    case "guide": {
      if (rest.length > 1) throw new Error("guide accepts one topic");
      const topic = rest[0] ?? "start";
      if (!guides[topic]) throw new Error(`Unknown topic. Choose: ${Object.keys(guides).join(", ")}`);
      print({ topic, text: guides[topic] }, guides[topic]); return 0;
    }
    case "skills": {
      if (rest.length > 1) throw new Error("skills accepts at most one exact name");
      const selected = rest.length ? skills.skills.filter(x => x.name === rest[0]) : skills.skills;
      if (!selected.length) throw new Error(`Unknown curated skill: ${rest[0]}`);
      print({ as_of: skills.as_of, selection: skills.selection, skills: selected }, selected.map(x => rest.length ? `${x.name}\n${x.principle}\nATS: ${x.application}\nLimit: ${x.guard}` : `${x.name}: ${x.principle}`).join("\n")); return 0;
    }
    case "install": case "doctor": case "rollback": {
      const { values, positional } = options(rest, command === "rollback" ? ["--home", "--id"] : ["--home"], command === "doctor" ? [] : ["--apply"]);
      if (positional.length) throw new Error("Unexpected positional arguments");
      if (command === "install") {
        const result = install(values["--home"], !values["--apply"]);
        print(result, `${result.dry_run ? "PLAN" : "INSTALLED"} · ${result.launchers.join(", ")}\n${"rollback_id" in result ? `Rollback id: ${result.rollback_id}\n` : "Use --apply to install.\n"}No host configuration changed.\nNext: ats guide`); return 0;
      }
      if (command === "rollback") {
        if (!values["--id"]) throw new Error("rollback requires --id from the installation result");
        const result = rollback(values["--home"] ?? homedir(), values["--id"], Boolean(values["--apply"]));
        print(result, `${result.dry_run ? "PLAN" : "RESTORED"} · installation ${result.id}`); return 0;
      }
      const result = doctor(values["--home"]);
      print(result, `${result.passed ? "PASS" : "FAIL"} · ${result.status} · ${result.runtime}\nInstall hashes and starters checked; live host behavior not verified.`); return result.passed ? 0 : 1;
    }
    default: throw new Error(`Unknown command: ${command}. Use ats --help`);
  }
}

export async function run(args: string[]) {
  try { return await main(args); }
  catch (error) {
    const detail = error instanceof Error ? error.message : String(error);
    const split = args.indexOf("--");
    if ((split < 0 ? args : args.slice(0, split)).includes("--json")) console.log(JSON.stringify({ passed: false, error: detail }));
    else console.error(`Error: ${detail}`);
    return 1;
  }
}
if (import.meta.main) process.exitCode = await run(Bun.argv.slice(2));
