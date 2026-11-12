import { createHash } from "node:crypto";
import { cpSync, existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import metadata from "../package.json";

const root = resolve(import.meta.dir, "..");
function git(args: string[]) {
  const result = Bun.spawnSync(["git", ...args], { cwd: root });
  if (result.exitCode !== 0) throw new Error(`git ${args[0]} failed: ${result.stderr.toString().trim()}`);
  return result.stdout;
}
export function releaseFiles() {
  return [...new Set(git(["ls-files", "--cached", "--others", "--exclude-standard", "-z"]).toString().split("\0").filter(path => path && existsSync(join(root, path))))];
}
export function inspect(files: string[]) {
  const forbidden = files.filter(path => /\.(?:py|sh|jsonl)$/.test(path) || /(?:^|\/)\.env(?:$|\.)/.test(path));
  if (forbidden.length) throw new Error(`Retired or private file types in release: ${forbidden.join(", ")}`);
  for (const path of ["src/cli.ts", "install.ts", "README.md", "LICENSE", "bun.lock", "docs/assets/social-preview.png"]) {
    if (!files.includes(path)) throw new Error(`Missing release file: ${path}`);
  }
  const png = readFileSync(join(root, "docs/assets/social-preview.png"));
  if (png.length > 1_000_000 || png.readUInt32BE(16) !== 1280 || png.readUInt32BE(20) !== 640) throw new Error("Social preview must be 1280x640 and <=1 MB");
  return { passed: true, files: files.length, version: metadata.version };
}
export function audit() {
  const files = releaseFiles();
  const result = inspect(files);
  const directory = mkdtempSync(join(tmpdir(), "ats-public-scan-"));
  try {
    for (const path of files) {
      const destination = join(directory, path);
      mkdirSync(dirname(destination), { recursive: true });
      cpSync(join(root, path), destination);
    }
    const scanner = Bun.spawnSync(["gitleaks", "dir", directory, "--redact", "--no-banner"], { stdout: "pipe", stderr: "pipe" });
    if (scanner.exitCode !== 0) throw new Error(`Public-file secret scan failed: ${scanner.stderr.toString()}`);
    return result;
  } finally { rmSync(directory, { recursive: true, force: true }); }
}
export function pack(out: string) {
  git(["diff", "--exit-code"]); git(["diff", "--cached", "--exit-code"]);
  const files = git(["ls-files", "-z"]).toString().split("\0").filter(Boolean);
  inspect(files);
  const directory = resolve(out);
  mkdirSync(directory, { recursive: true });
  const name = `agent-token-saver-${metadata.version}.tar.gz`;
  const artifact = join(directory, name);
  const revision = git(["rev-parse", "HEAD"]).toString().trim();
  const data = git(["archive", "--format=tar.gz", `--prefix=agent-token-saver-${metadata.version}/`, "HEAD"]);
  writeFileSync(artifact, data);
  writeFileSync(join(directory, "SHA256SUMS"), `${createHash("sha256").update(data).digest("hex")}  ${name}\n`);
  return { artifact, revision, bytes: data.length, checksum: join(directory, "SHA256SUMS") };
}
if (import.meta.main) {
  try {
    const command = Bun.argv[2];
    if (command === "audit") console.log(JSON.stringify(audit()));
    else if (command === "pack" && Bun.argv[3]) console.log(JSON.stringify(pack(Bun.argv[3])));
    else throw new Error("Usage: bun tools/release.ts audit | pack OUT_DIR");
  } catch (error) {
    console.error(error instanceof Error ? error.message : String(error)); process.exitCode = 1;
  }
}
