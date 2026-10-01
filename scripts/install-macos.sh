#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BIN_DIR="$HOME/.local/bin"
APP_DIR="$HOME/Library/Application Support/agent-status-indicator"
DESKTOP_DIR="$APP_DIR/desktop"

mkdir -p "$BIN_DIR" "$DESKTOP_DIR"
for script in agent-status agent-status-hook codex-status-exec agent-status-desktop; do
  install -m 0755 "$ROOT/bin/$script" "$BIN_DIR/$script"
done
install -m 0644 "$ROOT/desktop/agent_status_desktop.py" "$DESKTOP_DIR/agent_status_desktop.py"

echo "Installed Agent Status Indicator to $APP_DIR"
echo "Add this directory to PATH if needed:"
echo "  export PATH=\"$BIN_DIR:\$PATH\""
echo "Start the desktop indicator with:"
echo "  agent-status-desktop"
echo "Merge hooks, then restart Codex/Claude Code, with:"
echo "  $ROOT/install.sh --merge-hooks"
