#!/usr/bin/env bash
# install-optimized.sh — All-in-one Claude Code token stack installer
# Installs: trafilatura · MLX models · qwen3 Ollama · seek · ayg · catboost
# Configures: gemma-gate · smart-fetch · sg · hooks · CLAUDE.md addon
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/Supersynergy/agent-token-saver/main/install-optimized.sh | bash
#   bash install-optimized.sh [--fast] [--skip-mlx] [--skip-ollama] [--model phi4|qwen3|gemma4e2b]
#
# Attribution:
#   caveman       https://github.com/JuliusBrussee/caveman
#   context-mode  https://github.com/mksglu/context-mode
#   trafilatura   https://github.com/adbar/trafilatura
#   mlx-lm        https://github.com/ml-explore/mlx-lm
#   seek          https://github.com/dualeai/seek
#   aygrep        https://github.com/hemeda3/aygrep
#   ripgrep       https://github.com/BurntSushi/ripgrep
#   RTK           https://github.com/rtk-ai/rtk
#   catboost      https://github.com/catboost/catboost
#   ast-grep      https://github.com/ast-grep/ast-grep
#   ripgrep-all   https://github.com/phiresky/ripgrep-all

set -euo pipefail

if [[ "${ATS_LEGACY_HEAVY:-0}" != "1" ]]; then
  echo "install-optimized.sh is a legacy heavy installer and is disabled by default." >&2
  echo "Use ./install-universal.sh --profile lean --agent auto" >&2
  echo "Set ATS_LEGACY_HEAVY=1 only after reviewing this file." >&2
  exit 2
fi

# ── Args ──────────────────────────────────────────────────────────────────────
FAST=0; SKIP_MLX=0; SKIP_OLLAMA=0; SKIP_SEEK=0; MODEL="qwen3"
for arg in "$@"; do
  case "$arg" in
    --fast)          FAST=1 ;;
    --skip-mlx)      SKIP_MLX=1 ;;
    --skip-ollama)   SKIP_OLLAMA=1 ;;
    --skip-seek)     SKIP_SEEK=1 ;;
    --model=*)       MODEL="${arg#--model=}" ;;
    --model)         shift; MODEL="${1:-qwen3}" ;;
  esac
done

# ── Colors ────────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GRN='\033[0;32m'; YLW='\033[1;33m'; BLU='\033[0;34m'; NC='\033[0m'
ok()   { echo -e "${GRN}✓${NC} $*"; }
warn() { echo -e "${YLW}!${NC} $*"; }
info() { echo -e "${BLU}→${NC} $*"; }
fail() { echo -e "${RED}✗${NC} $*"; }

echo ""
echo "╔═══════════════════════════════════════════════════════╗"
echo "║  Claude Code Token Stack — Optimized Installer        ║"
echo "║  Target: 88-93% token reduction per session           ║"
echo "╚═══════════════════════════════════════════════════════╝"
echo ""

# ── Detect platform ───────────────────────────────────────────────────────────
ARCH=$(uname -m)
OS=$(uname -s)
IS_APPLE_SILICON=0
if [[ "$OS" == "Darwin" && "$ARCH" == "arm64" ]]; then
  IS_APPLE_SILICON=1
  info "Apple Silicon detected — MLX acceleration available"
fi

PY=$(command -v python3.12 2>/dev/null || command -v python3 2>/dev/null || echo "")
if [[ -z "$PY" ]]; then
  fail "python3 not found. Install: brew install python@3.12"
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"

# ── 1. Python deps ────────────────────────────────────────────────────────────
info "Installing Python dependencies..."

install_py() {
  local pkg="$1"
  if "$PY" -c "import ${pkg%%[>=<]*}" 2>/dev/null; then
    ok "$pkg already installed"
    return
  fi
  "$PY" -m pip install "$pkg" --break-system-packages -q 2>/dev/null || \
  "$PY" -m pip install "$pkg" -q 2>/dev/null || \
  warn "Could not install $pkg"
  "$PY" -c "import ${pkg%%[>=<]*}" 2>/dev/null && ok "$pkg installed" || fail "$pkg install failed"
}

