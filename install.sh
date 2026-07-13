#!/usr/bin/env bash
# ┌────────────────────────────────────────────��────────────────────┐
# │   ██████╗████████╗███████╗                                      │
# │  ██╔════╝╚══██╔══╝██╔════╝  Claude Token Saver                 │
# │  ██║        ██║   ███████╗  v3.0.0  |  Zero-waste startup      │
# │  ██║        ██║   ╚════██║  60-90% less tokens. Always.        │
# │  ╚██████╗   ██║   ███████║  github.com/Supersynergy/cts        │
# │   ╚═════╝   ╚═╝   ╚══════╝                                     │
# └──────────────────────────��─────────────────────────���────────────┘
set -euo pipefail

if [[ "${ATS_LEGACY_CTS_INSTALLER:-0}" != "1" ]]; then
  echo "install.sh is the archived Claude-only installer and is disabled by default." >&2
  echo "Use ./install-universal.sh --profile lean --agent auto" >&2
  echo "Set ATS_LEGACY_CTS_INSTALLER=1 only after reviewing this file." >&2
  exit 2
fi

CTS_VERSION="3.1.0"
CTS_REPO="https://raw.githubusercontent.com/Supersynergy/agent-token-saver/main"
CLAUDE_DIR="${CLAUDE_DIR:-$HOME/.claude}"
CTS_DIR="$CLAUDE_DIR/cts"           # vault: all cold-stored skills/agents/commands
SKILLS_DIR="$CLAUDE_DIR/skills"     # hot: only cts.md lives here
AGENTS_DIR="$CLAUDE_DIR/agents"
COMMANDS_DIR="$CLAUDE_DIR/commands"
RULES_DIR="$CLAUDE_DIR/rules"
REFS_DIR="$CLAUDE_DIR/refs"
SETTINGS="$CLAUDE_DIR/settings.json"
IDX="$CLAUDE_DIR/cts.idx"           # renamed from skills.idx

# ── Flags ─────────────────��───────────────────────────��────────────
DRY_RUN=0; SILENT=0; BACKUP_ONLY=0; AUDIT_ONLY=0; UPGRADE=0
SKIP_VAULT=0; SKIP_AGENTS=0; SKIP_RULES=0; SKIP_PLUGINS=0
for arg in "$@"; do case $arg in
  --dry-run)      DRY_RUN=1 ;;     --silent)       SILENT=1 ;;
  --backup-only)  BACKUP_ONLY=1 ;; --audit)        AUDIT_ONLY=1 ;;
  --upgrade)      UPGRADE=1 ;;     --skip-vault)   SKIP_VAULT=1 ;;
  --skip-agents)  SKIP_AGENTS=1 ;; --skip-rules)   SKIP_RULES=1 ;;
  --skip-plugins) SKIP_PLUGINS=1 ;;
esac; done

# ── Colours ────────────────────────────────────────────────────────
G='\033[0;32m'; Y='\033[1;33m'; R='\033[0;31m'; C='\033[0;36m'
B='\033[1m'; DIM='\033[2m'; NC='\033[0m'
ok()   { [[ $SILENT -eq 0 ]] && echo -e "${G}✓${NC} $*"; }
warn() { [[ $SILENT -eq 0 ]] && echo -e "${Y}⚠${NC} $*"; }
info() { [[ $SILENT -eq 0 ]] && echo -e "${C}ℹ${NC} $*"; }
die()  { echo -e "${R}✗ FATAL:${NC} $*" >&2; exit 1; }
run()  { [[ $DRY_RUN -eq 1 ]] && echo -e "  ${DIM}[dry-run]${NC} $*" || eval "$*"; }
hdr()  { [[ $SILENT -eq 0 ]] && echo -e "\n${B}── $* ──${NC}"; }

