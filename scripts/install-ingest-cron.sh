#!/usr/bin/env bash
# Install the daily CLI-log → Synapse ingest as a launchd job (macOS).
# Resolves the REAL python + script paths (a `command -v python3` alias will
# poison the plist and fail with exit 78), writes the plist, loads it.
#
# Usage:  bash scripts/install-ingest-cron.sh [--hour H] [--minute M]
#         launchctl unload ~/Library/LaunchAgents/de.supersynergy.synapse-cli-log-ingest.plist  # to remove

set -euo pipefail

HOUR=4 MIN=30
while [[ $# -gt 0 ]]; do
  case "$1" in
    --hour) HOUR="$2"; shift 2 ;;
    --minute) MIN="$2"; shift 2 ;;
    *) shift ;;
  esac
done

HERE="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")/.." && pwd)"
SCRIPT="$HERE/integration/cli/synapse-ingest-cli-logs.py"
[[ -f "$SCRIPT" ]] || { echo "ingest script not found: $SCRIPT" >&2; exit 1; }

# Resolve a REAL python binary — never a shell alias. Try python3.14, then a
# non-alias python3 on PATH.
PY=""
for c in python3.14 python3.13 python3; do
  p="$(command -v "$c" 2>/dev/null || true)"
  [[ -x "$p" ]] && { PY="$p"; break; }
done
[[ -n "$PY" ]] || { echo "no real python3 binary found" >&2; exit 1; }

BIN_PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
LABEL="de.supersynergy.synapse-cli-log-ingest"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
mkdir -p "$HOME/Library/LaunchAgents"

cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$PY</string>
    <string>$SCRIPT</string>
    <string>--since</string>
    <string>2</string>
  </array>
  <key>EnvironmentVariables</key>
  <dict><key>PATH</key><string>$BIN_PATH</string></dict>
  <key>StartCalendarInterval</key>
  <dict><key>Hour</key><integer>$HOUR</integer><key>Minute</key><integer>$MIN</integer></dict>
  <key>RunAtLoad</key><false/>
  <key>StandardOutPath</key><string>/tmp/synapse-cli-log-ingest.log</string>
  <key>StandardErrorPath</key><string>/tmp/synapse-cli-log-ingest.err</string>
</dict>
</plist>
EOF

plutil -lint "$PLIST" >/dev/null || { echo "plist invalid" >&2; exit 1; }
launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"
echo "installed: $LABEL (daily $HOUR:$(printf '%02d' "$MIN"), python=$PY)"
echo "test now:  launchctl start $LABEL   # then tail /tmp/synapse-cli-log-ingest.err"