install_py trafilatura
install_py catboost
install_py curl_cffi
if [[ $IS_APPLE_SILICON -eq 1 && $SKIP_MLX -eq 0 ]]; then
  install_py mlx_lm
fi

# ── 2. CLI tools via Homebrew ─────────────────────────────────────────────────
if command -v brew &>/dev/null; then
  info "Installing CLI tools via Homebrew..."
  for tool in ripgrep ripgrep-all ast-grep; do
    if command -v "${tool%%-*}" &>/dev/null; then
      ok "$tool already installed"
    else
      brew install "$tool" -q && ok "$tool installed" || warn "$tool install failed"
    fi
  done

  # aygrep
  if ! command -v ayg &>/dev/null; then
    brew tap hemeda3/tap 2>/dev/null && brew install ayg -q && ok "aygrep installed" || warn "aygrep: install manually — brew install hemeda3/tap/ayg"
  else
    ok "aygrep already installed"
  fi
else
  warn "Homebrew not found — install rg/ast-grep/ayg manually"
fi

# ── 3. seek — SKIPPED (wrong tool on crates.io) ──────────────────────────────
# dualeai/seek (BM25 Go tool) is NOT on crates.io. `cargo install seek` installs
# yxshv/seek (app launcher) — wrong tool. Use ayg (indexed) instead.
warn "seek: SKIPPED — cargo install seek installs wrong tool (yxshv/seek). Use ayg instead."

# ── 4. RTK ────────────────────────────────────────────────────────────────────
if ! command -v rtk &>/dev/null; then
  if command -v cargo &>/dev/null; then
    info "Installing RTK..."
    cargo install rtk -q && ok "RTK installed" || warn "RTK install failed"
  fi
else
  ok "RTK already installed"
fi

# ── 5. MLX model ─────────────────────────────────────────────────────────────
if [[ $IS_APPLE_SILICON -eq 1 && $SKIP_MLX -eq 0 ]]; then
  info "Configuring MLX model..."

  case "$MODEL" in
    gemma4e2b)
      MLX_MODEL="mlx-community/gemma-4-e2b-it-4bit"
      MLX_FAST="mlx-community/Phi-4-mini-instruct-4bit"
      info "Model: gemma-4-e2b-it-4bit (~7GB, ~50ms, 97% quality) — highest quality"
      ;;
    qwen3)
      # NOTE: Qwen3-0.6B/1.7B NOT suitable for summarization — fails instruction following
      # Use Phi-4-mini-instruct instead (benchmarked 2026-04-16)
      MLX_MODEL="mlx-community/Phi-4-mini-instruct-4bit"
      MLX_FAST="mlx-community/Phi-4-mini-instruct-4bit"
      warn "Qwen3 models fail instruction-following for summarization. Using Phi-4-mini-instruct instead."
      info "Model: Phi-4-mini-instruct-4bit (2.2GB, 556ms, 94% quality)"
      ;;
    phi4|*)
      # DEFAULT — benchmarked best: 118t→55t (-53%), proper structured output
      MLX_MODEL="mlx-community/Phi-4-mini-instruct-4bit"
      MLX_FAST="mlx-community/Phi-4-mini-instruct-4bit"
      info "Model: Phi-4-mini-instruct-4bit (2.2GB, 556ms warm, 94% quality) ← RECOMMENDED"
      info "  Benchmark: 118t→55t (-53%), correct structured output (2026-04-16, M4 Max)"
      ;;
  esac

  # Pre-download fast model (small, quick)
  info "Pre-downloading $MLX_FAST (fast model, ~350MB)..."
  "$PY" -c "
from mlx_lm import load
try:
    load('$MLX_FAST')
    print('[mlx] $MLX_FAST cached')
except Exception as e:
    print(f'[mlx] cache failed: {e}')
