#!/usr/bin/env bash
set -euo pipefail

KEEP_CONFIG=0
INSTALL_DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
INSTALL_CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"

usage() {
  cat <<'EOF'
Usage: ./uninstall.sh [options]

Options:
  --keep-config   Leave state files, hooks, and user config untouched.
  -h, --help      Show this help.

This removes installed scripts, the GNOME extension, and user systemd services.
It does not edit ~/.codex/hooks.json or ~/.claude/settings.json; remove hook
entries manually if you merged them during installation.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --keep-config)
      KEEP_CONFIG=1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
  shift
done

gnome-extensions disable agent-status-indicator@Ruochen0513.github.io 2>/dev/null || true
gnome-extensions disable agent-status-indicator@yuhaozhang.github.io 2>/dev/null || true
systemctl --user disable --now agent-status.service 2>/dev/null || true
systemctl --user disable --now agent-status-indicator.service 2>/dev/null || true
systemctl --user daemon-reload

rm -f "$HOME/.local/bin/agent_status_state.py"
rm -f "$HOME/.local/bin/agent-status"
rm -f "$HOME/.local/bin/agent-status-hook"
rm -f "$HOME/.local/bin/agent-status-indicator"
rm -f "$HOME/.local/bin/codex-status-exec"
rm -f "$HOME/.local/bin/agent-status-desktop"
rm -f "$INSTALL_CONFIG_HOME/systemd/user/agent-status.service"
rm -f "$INSTALL_CONFIG_HOME/systemd/user/agent-status-indicator.service"
rm -rf "$INSTALL_DATA_HOME/gnome-shell/extensions/agent-status-indicator@Ruochen0513.github.io"
rm -rf "$INSTALL_DATA_HOME/gnome-shell/extensions/agent-status-indicator@yuhaozhang.github.io"
rm -rf "$INSTALL_DATA_HOME/agent-status-indicator"
rm -f "$INSTALL_CONFIG_HOME/autostart/agent-status-indicator.desktop"

if [[ "$KEEP_CONFIG" -eq 0 ]]; then
  rm -rf "$HOME/.cache/agent-status-indicator"
  runtime_dir="${XDG_RUNTIME_DIR:-/tmp}/agent-status-indicator"
  if [[ -z "${XDG_RUNTIME_DIR:-}" ]]; then
    runtime_dir="/tmp/agent-status-indicator-$(id -u)"
  fi
  rm -rf "$runtime_dir" 2>/dev/null || true
fi

echo "Uninstalled Agent Status Indicator."
