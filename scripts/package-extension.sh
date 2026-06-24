#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXT_DIR="$ROOT/gnome-extension/agent-status-indicator@Ruochen0513.github.io"
OUT="$ROOT/agent-status-indicator@Ruochen0513.github.io.shell-extension.zip"

rm -f "$OUT"
(
  cd "$EXT_DIR"
  zip -q -r "$OUT" metadata.json extension.js stylesheet.css
)

echo "$OUT"