" 2>/dev/null && ok "MLX fast model cached" || warn "MLX fast model: will download on first use"

  if [[ $FAST -eq 0 ]]; then
    info "Pre-downloading $MLX_MODEL (quality model)..."
    "$PY" -c "
from mlx_lm import load
try:
    load('$MLX_MODEL')
    print('[mlx] $MLX_MODEL cached')
except Exception as e:
    print(f'[mlx] cache failed: {e}')
" 2>/dev/null && ok "MLX quality model cached" || warn "MLX quality model: will download on first use"
  fi

  # Write env config
  ENV_FILE="$HOME/.claude/cts-env.sh"
  cat > "$ENV_FILE" << EOF
# CTS MLX Configuration — auto-generated by install-optimized.sh
export CTS_MLX_MODEL="$MLX_MODEL"
export CTS_MLX_FAST_MODEL="$MLX_FAST"
export CTS_GEMMA_THRESHOLD="200"
export CTS_FORCE_LLM="0"
export CTS_CATBOOST="0"
EOF
  ok "MLX config written → $ENV_FILE"
fi

# ── 6. Ollama model ───────────────────────────────────────────────────────────
if [[ $SKIP_OLLAMA -eq 0 ]] && command -v ollama &>/dev/null; then
  info "Pulling qwen3:0.6b (Ollama fallback, 400MB)..."
  ollama pull qwen3:0.6b 2>/dev/null && ok "qwen3:0.6b pulled" || warn "Ollama pull failed — run: ollama pull qwen3:0.6b"
fi

# ── 7. Install fused tools ────────────────────────────────────────────────────
info "Installing fused tools (smart-fetch, sg)..."
BIN_DIR="$HOME/.local/bin"
mkdir -p "$BIN_DIR"

# smart-fetch
SMARTFETCH_SRC="$SCRIPT_DIR/integration/cli/smart-fetch"
if [[ ! -f "$SMARTFETCH_SRC" ]]; then
  SMARTFETCH_SRC="$HOME/.local/bin/smart-fetch"
fi
if [[ -f "$SMARTFETCH_SRC" ]]; then
  cp "$SMARTFETCH_SRC" "$BIN_DIR/smart-fetch"
  chmod +x "$BIN_DIR/smart-fetch"
  ok "smart-fetch → $BIN_DIR/smart-fetch"
fi

# sg (smart grep)
SG_SRC="$SCRIPT_DIR/integration/cli/sg"
if [[ ! -f "$SG_SRC" ]]; then SG_SRC="$HOME/.local/bin/sg"; fi
if [[ -f "$SG_SRC" ]]; then
  cp "$SG_SRC" "$BIN_DIR/sg"
  chmod +x "$BIN_DIR/sg"
  ok "sg → $BIN_DIR/sg"
fi

# gemma-gate
cp "$SCRIPT_DIR/core/gemma-gate.py" "$BIN_DIR/gemma-gate"
chmod +x "$BIN_DIR/gemma-gate"
ok "gemma-gate → $BIN_DIR/gemma-gate"

# ── 8. Claude Code plugins ────────────────────────────────────────────────────
if command -v claude &>/dev/null; then
  info "Installing Claude Code plugins..."
  claude plugin marketplace add JuliusBrussee/caveman 2>/dev/null && \
    claude plugin install caveman@caveman 2>/dev/null && ok "caveman plugin installed" || \
    warn "caveman: run manually — claude plugin marketplace add JuliusBrussee/caveman"
  claude plugin marketplace add mksglu/context-mode 2>/dev/null && \
    claude plugin install context-mode@context-mode 2>/dev/null && ok "context-mode plugin installed" || \
    warn "context-mode: run manually — claude plugin marketplace add mksglu/context-mode"
fi

# ── 9. CLAUDE.md addon ────────────────────────────────────────────────────────
info "Writing CLAUDE.md addon..."
CLAUDE_ADDON="$HOME/.claude/token-stack.md"
cat > "$CLAUDE_ADDON" << 'CLAUDEMD'
# Token Optimization Stack

