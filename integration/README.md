# Claude Code Integration Bundle

Drop-in Hyperstack auto-integration for Claude Code v2.1.x. Makes every fetch, every subagent, every mode automatically use the 4-stage escalation chain.

## What's Inside

| Path | Install To | Purpose |
|------|-----------|---------|
| `skills/hyperstack.md` | `~/.claude/skills/hyperstack.md` | Always-on skill that teaches Claude to use hyperfetch/dsh/cts-team |
| `agents/hyperstack-scraper.md` | `~/.claude/agents/` | Haiku 4.5 bulk fetch subagent |
| `agents/hyperstack-researcher.md` | `~/.claude/agents/` | Sonnet 4.6 JS-heavy research subagent |
| `agents/hyperstack-heavy.md` | `~/.claude/agents/` | Opus 4.6 hard-target + synthesis subagent |
| `hooks/hyperstack-pretool.sh` | `~/.claude/hooks/` | PreToolUse hook blocking WebFetch/curl/playwright |
| `hooks/hyperstack-postcompact.sh` | `~/.claude/hooks/` | PostCompact hook for bd prime + team stats |
| `teams/hyperstack/config.json` | `~/.claude/teams/hyperstack/` | 5-member Agent Team (team-lead, frontliner, deep-diver, heavy-lifter, analyst) |
| `loop-hyperstack.md` | `~/.claude/loop-hyperstack.md` | `/loop` self-paced mode for autonomous bd queue processing |
| `cli/hyperfetch` | `~/.cts/bin/hyperfetch` | Single-binary 4-stage escalation CLI |

## One-Shot Install

```bash
cd ~/agent-token-saver
bash integration/install.sh
```

Or manually:

```bash
mkdir -p ~/.claude/{agents,hooks,skills,teams/hyperstack} ~/.cts/bin
cp integration/skills/hyperstack.md ~/.claude/skills/
cp integration/agents/*.md ~/.claude/agents/
cp integration/hooks/*.sh ~/.claude/hooks/
chmod +x ~/.claude/hooks/hyperstack-*.sh
cp integration/teams/hyperstack/config.json ~/.claude/teams/hyperstack/
cp integration/loop-hyperstack.md ~/.claude/
cp integration/cli/hyperfetch ~/.cts/bin/
chmod +x ~/.cts/bin/hyperfetch
```

## Settings.json Wiring

Add to `~/.claude/settings.json` under `hooks`:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "WebFetch|Bash",
        "hooks": [{
          "type": "command",
          "command": "bash \"/Users/$USER/.claude/hooks/hyperstack-pretool.sh\""
        }]
      }
    ],
    "PostCompact": [
      {
        "hooks": [{
          "type": "command",
          "command": "bash \"/Users/$USER/.claude/hooks/hyperstack-postcompact.sh\"",
          "async": true
        }]
      }
    ]
  }
}
```

## PATH

```bash
echo 'export PATH="$HOME/.cts/bin:$PATH"' >> ~/.zshrc
```

## Enable Agent Teams

```bash
# In your shell rc or ~/.claude/settings.json env block:
export CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1
```

Then in Claude Code:
```
/teams activate hyperstack
```

## How It Works (April 2026)

1. **PreToolUse Hook** intercepts `WebFetch` calls and raw `curl|wget https://...` in Bash. Blocks with an actionable nudge telling Claude to use `hyperfetch` + subagent instead. Override: `HYPERSTACK_BYPASS=1`.

2. **Skill Autoload** — The `hyperstack.md` skill is effort: low and auto-loads on any web-fetch-adjacent intent. It teaches Claude the primary commands, subagent routing, and team cache patterns.

3. **Subagent Dispatch** — When Claude delegates via `Task`, it picks the right tier:
   - `hyperstack-scraper` (Haiku 4.5) for bulk static work
   - `hyperstack-researcher` (Sonnet 4.6) for JS-heavy / auth flows
   - `hyperstack-heavy` (Opus 4.6) for hard-blocked or cross-source synthesis

4. **Agent Team** — When the user types `/teams activate hyperstack`, all 5 members come alive in tmux panes with parallel execution. The team-lead orchestrates via channel subscriptions.

5. **Worktree Isolation** — Each subagent runs in an isolated worktree via `isolation: "worktree"` (v2.1.49+), so parallel Hyperstack missions don't conflict.

6. **Loop Mode** — `/loop ~/.claude/loop-hyperstack.md` runs self-paced, pulling from `bd ready --label=research,scrape` and routing to the cheapest viable agent with budget guards.

7. **PostCompact Recovery** — After context compaction, the hook re-orients the agent with `bd ready`, `cts-team stats`, and a skill reminder.

## Token Math (Integrated Stack)

| Feature | Baseline | Hyperstack | Factor |
|---------|----------|------------|--------|
| Ad-hoc WebFetch | 15,000 tok | blocked → hyperfetch 200 tok | 75x |
| Bulk scrape (20 URLs, single dev) | 300,000 tok | 4,000 tok via scraper subagent | 75x |
| Same bulk scrape, 10-dev team | 3,000,000 tok | 4,000 tok (cache hit 99%) | 750x |
| Research 100 competitor pages | 1.5M tok | 20k tok | 75x |
| Autonomous `/loop` over 50 tickets | 7.5M tok | 100k tok | 75x |
| + catboost/gemma full stack | — | 1k tok | 7,500x |

Combined on repetitive team research → **10,000x+** territory.

## Testing the Install

```bash
# 1. Should be blocked
curl https://example.com
# Expected: hook error with "Use hyperfetch instead" nudge

# 2. Should pass through (localhost)
curl http://localhost:8000/health

# 3. Should work (bypass)
HYPERSTACK_BYPASS=1 curl -X POST https://api.example.com/data -d '{}'

# 4. Direct hyperfetch
hyperfetch https://example.com --team-ns test

# 5. Subagent dispatch (ask Claude Code)
# "Use the hyperstack-scraper subagent to fetch these 5 URLs..."
```

## Uninstall

```bash
rm ~/.claude/skills/hyperstack.md
rm ~/.claude/agents/hyperstack-*.md
rm ~/.claude/hooks/hyperstack-{pretool,postcompact}.sh
rm -rf ~/.claude/teams/hyperstack
rm ~/.claude/loop-hyperstack.md
rm ~/.cts/bin/hyperfetch
# Then edit ~/.claude/settings.json to remove the Hyperstack hook entries
```

## See Also

- `../HYPERSTACK.md` — Architecture, cost model, component reference
- `../README.md` — Main CTS project
- Anthropic Agent Teams docs: `~/.claude/cts/skills/claude-code-sdk/`
