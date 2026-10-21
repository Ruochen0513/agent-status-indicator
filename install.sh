#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MERGE_CODEX_HOOKS=0
MERGE_CLAUDE_HOOKS=0
START_SERVICES=1

usage() {
  cat <<'EOF'
Usage: ./install.sh [options]

Options:
  --merge-codex-hooks    Merge config/codex/hooks.json into ~/.codex/hooks.json.
  --merge-claude-hooks   Merge config/claude/settings.example.json into ~/.claude/settings.json.
  --merge-hooks          Merge both Codex and Claude hook configs.
  --no-start             Install files without starting services or enabling extensions.
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
    --no-start)
      START_SERVICES=0
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

INSTALL_DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
INSTALL_CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"
EXTENSION_UUID="agent-status-indicator@Ruochen0513.github.io"
LEGACY_EXTENSION_UUID="agent-status-indicator@yuhaozhang.github.io"
EXTENSION_ROOT="$INSTALL_DATA_HOME/gnome-shell/extensions"
# Older releases used a different UUID. Update the installed identity in place
# so GNOME does not keep running a forgotten, unpatched copy.
if [[ -d "$EXTENSION_ROOT/$LEGACY_EXTENSION_UUID" && ! -d "$EXTENSION_ROOT/$EXTENSION_UUID" ]]; then
  EXTENSION_UUID="$LEGACY_EXTENSION_UUID"
fi
EXTENSION_DIR="$EXTENSION_ROOT/$EXTENSION_UUID"

DESKTOP_RUNTIME_DIR="$INSTALL_DATA_HOME/agent-status-indicator/desktop"
mkdir -p "$HOME/.local/bin" "$INSTALL_DATA_HOME/agent-status-indicator/icons" "$DESKTOP_RUNTIME_DIR" "$INSTALL_CONFIG_HOME/systemd/user"
mkdir -p "$EXTENSION_DIR"
install -m 0644 "$ROOT/bin/agent_status_state.py" "$HOME/.local/bin/agent_status_state.py"
install -m 0644 "$ROOT/bin/agent_status_state.py" "$DESKTOP_RUNTIME_DIR/agent_status_state.py"
install -m 0755 "$ROOT/bin/agent-status" "$HOME/.local/bin/agent-status"
install -m 0755 "$ROOT/bin/agent-status-indicator" "$HOME/.local/bin/agent-status-indicator"
install -m 0755 "$ROOT/bin/agent-status-hook" "$HOME/.local/bin/agent-status-hook"
install -m 0755 "$ROOT/bin/codex-status-exec" "$HOME/.local/bin/codex-status-exec"
install -m 0755 "$ROOT/bin/agent-status-desktop" "$HOME/.local/bin/agent-status-desktop"
cp "$ROOT/desktop/agent_status_desktop.py" "$DESKTOP_RUNTIME_DIR/agent_status_desktop.py"
chmod 0644 "$DESKTOP_RUNTIME_DIR/agent_status_desktop.py"
if [[ ! -s "$DESKTOP_RUNTIME_DIR/agent_status_desktop.py" ]]; then
  echo "Desktop runtime was not installed: $DESKTOP_RUNTIME_DIR/agent_status_desktop.py" >&2
  exit 1
fi
install -m 0644 "$ROOT/icons"/agent-status-*.png "$INSTALL_DATA_HOME/agent-status-indicator/icons/"
if command -v systemctl >/dev/null 2>&1 && [[ "$(uname -s)" == "Linux" ]]; then
  install -m 0644 "$ROOT/config/systemd/agent-status.service" "$INSTALL_CONFIG_HOME/systemd/user/agent-status.service"
  install -m 0644 "$ROOT/config/systemd/agent-status-indicator.service" "$INSTALL_CONFIG_HOME/systemd/user/agent-status-indicator.service"
fi
install -m 0644 "$ROOT/gnome-extension/agent-status-indicator@Ruochen0513.github.io/metadata.json" "$EXTENSION_DIR/metadata.json"
install -m 0644 "$ROOT/gnome-extension/agent-status-indicator@Ruochen0513.github.io/extension.js" "$EXTENSION_DIR/extension.js"
install -m 0644 "$ROOT/gnome-extension/agent-status-indicator@Ruochen0513.github.io/state.js" "$EXTENSION_DIR/state.js"
install -m 0644 "$ROOT/LICENSE" "$EXTENSION_DIR/LICENSE"

EXTENSION_DIR="$EXTENSION_DIR" EXTENSION_UUID="$EXTENSION_UUID" "${PYTHON_BIN:-python3}" - <<'PYMETA'
import json
import os
from pathlib import Path
path = Path(os.environ["EXTENSION_DIR"]) / "metadata.json"
metadata = json.loads(path.read_text())
metadata["uuid"] = os.environ["EXTENSION_UUID"]
path.write_text(json.dumps(metadata, indent=2) + "\n")
PYMETA