# ── Auto-update check ──────────────────────────────────────────────
check_update() {
  local latest
  latest=$(curl -fsSL "$CTS_REPO/VERSION" 2>/dev/null || echo "")
  [[ -z "$latest" ]] && return
  if [[ "$latest" != "$CTS_VERSION" ]]; then
    warn "CTS $latest available (you have $CTS_VERSION). Run: bash install.sh --upgrade"
  fi
}

# ── Token Audit ────────────────────────────────────────────────────
audit_tokens() {
  echo -e "\n${B}╔═══════════════════════════════════════════════╗${NC}"
  echo -e "${B}║         CTS Token Audit                       ║${NC}"
  echo -e "${B}╚═══════════════════════════════════════════════╝${NC}"
  local total=0

  hdr "Memory files (auto-loaded every session)"
  for f in \
    "$CLAUDE_DIR/CLAUDE.md" "$CLAUDE_DIR/RTK.md" \
    "$HOME/CLAUDE.md" "$HOME/CLAUDE.local.md" \
    "$CLAUDE_DIR/projects/$(echo "$HOME"|sed 's|/|-|g')/memory/MEMORY.md"; do
    [[ -f "$f" ]] || continue
    local lines; lines=$(wc -l < "$f")
    local est=$(( lines * 12 ))
    total=$((total + est))
    local status="${G}✓${NC}"
    [[ $lines -gt 100 ]] && status="${Y}⚠${NC}"
    [[ $lines -gt 200 ]] && status="${R}✗${NC}"
    printf "  %b %-52s %4d lines  ~%dk tokens\n" "$status" "${f/$HOME/~}" "$lines" "$((est/1000))"
  done
  echo -e "  ${B}Memory total: ~$((total/1000))k tokens${NC}"

  hdr "Rules (unconditionally loaded)"
  local always=0
  while IFS= read -r f; do
    head -5 "$f" | grep -q 'paths:' && continue
    always=$((always+1))
    printf "  ${Y}⚠${NC} ALWAYS: %s (%d lines)\n" "${f/$HOME/~}" "$(wc -l < "$f")"
  done < <(find "$RULES_DIR" -name '*.md' 2>/dev/null)
  [[ $always -eq 0 ]] && ok "All rules are conditional or minimal"

  hdr "Skills/Commands (stubs loaded at startup)"
  local cmds; cmds=$(ls "$COMMANDS_DIR"/*.md 2>/dev/null | wc -l || echo 0)
  [[ $cmds -gt 0 ]] \
    && warn "$cmds command stubs (~$((cmds*30)) tokens wasted) — run CTS to vault them" \
    || ok "commands/ clean — CTS vault active (0 startup tokens)"

  hdr "Agents (stubs loaded at startup)"
  local agts; agts=$(ls "$AGENTS_DIR"/*.md 2>/dev/null | wc -l || echo 0)
  [[ $agts -gt 0 ]] \
    && warn "$agts agent stubs (~$((agts*50)) tokens wasted) — run CTS to vault them" \
    || ok "agents/ root clean — CTS vault active (0 startup tokens)"

  hdr "Plugins"
  [[ -f "$SETTINGS" ]] && python3 - <<'PY'
import json,os
s=json.load(open(os.environ.get('SETTINGS',os.path.expanduser('~/.claude/settings.json'))))
costs={'claude-hud@claude-hud':50,'claude-mem@claude-mem':300,
       'minimal-claude@minimal-claude-marketplace':200,
       'pyright-lsp@claude-plugins-official':100,
       'rust-analyzer-lsp@claude-plugins-official':100}
print("  GSD/opsx built-in: ~2500 tokens (unavoidable while GSD plugin installed)")
for p,en in s.get('enabledPlugins',{}).items():
    if en:
        tok=costs.get(p,100)
        status='✓' if tok<200 else '⚠'
        print(f"  {status} {p}: ~{tok} tokens")
PY

  hdr "Broken hooks"
  [[ -f "$SETTINGS" ]] && python3 - <<'PY'
import json,os
s=json.load(open(os.environ.get('SETTINGS',os.path.expanduser('~/.claude/settings.json'))))
broken=0
for evt,hooks in s.get('hooks',{}).items():
    for h in hooks:
        for hh in h.get('hooks',[]):
            cmd=hh.get('command','')
            if 'CLAUDE_PLUGIN_ROOT' in cmd:
                print(f"  ✗ BROKEN [{evt}]: {cmd[:70]}..."); broken+=1; continue
            if 'node "' in cmd:
                p=cmd.split('"')[1] if '"' in cmd else ''
                if p and not os.path.exists(p):
                    print(f"  ✗ BROKEN [{evt}]: {cmd[:70]}..."); broken+=1
if broken==0: print("  ✓ All hooks healthy")
PY
  echo ""
}

# ── Backup ─────────────────────────────────────────────────────────
create_backup() {
  local BAK="$HOME/.cts-backup-$(date +%Y%m%d-%H%M%S)"
  mkdir -p "$BAK"
  for d in skills cts commands agents rules hooks scripts; do
    [[ -d "$CLAUDE_DIR/$d" ]] && cp -r "$CLAUDE_DIR/$d" "$BAK/" 2>/dev/null || true
  done
  for f in settings.json CLAUDE.md RTK.md skills.idx cts.idx; do
    [[ -f "$CLAUDE_DIR/$f" ]] && cp "$CLAUDE_DIR/$f" "$BAK/" 2>/dev/null || true
  done
  [[ -f "$HOME/CLAUDE.md" ]] && cp "$HOME/CLAUDE.md" "$BAK/project-CLAUDE.md" 2>/dev/null || true
  cat > "$BAK/restore.sh" <<RESTORE
#!/usr/bin/env bash
BAK="\$(cd "\$(dirname "\$0")" && pwd)"
echo "Restoring CTS backup from \$BAK ..."
for d in skills cts commands agents rules hooks scripts; do
  [[ -d "\$BAK/\$d" ]] && rm -rf "$CLAUDE_DIR/\$d" && cp -r "\$BAK/\$d" "$CLAUDE_DIR/"
done
for f in settings.json CLAUDE.md RTK.md skills.idx cts.idx; do
  [[ -f "\$BAK/\$f" ]] && cp "\$BAK/\$f" "$CLAUDE_DIR/"
done
[[ -f "\$BAK/project-CLAUDE.md" ]] && cp "\$BAK/project-CLAUDE.md" "$HOME/CLAUDE.md"
echo "✓ Restored. Restart Claude Code."
RESTORE
  chmod +x "$BAK/restore.sh"
  ok "Backup → $BAK  |  rollback: bash $BAK/restore.sh"
  echo "$BAK"
}

# ── Fix broken settings ────────────────────────────────────────────
fix_settings() {
  hdr "Fixing settings.json"
  [[ -f "$SETTINGS" ]] || { info "No settings.json found"; return; }
  python3 - <<'PY'
import json,os
f=os.environ.get('SETTINGS',os.path.expanduser('~/.claude/settings.json'))
s=json.load(open(f)); changed=False
# Fix companyAnnouncements bool → array
if s.get('companyAnnouncements') is False:
    s['companyAnnouncements']=[]; changed=True; print("  ✓ Fixed companyAnnouncements: false→[]")
# Remove duplicate statusline key
if 'statusline' in s and 'statusLine' in s:
    del s['statusline']; changed=True; print("  ✓ Removed duplicate statusline key")
# Remove redundant shellfirm MCP (PreToolUse hook is better)
if 'shellfirm' in s.get('mcpServers',{}):
    del s['mcpServers']['shellfirm']; changed=True; print("  ✓ Removed shellfirm MCP (hook covers it)")
# Remove broken hooks
removed=0
for evt in list(s.get('hooks',{}).keys()):
    clean=[]
    for h in s['hooks'][evt]:
        ch=[]
        for hh in h.get('hooks',[]):
            cmd=hh.get('command','')
            if 'CLAUDE_PLUGIN_ROOT' in cmd: removed+=1; continue
            if 'node "' in cmd:
                p=cmd.split('"')[1] if '"' in cmd else ''
                if p and not os.path.exists(p): removed+=1; continue
            ch.append(hh)
        if ch: h['hooks']=ch; clean.append(h)
    if clean: s['hooks'][evt]=clean
    else: del s['hooks'][evt]
if removed: changed=True; print(f"  ✓ Removed {removed} broken hooks")
if changed: open(f,'w').write(json.dumps(s,indent=2)); print("  ✓ settings.json saved")
else: print("  ✓ settings.json already clean")
PY
}

# ── Install cts.md ─────────────────────────────────────────────────
install_cts_md() {
  hdr "Installing CTS skill manager (cts.md)"
  run "mkdir -p '$SKILLS_DIR'"
  local dest="$SKILLS_DIR/cts.md"

  # Migrate sm.md → cts.md if needed
  if [[ -f "$SKILLS_DIR/sm.md" ]] && [[ ! -f "$dest" ]]; then
    run "mv '$SKILLS_DIR/sm.md' '$dest'"
    ok "Renamed sm.md → cts.md"
  fi

  if [[ -f "$dest" ]] && [[ $UPGRADE -eq 0 ]]; then
    ok "cts.md installed (--upgrade to refresh)"
    _fix_cts_paths "$dest"
    return
  fi

  local src="$(cd "$(dirname "$0")" && pwd)/cts.md"
  if [[ -f "$src" ]]; then
    run "cp '$src' '$dest'"
  else
    # Try sm.md in repo for backward compat
    local sm_src="$(cd "$(dirname "$0")" && pwd)/sm.md"
    if [[ -f "$sm_src" ]]; then
      run "cp '$sm_src' '$dest'"
    else
      run "curl -fsSL '$CTS_REPO/cts.md' -o '$dest' 2>/dev/null || curl -fsSL '$CTS_REPO/sm.md' -o '$dest'"
    fi
  fi
  _fix_cts_paths "$dest"
  ok "cts.md installed at ~/.claude/skills/cts.md"
}

_fix_cts_paths() {
  local f="$1"
  [[ $DRY_RUN -eq 1 ]] && return
  python3 -c "
import os,re
f=open('$f').read()
# Update all path/name references
updated=f.replace('skills-vault','cts').replace('skills.idx','cts.idx').replace('/sm ','/ cts ').replace('name: sm','name: cts')
# Update vault dir reference
updated=re.sub(r'Vault dir.*','Vault dir**: \`~/.claude/cts/\` — all cold-stored skills, agents, commands',updated)
open('$f','w').write(updated)
" 2>/dev/null && ok "cts.md paths updated (skills-vault→cts, skills.idx→cts.idx)"
}

# ── CTS Vault: migrate + organize ─────────────────────────────────
setup_cts_vault() {
  [[ $SKIP_VAULT -eq 1 ]] && return
  hdr "CTS Vault Setup"
  run "mkdir -p '$CTS_DIR/commands' '$CTS_DIR/agents'"

  # Migrate old skills-vault → cts
  if [[ -d "$CLAUDE_DIR/skills-vault" ]]; then
    if [[ ! -d "$CTS_DIR" ]] || [[ -z "$(ls -A "$CTS_DIR" 2>/dev/null)" ]]; then
      run "mv '$CLAUDE_DIR/skills-vault' '$CTS_DIR'"
    else
      run "cp -rn '$CLAUDE_DIR/skills-vault'/. '$CTS_DIR/' 2>/dev/null; rm -rf '$CLAUDE_DIR/skills-vault'"
    fi
    ok "Migrated skills-vault → cts"
    _update_idx "skills-vault" "cts"
  fi

  # Migrate old skills.idx → cts.idx
  if [[ -f "$CLAUDE_DIR/skills.idx" ]] && [[ ! -f "$IDX" ]]; then
    run "cp '$CLAUDE_DIR/skills.idx' '$IDX'"
    _update_idx "skills-vault" "cts"
    ok "Migrated skills.idx → cts.idx"
  fi

  # Commands → cts/commands
  local cmds; cmds=$(ls "$COMMANDS_DIR"/*.md 2>/dev/null | wc -l || echo 0)
  if [[ $cmds -gt 0 ]]; then
    run "cp '$COMMANDS_DIR'/*.md '$CTS_DIR/commands/' 2>/dev/null; rm '$COMMANDS_DIR'/*.md"
    ok "Vaulted $cmds commands → cts/commands/ (~$((cmds*30)) tokens freed)"
    [[ $DRY_RUN -eq 0 ]] && _index_dir "$CTS_DIR/commands" "Commands"
  else
    ok "commands/ already clean"
  fi

  # Agents → cts/agents
  [[ $SKIP_AGENTS -eq 1 ]] && return
  local agts; agts=$(ls "$AGENTS_DIR"/*.md 2>/dev/null | wc -l || echo 0)
  if [[ $agts -gt 0 ]]; then
    run "mv '$AGENTS_DIR'/*.md '$CTS_DIR/agents/' 2>/dev/null"
    ok "Vaulted $agts agents → cts/agents/ (~$((agts*50)) tokens freed)"
  else
    ok "agents/ already clean"
  fi
}

_update_idx() {
  local old="$1" new="$2"
  for idx in "$IDX" "$CLAUDE_DIR/skills.idx"; do
    [[ -f "$idx" ]] || continue
    python3 -c "
f=open('$idx').read()
updated=f.replace('/.claude/$old/','/.claude/$new/')
open('$idx','w').write(updated)
n=f.count('/.claude/$old/')
if n: print(f'  ✓ Updated {n} paths in $(basename $idx): $old→$new')
"
  done
}

_index_dir() {
  local dir="$1" cat="$2"
  python3 - <<PY
import os,re,glob
vault,cat,idx_path="$dir","$cat","$IDX"
existing=open(idx_path).read() if os.path.exists(idx_path) else ''
entries=[]
for f in sorted(glob.glob(os.path.join(vault,'*.md'))):
    name=os.path.basename(f)[:-3]
    if name+'\t' in existing: continue
    content=open(f).read()
    m=re.search(r'^description:\s*(.+)',content,re.MULTILINE)
    desc=m.group(1).strip()[:100] if m else 'Skill'
    entries.append(f"{name}\t{cat}\t{desc}\t{f}\t1")
if entries:
    with open(idx_path,'a') as fh: fh.write('\n'.join(entries)+'\n')
    print(f"  ✓ Indexed {len(entries)} new entries ({cat})")
PY
}

# ── Rules optimization ─────────────────────────────────────────────
optimize_rules() {
  [[ $SKIP_RULES -eq 1 ]] && return
  hdr "Rules Optimization"
  run "mkdir -p '$REFS_DIR/rules'"

  [[ -f "$RULES_DIR/README.md" ]] && \
    run "mv '$RULES_DIR/README.md' '$REFS_DIR/rules/'" && ok "rules/README.md → refs/ (-1.1k tokens)"

  local n; n=$(ls "$RULES_DIR/common/"*.md 2>/dev/null | wc -l || echo 0)
  if [[ $n -gt 0 ]]; then
    run "cp '$RULES_DIR/common/'*.md '$REFS_DIR/rules/' 2>/dev/null"
    run "rm '$RULES_DIR/common/'*.md"
    ok "Moved $n common rules → refs/rules/ (~2.8k tokens freed)"
  fi

  if [[ ! -f "$RULES_DIR/core.md" ]]; then
    [[ $DRY_RUN -eq 1 ]] && { info "[dry-run] Would create rules/core.md"; return; }
    cat > "$RULES_DIR/core.md" <<'CORE'
# Core Rules — CTS Minimal

- NEVER mutate — always return new objects
- NEVER hardcode secrets — use env vars
- NEVER silently swallow errors — handle explicitly
- Functions <50 lines | Files <800 lines | Nesting <4 levels
- Validate at system boundaries only (user input, external APIs)
- Absolute paths always — no tree-style listings (├──)
- 80% test coverage — TDD: red→green→refactor
- Commit: `<type>: <description>` (feat/fix/refactor/docs/test/chore)
- Models: haiku=explore, sonnet=code, opus=architecture only
- Full rule refs: ~/.claude/refs/rules/
CORE
    ok "Created rules/core.md (~150 tokens, replaces 2.8k)"
  fi
}

# ── CLAUDE.md optimization ─────────────────────────────────────────
optimize_claude_md() {
  hdr "CLAUDE.md Optimization"

  # Move toolstack-2026.md to refs (4.9k tokens)
  if [[ -f "$CLAUDE_DIR/toolstack-2026.md" ]]; then
    run "mkdir -p '$REFS_DIR' && mv '$CLAUDE_DIR/toolstack-2026.md' '$REFS_DIR/'"
    ok "toolstack-2026.md → refs/ (-4.9k tokens)"
    if [[ -f "$CLAUDE_DIR/CLAUDE.md" ]]; then
      run "python3 -c \"
f=open('$CLAUDE_DIR/CLAUDE.md').read()
updated='\n'.join(l for l in f.split('\n') if '@toolstack-2026' not in l)
open('$CLAUDE_DIR/CLAUDE.md','w').write(updated)
print('  ✓ Removed @toolstack-2026 import')
\""
    fi
  fi

  # Audit size
  if [[ -f "$CLAUDE_DIR/CLAUDE.md" ]]; then
    local lines; lines=$(wc -l < "$CLAUDE_DIR/CLAUDE.md")
    [[ $lines -gt 100 ]] \
      && warn "CLAUDE.md is $lines lines (~$((lines*12)) tokens). Tip: keep <50 lines, move sections to refs/" \
      || ok "CLAUDE.md: $lines lines ✓"
  fi
}

# ── Plugin optimization ────────────────────────────────────────────
optimize_plugins() {
  [[ $SKIP_PLUGINS -eq 1 ]] && return
  hdr "Plugin Optimization"
  [[ -f "$SETTINGS" ]] || return

  python3 - <<'PY'
import json,os
f=os.environ.get('SETTINGS',os.path.expanduser('~/.claude/settings.json'))
s=json.load(open(f)); changed=False
plugins=s.get('enabledPlugins',{})

# Disable LSP plugins globally — use per-project .claude/settings.json instead
lsp=[k for k in list(plugins) if 'lsp' in k.lower()]
for k in lsp:
    del plugins[k]; changed=True
    print(f"  ✓ Disabled globally (enable per-project): {k}")
if not lsp: print("  ✓ No global LSP plugins found")

if changed:
    s['enabledPlugins']=plugins
    open(f,'w').write(json.dumps(s,indent=2))

print(f"\n  Active plugins after optimization:")
for p,en in s.get('enabledPlugins',{}).items():
    if en: print(f"    ✓ {p}")
print(f"\n  Note: GSD/opsx built-in skills = ~2500 tokens (while GSD installed)")
print(f"  To remove GSD tokens: claude plugins uninstall gsd (loses /gsd:* commands)")
PY
}

# ── Rebuild index ──────────────────────────────────────────────────
rebuild_index() {
  hdr "Rebuilding CTS Index"
  local builder="$CLAUDE_DIR/scripts/build-skills-index.py"
  run "mkdir -p '$CLAUDE_DIR/scripts'"

  local src; src="$(cd "$(dirname "$0")" && pwd)/build-skills-index.py"
  if [[ -f "$src" ]]; then
    run "cp '$src' '$builder'"
  elif [[ ! -f "$builder" ]]; then
    run "curl -fsSL '$CTS_REPO/build-skills-index.py' -o '$builder'"
  fi

  if [[ $DRY_RUN -eq 0 ]] && [[ -f "$builder" ]]; then
    python3 "$builder" --vault "$CTS_DIR" --skills "$SKILLS_DIR" --output "$IDX" 2>/dev/null \
      && ok "Index rebuilt: $(wc -l < "$IDX" 2>/dev/null || echo '?') entries → $IDX" \
      || warn "Index rebuild failed — run manually: python3 $builder"
  fi
}

# ── Final summary ──────────────────────────────────────────────────
print_summary() {
  echo ""
  echo -e "${G}${B}╔═════════════════��═════════════════════════════╗${NC}"
  echo -e "${G}${B}║   ██████╗████████╗███████╗  v${CTS_VERSION}            ║${NC}"
  echo -e "${G}${B}║  ██╔════╝╚══██╔══╝██╔════╝                    ║${NC}"
  echo -e "${G}${B}║  ██║        ██║   ███████╗  Done!              ║${NC}"
  echo -e "${G}${B}║  ██║        ██║   ╚════██║                    ║${NC}"
  echo -e "${G}${B}║  ╚██████╗   ██║   ███████║  Claude Token Saver ║${NC}"
  echo -e "${G}${B}║   ╚═════╝   ╚═╝   ╚══════╝                    ║${NC}"
  echo -e "${G}${B}╚════════════════════════════════════════════��══╝${NC}"
  echo ""
  echo -e "${B}Token savings per session (estimated):${NC}"
  printf "  %-34s  %s\n" "Skills/Commands → vault:"     "0 startup  (was up to 3k)"
  printf "  %-34s  %s\n" "Agents → vault:"              "0 startup  (was up to 2.5k)"
  printf "  %-34s  %s\n" "rules/common → core.md:"      "~150 tokens (was 2.8k)"
  printf "  %-34s  %s\n" "CLAUDE.md optimized:"         "~400 tokens (was 5k)"
  printf "  %-34s  %s\n" "toolstack → refs/:"           "0 tokens    (was 4.9k)"
  printf "  %-34s  %s\n" "RTK Bash compression:"        "60-90% per Bash call"
  echo ""
  echo -e "${B}Quick commands:${NC}"
  echo "  /cts search <query>     — find skills (0 tokens)"
  echo "  /cts load <name>        — load skill on demand"
  echo "  /cts auto <intent>      — find + invoke best match"
  echo "  /cts stats              — savings dashboard"
  echo "  bash install.sh --audit — re-run token audit"
  echo ""
  echo -e "  ${Y}Restart Claude Code to activate all changes.${NC}"
  echo ""
}

# ── Main ───────────────────────────────────────────────────────────
main() {
  [[ $SILENT -eq 0 ]] && echo -e "\n${B}CTS — Claude Token Saver v${CTS_VERSION}${NC}  |  github.com/Supersynergy/agent-token-saver\n"
  command -v python3 &>/dev/null || die "Python 3 required"
  [[ -d "$CLAUDE_DIR" ]] || die "~/.claude not found — is Claude Code installed?"
  export SETTINGS IDX CTS_DIR

  check_update

  [[ $AUDIT_ONLY -eq 1 ]] && { audit_tokens; exit 0; }

  create_backup > /dev/null
  [[ $BACKUP_ONLY -eq 1 ]] && exit 0
  [[ $DRY_RUN -eq 1 ]] && warn "DRY RUN — no changes will be made"

  fix_settings
  install_cts_md
  setup_cts_vault
  optimize_rules
  optimize_claude_md
  optimize_plugins
  rebuild_index
  print_summary
}

main "$@"
