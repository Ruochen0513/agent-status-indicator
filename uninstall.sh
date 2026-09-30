#!/usr/bin/env bash
set -euo pipefail

KEEP_CONFIG=0

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
systemctl --user disable --now agent-status.service 2>/dev/null || true
systemctl --user disable --now agent-status-indicator.service 2>/dev/null || true
systemctl --user daemon-reload

rm -f "$HOME/.local/bin/agent-status"
rm -f "$HOME/.local/bin/agent-status-hook"
rm -f "$HOME/.local/bin/agent-status-indicator"
rm -f "$HOME/.local/bin/codex-status-exec"
rm -f "$HOME/.local/bin/agent-status-desktop"
rm -f "$HOME/.config/systemd/user/agent-status.service"
rm -f "$HOME/.config/systemd/user/agent-status-indicator.service"
rm -rf "$HOME/.local/share/gnome-shell/extensions/agent-status-indicator@Ruochen0513.github.io"
rm -rf "$HOME/.local/share/agent-status-indicator"
rm -f "$HOME/.config/autostart/agent-status-indicator.desktop"

if [[ "$KEEP_CONFIG" -eq 0 ]]; then
  rm -rf "$HOME/.cache/agent-status-indicator"
  runtime_dir="${XDG_RUNTIME_DIR:-/tmp}/agent-status-indicator"
  rm -rf "$runtime_dir" 2>/dev/null || true
fi

echo "Uninstalled Agent Status Indicator Indicator."