if [[ "$START_SERVICES" -eq 1 ]]; then
  if command -v systemctl >/dev/null 2>&1 && [[ "$(uname -s)" == "Linux" ]]; then
    systemctl --user daemon-reload
    systemctl --user enable --now agent-status.service
    systemctl --user restart agent-status.service
  fi
  if command -v gnome-extensions >/dev/null 2>&1; then
    if gnome-extensions enable "$EXTENSION_UUID"; then
      if [[ "$EXTENSION_UUID" != "$LEGACY_EXTENSION_UUID" && -d "$EXTENSION_ROOT/$LEGACY_EXTENSION_UUID" ]]; then
        gnome-extensions disable "$LEGACY_EXTENSION_UUID" || true
      fi
      # Do not remove the user's fallback until native extension enable succeeds.
      systemctl --user disable --now agent-status-indicator.service 2>/dev/null || true
      echo "GNOME extension enabled. Existing loaded code needs logout/login to update."
    else
      echo "GNOME extension could not be enabled. Log out/in, then run:" >&2
      echo "  gnome-extensions enable $EXTENSION_UUID" >&2
    fi
  fi
fi

if [[ "$MERGE_CODEX_HOOKS" -eq 1 || "$MERGE_CLAUDE_HOOKS" -eq 1 ]]; then
  ROOT="$ROOT" MERGE_CODEX_HOOKS="$MERGE_CODEX_HOOKS" MERGE_CLAUDE_HOOKS="$MERGE_CLAUDE_HOOKS" "${PYTHON_BIN:-python3}" - <<'PY'
from __future__ import annotations

import json
import os
import shutil
import shlex
import subprocess
import tempfile
import time
from pathlib import Path

root = Path(os.environ["ROOT"])
stamp = time.strftime("%Y%m%d-%H%M%S") + f"-{time.time_ns()}"


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in {path}: {exc}")


def is_status_handler(handler: dict) -> bool:
    if not isinstance(handler, dict) or handler.get("type") != "command":
        return False
    try:
        words = shlex.split(handler.get("command", ""))
    except ValueError:
        return False
    return bool(words) and Path(words[0]).name in {"agent-status-hook", "agent-status-hook.cmd"}


def merge_hooks(dst: dict, src: dict) -> dict:
    dst_hooks = dst.setdefault("hooks", {})
    # Replace our old definitions (including stale matchers) while retaining
    # unrelated handlers even when they share a matcher group with ours.
    for event, entries in list(dst_hooks.items()):
        kept = []
        for entry in entries:
            handlers = entry.get("hooks", [])
            filtered = [handler for handler in handlers if not is_status_handler(handler)]
            if len(filtered) == len(handlers):
                kept.append(entry)
            elif filtered:
                kept.append({**entry, "hooks": filtered})
        if kept:
            dst_hooks[event] = kept
        else:
            dst_hooks.pop(event, None)
    for event, entries in src.get("hooks", {}).items():
        for entry in entries:
            for handler in entry["hooks"]:
                words = shlex.split(handler["command"])
                words[0] = str(Path.home() / ".local/bin/agent-status-hook")
                handler["command"] = shlex.join(words)
        dst_hooks.setdefault(event, []).extend(entries)
    return dst


def codex_supported_events() -> set[str]:
    # Query this executable's protocol rather than assuming the website documents
    # the exact release installed on the user's machine. Never execute a turn.
    core = {"sessionstart", "userpromptsubmit", "pretooluse", "permissionrequest", "posttooluse", "stop"}
    executable = shutil.which("codex")
    if not executable:
        return core
    try:
        with tempfile.TemporaryDirectory(prefix="agent-status-schema-") as directory:
            result = subprocess.run([executable, "app-server", "generate-json-schema", "--experimental", "--out", directory],
                                    capture_output=True, text=True, timeout=10)
            path = Path(directory) / "v2/HooksListResponse.json"
            if result.returncode == 0 and path.exists():
                schema = json.loads(path.read_text())
                names = schema["definitions"]["HookEventName"]["enum"]
                return {name.lower() for name in names}
    except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired):
        pass
    print("Could not query Codex event support; using the core lifecycle hooks.")
    return core


def write_merged(target: Path, source: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        backup = target.with_suffix(target.suffix + f".bak-{stamp}")
        shutil.copy2(target, backup)
        print(f"Backed up {target} -> {backup}")
    source_config = load_json(source)
    if source == root / "config/codex/hooks.json":
        supported = codex_supported_events()
        omitted = [event for event in source_config["hooks"] if event.lower() not in supported]
        for event in omitted:
            del source_config["hooks"][event]
        if omitted:
            print("Codex release does not register these events; omitted: " + ", ".join(omitted))
    merged = merge_hooks(load_json(target), source_config)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(json.dumps(merged, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.chmod(0o600)
    temporary.replace(target)
    print(f"Merged {source} -> {target}")


if os.environ.get("MERGE_CODEX_HOOKS") == "1":
    write_merged(Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex") / "hooks.json", root / "config/codex/hooks.json")
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

if [[ "$MERGE_CODEX_HOOKS" -eq 1 ]]; then
  echo "Codex automatic status is inactive until these hooks are reviewed and trusted in /hooks."
  echo "Verify runtime registration and trust: agent-status doctor --check-codex"
fi
