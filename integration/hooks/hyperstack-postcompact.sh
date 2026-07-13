#!/usr/bin/env bash
# PostCompact hook — after context compaction, refresh working state:
#  1. Run `bd prime` to restore Beads tracker
#  2. Print Hyperstack team savings
#  3. Remind agent of the skill
# Async, best-effort, never blocks the main thread.

set +e

LOG=/tmp/claude-hyperstack-postcompact.log
echo "[$(date +%Y-%m-%dT%H:%M:%S)] post-compact fired" >> "$LOG" 2>/dev/null

{
  echo ""
  echo "## Post-Compact Refresh"
  echo ""

  if command -v bd >/dev/null 2>&1; then
    echo "### Beads ready queue"
    bd ready 2>/dev/null | head -10 || echo "(bd ready failed)"
    echo ""
  fi

  if [[ -x "$HOME/agent-token-saver/plugins/team-sandbox.sh" && -f "$HOME/.claude/toolstack.db" ]]; then
    echo "### Hyperstack team savings (current session namespace)"
    bash "$HOME/agent-token-saver/plugins/team-sandbox.sh" stats 2>/dev/null | head -20 || echo "(sandbox stats unavailable)"
    echo ""
  fi

  echo "### Reminder"
  echo "- All web fetches go through \`hyperfetch\`, never \`WebFetch\`."
  echo "- DOM navigation via \`dsh --session <name>\`."
  echo "- Delegate bulk work to \`hyperstack-scraper\` / \`hyperstack-researcher\` / \`hyperstack-heavy\`."
  echo "- Skill: \`~/.claude/skills/hyperstack.md\`"
} 2>>"$LOG"

exit 0
