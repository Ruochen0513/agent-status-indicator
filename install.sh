#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MERGE_CODEX_HOOKS=0
MERGE_CLAUDE_HOOKS=0

usage() {
  cat <<'EOF'
Usage: ./install.sh [options]

Options:
  --merge-codex-hooks    Merge config/codex/hooks.json into ~/.codex/hooks.json.
  --merge-claude-hooks   Merge config/claude/settings.example.json into ~/.claude/settings.json.
  --merge-hooks          Merge both Codex and Claude hook configs.
  -h, --help             Show this help.

By default this installs the GNOME extension, CLI scripts, and user systemd
service only. Hook config changes are opt-in because they modify agent config.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --merge-codex-hooks)
      MERGE_CODEX_HOOKS=1
      ;;
    --merge-claude-hooks)
      MERGE_CLAUDE_HOOKS=1
      ;;
    --merge-hooks)
      MERGE_CODEX_HOOKS=1
      MERGE_CLAUDE_HOOKS=1
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

mkdir -p "$HOME/.local/bin" "$HOME/.local/share/agent-status-indicator/icons" "$HOME/.config/systemd/user"
mkdir -p "$HOME/.local/share/gnome-shell/extensions/agent-status-indicator@yuhaozhang.github.io"
install -m 0755 "$ROOT/bin/agent-status" "$HOME/.local/bin/agent-status"
install -m 0755 "$ROOT/bin/agent-status-indicator" "$HOME/.local/bin/agent-status-indicator"
install -m 0755 "$ROOT/bin/agent-status-hook" "$HOME/.local/bin/agent-status-hook"
install -m 0755 "$ROOT/bin/codex-status-exec" "$HOME/.local/bin/codex-status-exec"
install -m 0644 "$ROOT/icons"/agent-status-*.png "$HOME/.local/share/agent-status-indicator/icons/"
install -m 0644 "$ROOT/config/systemd/agent-status.service" "$HOME/.config/systemd/user/agent-status.service"
install -m 0644 "$ROOT/config/systemd/agent-status-indicator.service" "$HOME/.config/systemd/user/agent-status-indicator.service"
install -m 0644 "$ROOT/gnome-extension/agent-status-indicator@yuhaozhang.github.io/metadata.json" "$HOME/.local/share/gnome-shell/extensions/agent-status-indicator@yuhaozhang.github.io/metadata.json"
install -m 0644 "$ROOT/gnome-extension/agent-status-indicator@yuhaozhang.github.io/extension.js" "$HOME/.local/share/gnome-shell/extensions/agent-status-indicator@yuhaozhang.github.io/extension.js"
install -m 0644 "$ROOT/gnome-extension/agent-status-indicator@yuhaozhang.github.io/stylesheet.css" "$HOME/.local/share/gnome-shell/extensions/agent-status-indicator@yuhaozhang.github.io/stylesheet.css"

systemctl --user daemon-reload
systemctl --user enable --now agent-status.service
systemctl --user restart agent-status.service
systemctl --user disable --now agent-status-indicator.service 2>/dev/null || true
gnome-extensions enable agent-status-indicator@yuhaozhang.github.io 2>/dev/null || true

if [[ "$MERGE_CODEX_HOOKS" -eq 1 || "$MERGE_CLAUDE_HOOKS" -eq 1 ]]; then
  ROOT="$ROOT" MERGE_CODEX_HOOKS="$MERGE_CODEX_HOOKS" MERGE_CLAUDE_HOOKS="$MERGE_CLAUDE_HOOKS" /usr/bin/python3 - <<'PY'
from __future__ import annotations

import json
import os
import shutil
import time
from pathlib import Path

root = Path(os.environ["ROOT"])
stamp = time.strftime("%Y%m%d-%H%M%S")


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in {path}: {exc}")


def merge_hooks(dst: dict, src: dict) -> dict:
    dst_hooks = dst.setdefault("hooks", {})
    for event, entries in src.get("hooks", {}).items():
        existing = dst_hooks.setdefault(event, [])
        seen = {json.dumps(item, sort_keys=True) for item in existing}
        for item in entries:
            key = json.dumps(item, sort_keys=True)
            if key not in seen:
                existing.append(item)
                seen.add(key)
    return dst


def write_merged(target: Path, source: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        backup = target.with_suffix(target.suffix + f".bak-{stamp}")
        shutil.copy2(target, backup)
        print(f"Backed up {target} -> {backup}")
    merged = merge_hooks(load_json(target), load_json(source))
    target.write_text(json.dumps(merged, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Merged {source} -> {target}")


if os.environ.get("MERGE_CODEX_HOOKS") == "1":
    write_merged(Path.home() / ".codex" / "hooks.json", root / "config/codex/hooks.json")
if os.environ.get("MERGE_CLAUDE_HOOKS") == "1":
    write_merged(Path.home() / ".claude" / "settings.json", root / "config/claude/settings.example.json")
PY
fi

echo "Installed. Test with:"
echo "  agent-status update codex working"
echo "  agent-status update codex approval"
echo "  agent-status update codex error"
echo "  agent-status update all idle"
echo
echo "To enable automatic Codex/Claude updates, merge hooks and restart those agents:"
echo "  ./install.sh --merge-hooks"
