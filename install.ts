#!/usr/bin/env bun
import { run } from "./src/cli.ts";
process.exitCode = await run(["install", ...Bun.argv.slice(2)]);
