#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXT_DIR="$ROOT/gnome-extension/agent-status-indicator@Ruochen0513.github.io"
OUT="$ROOT/agent-status-indicator@Ruochen0513.github.io.shell-extension.zip"
STAGING_DIR="$(mktemp -d)"
trap 'rm -rf "$STAGING_DIR"' EXIT

# Keep the marketplace archive independent of the Python companion and installers.
cp "$EXT_DIR/metadata.json" "$EXT_DIR/extension.js" "$EXT_DIR/state.js" "$ROOT/LICENSE" "$STAGING_DIR/"
if command -v gnome-extensions >/dev/null 2>&1; then
  gnome-extensions pack --force --out-dir "$ROOT" \
    --extra-source=state.js --extra-source=LICENSE "$STAGING_DIR"
else
  # Source users on other platforms can still produce the identical archive layout.
  rm -f "$OUT"
  (cd "$STAGING_DIR" && zip -q "$OUT" metadata.json extension.js state.js LICENSE)
fi

"${PYTHON_BIN:-python3}" "$ROOT/scripts/validate-extension.py" "$OUT"
echo "$OUT"