## Tool Routing (fastest → slowest)

### Web Fetch
```
Small API (/json /health /ping /api/*)  → rtk curl -s <url>         = 39t, 890ms
HTML article/doc                         → smart-fetch <url>          = 35t, 200ms (trafilatura, 0 LLM)
Anti-bot target                          → hyperfetch --stage camoufox = 153t, 3.3s
Specific fact from page                  → hyperfetch --extract "X"   = 5-12t
```

### Code Search
```
Any pattern search                       → sg <pattern>               (seek→ayg→rg auto-route)
Structural (function/class pattern)      → ast-grep -p 'pattern'
Symbol search                            → sg sym:ClassName
PDF/archive search                       → rga "term"
```

### Context Protection
```
2+ commands/queries                      → ctx_batch_execute (ONE call, 98% reduction)
Follow-up search                         → ctx_search
WebFetch                                 → ctx_fetch_and_index
```

### Output
```
caveman:full active                      → 65% output token reduction (automatic)
caveman:ultra                            → 75% (for non-critical tasks)
stop caveman                             → normal mode
```

## NEVER use these (benchmarked WORSE)
```
rtk ls    → +35% MORE tokens  → use Glob tool
rtk grep  → +10000% overhead  → use Grep tool / sg
rtk env   → +105% MORE bytes  → use env | grep
rtk read  → +412% MORE tokens → use Read tool
raw cat   → use Read tool
find      → use Glob tool
```

## Gemma Gate (HTML→token compression)
Pipeline: trafilatura (0ms) → MLX Qwen3 (~12-35ms) → Ollama qwen3:0.6b (~50ms) → extractive fallback
Config: source ~/.claude/cts-env.sh

## Cost Reference
```
ctx_batch_execute : 500t ($0.001 Sonnet)
spawn Agent       : 30,000t ($0.09 Sonnet / $0.45 Opus)
→ ctx_batch first. 60x cheaper than research agents.
```
CLAUDEMD

ok "CLAUDE.md addon → $CLAUDE_ADDON"

# ── 10. Verify ────────────────────────────────────────────────────────────────
echo ""
echo "╔═══════════════════════════════════════════════════════╗"
echo "║  Installation Complete — Stack Verification           ║"
echo "╚═══════════════════════════════════════════════════════╝"

check() {
  local name="$1"; local cmd="$2"; local hint="$3"
  if eval "$cmd" &>/dev/null; then
    ok "$name"
  else
    warn "$name — $hint"
  fi
}

check "trafilatura"     "$PY -c 'import trafilatura'"          "pip install trafilatura"
check "catboost"        "$PY -c 'import catboost'"             "pip install catboost"
check "curl_cffi"       "$PY -c 'import curl_cffi'"            "pip install curl_cffi"
check "mlx-lm"          "$PY -c 'import mlx_lm'"              "pip install mlx-lm (Apple Silicon only)"
check "ripgrep (rg)"   "command -v rg"                         "brew install ripgrep"
check "ripgrep-all (rga)" "command -v rga"                     "brew install ripgrep-all"
check "ast-grep"        "command -v ast-grep"                  "brew install ast-grep"
check "aygrep (ayg)"   "command -v ayg"                        "brew install hemeda3/tap/ayg"
# seek SKIPPED — wrong tool on crates.io, use ayg instead
check "RTK"             "command -v rtk"                       "cargo install rtk"
check "Ollama"          "command -v ollama"                    "brew install ollama"
check "smart-fetch"     "command -v smart-fetch"               "copy to ~/.local/bin/"
check "sg"              "command -v sg"                        "copy to ~/.local/bin/"

echo ""
info "Add to shell: source ~/.claude/cts-env.sh"
info "Add to CLAUDE.md: cat ~/.claude/token-stack.md >> ~/.claude/CLAUDE.md"
echo ""
echo "  Stack savings: caveman(65%) + context-mode(98%) + RTK(62%) = 88-93% total"
echo ""
