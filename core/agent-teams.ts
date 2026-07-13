// Agent Teams — parallel multi-agent dispatch with shared hyperstack cache.
// April 2026 best practice: fan-out via subagents, reduce-via context-mode.
// Each dev gets a role; results merge through the SurrealDB team bus.

import { hyperfetch, hyperfetchBatch, type FetchResult, type HyperstackConfig } from "../adapters/hyperstack.js";
import { spawn } from "node:child_process";
import { homedir } from "node:os";
import { join } from "node:path";

export type AgentRole =
  | "explorer"     // Map unknown territory
  | "researcher"   // Deep dive into specific targets
  | "scraper"      // Bulk fetch via hyperstack
  | "analyzer"     // Run catboost/gemma on results
  | "planner"      // Synthesize findings into action
  | "executor";    // Apply changes

export interface AgentSpec {
  id: string;
  role: AgentRole;
  model: "opus-4.6" | "sonnet-4.6" | "haiku-4.5" | "gemma-local" | "catboost-local";
  targets: string[];
  config?: Partial<HyperstackConfig>;
}

export interface TeamResult {
  agentId: string;
  role: AgentRole;
  fetches: FetchResult[];
  durationMs: number;
  localModelCalls: number;
  apiTokenEstimate: number;
}

const SANDBOX = join(homedir(), "agent-token-saver", "plugins", "team-sandbox.sh");

async function broadcastEvent(agentId: string, event: string, payload: object = {}): Promise<void> {
  return new Promise((resolve) => {
    const child = spawn("bash", [SANDBOX, "broadcast", agentId, event, JSON.stringify(payload)], {
      stdio: "ignore",
    });
    child.on("close", () => resolve());
  });
}

async function runAgent(spec: AgentSpec, teamNs: string): Promise<TeamResult> {
  const t0 = Date.now();
  await broadcastEvent(spec.id, "start", { role: spec.role, targets: spec.targets.length });

  const cfg: Partial<HyperstackConfig> = {
    ...spec.config,
    teamSandbox: true,
    teamNamespace: teamNs,
    useMlFilter: true,
    useGemmaGate: true,
  };

  if (spec.role === "scraper" || spec.role === "researcher") {
    const fetches = await hyperfetchBatch(spec.targets, cfg);
    const apiTokens = fetches.reduce((sum, f) => sum + (f.summary ? f.tokenEstimate : f.tokenEstimate), 0);
    await broadcastEvent(spec.id, "done", { fetched: fetches.length, tokens: apiTokens });
    return {
      agentId: spec.id,
      role: spec.role,
      fetches,
      durationMs: Date.now() - t0,
      localModelCalls: fetches.length,
      apiTokenEstimate: apiTokens,
    };
  }

  if (spec.role === "explorer") {
    const seeds = spec.targets.slice(0, 3);
    const initial = await hyperfetchBatch(seeds, { ...cfg, maxStage: "curl_cffi" });
    await broadcastEvent(spec.id, "explored", { seeds: seeds.length });
    return {
      agentId: spec.id,
      role: "explorer",
      fetches: initial,
      durationMs: Date.now() - t0,
      localModelCalls: initial.length,
      apiTokenEstimate: initial.reduce((s, f) => s + f.tokenEstimate, 0),
    };
  }

  return {
    agentId: spec.id,
    role: spec.role,
    fetches: [],
    durationMs: Date.now() - t0,
    localModelCalls: 0,
    apiTokenEstimate: 0,
  };
}

export interface TeamMission {
  teamNamespace: string;
  agents: AgentSpec[];
  mergeStrategy: "parallel" | "pipeline";
}

export interface MissionReport {
  teamNamespace: string;
  durationMs: number;
  totalFetches: number;
  uniqueContent: number;
  apiTokensUsed: number;
  apiTokensAvoided: number;
  savingsPct: number;
  results: TeamResult[];
}

function estimateBaselineTokens(fetches: FetchResult[]): number {
  return fetches.reduce((sum, f) => sum + Math.ceil(f.bytes / 3.5), 0);
}

export async function dispatchTeam(mission: TeamMission): Promise<MissionReport> {
  const t0 = Date.now();
  await broadcastEvent("team-orchestrator", "mission-start", {
    ns: mission.teamNamespace,
    agents: mission.agents.length,
  });

  let results: TeamResult[];
  if (mission.mergeStrategy === "parallel") {
    results = await Promise.all(mission.agents.map((a) => runAgent(a, mission.teamNamespace)));
  } else {
    results = [];
    for (const a of mission.agents) {
      results.push(await runAgent(a, mission.teamNamespace));
    }
  }

  const allFetches = results.flatMap((r) => r.fetches);
  const uniqueHashes = new Set(allFetches.map((f) => f.contentHash));
  const apiTokensUsed = results.reduce((s, r) => s + r.apiTokenEstimate, 0);
  const baseline = estimateBaselineTokens(allFetches);
  const avoided = Math.max(0, baseline - apiTokensUsed);
  const savingsPct = baseline > 0 ? (avoided / baseline) * 100 : 0;

  const report: MissionReport = {
    teamNamespace: mission.teamNamespace,
    durationMs: Date.now() - t0,
    totalFetches: allFetches.length,
    uniqueContent: uniqueHashes.size,
    apiTokensUsed,
    apiTokensAvoided: avoided,
    savingsPct,
    results,
  };

  await broadcastEvent("team-orchestrator", "mission-done", {
    ns: mission.teamNamespace,
    savings_pct: savingsPct.toFixed(1),
    tokens_avoided: avoided,
  });

  return report;
}

export const ROLES_APRIL_2026: Record<string, AgentSpec> = {
  frontliner: {
    id: "frontliner-1",
    role: "scraper",
    model: "haiku-4.5",
    targets: [],
    config: { maxStage: "curl_cffi", useGemmaGate: true, gemmaThresholdTokens: 300 },
  },
  deep_diver: {
    id: "deep-diver-1",
    role: "researcher",
    model: "sonnet-4.6",
    targets: [],
    config: { maxStage: "camoufox", useGemmaGate: true, gemmaThresholdTokens: 800 },
  },
  heavy_lifter: {
    id: "heavy-lifter-1",
    role: "researcher",
    model: "opus-4.6",
    targets: [],
    config: { maxStage: "browser", useGemmaGate: true, gemmaThresholdTokens: 1500 },
  },
  explorer: {
    id: "explorer-1",
    role: "explorer",
    model: "haiku-4.5",
    targets: [],
    config: { maxStage: "curl_cffi", useMlFilter: true },
  },
};

export function buildTeam(targets: string[], teamNs: string = "default"): TeamMission {
  const chunks = chunkArray(targets, 10);
  const agents: AgentSpec[] = chunks.map((chunk, i) => ({
    ...ROLES_APRIL_2026.frontliner,
    id: `frontliner-${i}`,
    targets: chunk,
  }));
  return { teamNamespace: teamNs, agents, mergeStrategy: "parallel" };
}

function chunkArray<T>(arr: T[], size: number): T[][] {
  const out: T[][] = [];
  for (let i = 0; i < arr.length; i += size) out.push(arr.slice(i, i + size));
  return out;
}
