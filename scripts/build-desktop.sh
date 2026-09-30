#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYINSTALLER="${PYINSTALLER:-pyinstaller}"

if ! command -v "$PYINSTALLER" >/dev/null 2>&1; then
  echo "PyInstaller is required. Install it with: python3 -m pip install pyinstaller" >&2
  exit 1
fi

"$PYINSTALLER" --noconfirm --clean --windowed \
  --name AgentStatusIndicator \
  "$ROOT/desktop/agent_status_desktop.py"

echo "Built a platform-specific desktop app in $ROOT/dist/"
