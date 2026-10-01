# Agent Status Indicator

Agent Status Indicator is a local desktop status indicator for Codex and Claude Code. It provides a small floating circle on Linux, macOS, and Windows, and a native GNOME Shell top-bar extension on GNOME desktops.

It is designed for people who run several coding-agent sessions at the same time and need a quick signal for whether an agent is working, waiting for approval, idle, or has failed.

## Features

- Floating desktop indicator for Linux, macOS, and Windows.
- Native GNOME Shell extension for GNOME 46 and compatible GNOME desktops.
- Per-session state tracking for concurrent Codex and Claude Code sessions.
- Status priority aggregation: `error > approval > working > idle`.
- Persistent position, size, opacity, colors, click behavior, and always-on-top settings.
- Codex and Claude Code lifecycle hook adapters.
- Local CLI for manual updates and diagnostics.
- Optional `codex exec --json` wrapper.
- No network access and no root installation required.

## Statuses

| Status | Color | Meaning |
| --- | --- | --- |
| `idle` | Gray | No active agent work or no active session |
| `working` | Green | An agent is processing a prompt or tool call |
| `approval` | Yellow | An agent is waiting for user approval |
| `error` | Red | An agent or tool operation failed |

When several sessions are active, the highest-priority status is shown. A status belongs to its session, so one session stopping or resuming does not clear another concurrent session.

## Platform Support

| Platform | Desktop app | Agent hooks | Native shell integration |
| --- | --- | --- | --- |
| Linux | `install.sh` or source | Codex/Claude hooks and Unix socket daemon | GNOME Shell extension |
| macOS | `scripts/install-macos.sh` or source | Codex/Claude hooks and direct state-file updates | None |
| Windows | `scripts/install-windows.ps1` | `.cmd` hook wrappers and direct state-file updates | None |

The desktop app needs Python 3.10+ and Tkinter when run from source. A standalone executable can be built with PyInstaller on the target platform.

## Quick Start

### Linux

Install Tkinter if it is not already available:

```bash
sudo apt install python3-tk
```

Install the desktop app, CLI, daemon, and GNOME extension:

```bash
git clone https://github.com/Ruochen0513/agent-status-indicator.git
cd agent-status-indicator
bash install.sh
export PATH="$HOME/.local/bin:$PATH"
agent-status-desktop
```

The Linux installer starts the user-level `agent-status` daemon. To use the GNOME top-bar extension, log out and back in if GNOME does not load it immediately.

### macOS

From the repository directory:

```bash
chmod +x scripts/install-macos.sh
./scripts/install-macos.sh
export PATH="$HOME/.local/bin:$PATH"
agent-status-desktop
```

macOS does not use systemd or the GNOME extension. Add `agent-status-desktop` to Login Items or create a LaunchAgent if it should start when you log in.

### Windows

Run PowerShell from the repository directory:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\install-windows.ps1
```

Open a new PowerShell window and start the app:

```powershell
agent-status-desktop
```

The installer places files under `%LOCALAPPDATA%\AgentStatusIndicator` and adds its command directory to the current user's `PATH`. The Python launcher (`py -3`) and Tkinter must be available.

## Using The Desktop App

The first launch places the circle near the bottom-right corner of the primary display.

- Drag the circle to move it.
- Right-click it to open the status menu.
- Open **Settings** to change colors, size, opacity, click action, and always-on-top behavior.
- Double-click it to open settings.

Settings are stored per user:

```text
Linux:   ~/.config/agent-status-indicator/desktop.json
macOS:   ~/Library/Application Support/agent-status-indicator/desktop.json
Windows: %APPDATA%\agent-status-indicator\desktop.json
```

## Enabling Agent Hooks

Hooks are lifecycle callbacks executed by Codex or Claude Code. They call `agent-status-hook`, extract the event and session id, and update the local status. Without hooks, the indicator still runs, but automatic agent status updates are unavailable.

The supplied mappings are:

| Hook event | Result |
| --- | --- |
| `SessionStart` | `idle` initialization |
| `UserPromptSubmit`, `PreToolUse`, `PostToolUse` | `working` |
| `PermissionRequest`, `Notification` | `approval` |
| `Stop`, `SubagentStop` | `idle` |
| `StopFailure`, `PostToolUseFailure`, `Error` | `error` |

Hook configuration is opt-in because it modifies user-owned agent configuration files. Existing files are backed up before merging.

On Linux or macOS:

```bash
./install.sh --merge-hooks
```

To merge only one agent:

```bash
./install.sh --merge-codex-hooks
./install.sh --merge-claude-hooks
```

On Windows, use the installed `.cmd` wrapper in the hook command, for example:

```text
agent-status-hook.cmd --agent codex --event PreToolUse
```

After changing hooks, restart existing Codex and Claude Code sessions. In Codex, review and trust the hook definitions with `/hooks`.

Manual source files:

```text
config/codex/hooks.json              -> ~/.codex/hooks.json
config/claude/settings.example.json -> ~/.claude/settings.json
```

Merge the `hooks` object into an existing file instead of replacing unrelated settings.

## CLI Usage

Manual status updates:

```bash
agent-status update codex working
agent-status update codex approval
agent-status update codex error
agent-status update all idle
```

Inspect the aggregate state:

```bash
agent-status get
agent-status get codex
```

Test concurrent sessions:

```bash
agent-status update codex working "session one" --session codex:s1
agent-status update codex approval "session two" --session codex:s2
agent-status get codex
agent-status update codex idle --session codex:s1
agent-status update codex idle --session codex:s2
```

Run a non-interactive Codex command and mirror its JSONL lifecycle events:

```bash
codex-status-exec "summarize this repository"
```

On Windows, use the corresponding `.cmd` wrappers, such as `agent-status.cmd` and `codex-status-exec.cmd`.

## Building A Standalone App

Build on the platform where the app will run:

```bash
python3 -m pip install pyinstaller
./scripts/build-desktop.sh
```

The output under `dist/` is platform-specific. Build separately for Linux, macOS, and Windows.

## Uninstall

Linux:

```bash
./uninstall.sh
```

The uninstaller removes installed scripts, icons, the GNOME extension, and Linux user services. It does not remove Codex or Claude hook entries because those files may contain unrelated user configuration.

For macOS and Windows, remove the installed application directory and command entries described in the platform sections. Remove the corresponding hook entries manually if hooks were enabled.

## Troubleshooting

### The indicator stays gray

Check the current state and restart the agent after installing hooks:

```bash
agent-status get
```

On Linux, also check the daemon:

```bash
systemctl --user status agent-status.service
```

### The desktop command cannot be found

Add the user command directory to `PATH`:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

On Windows, open a new terminal after running `install-windows.ps1`.

### The desktop module is missing

Re-run the installer from the current checkout:

```bash
bash install.sh
```

The expected Linux runtime file is:

```text
~/.local/share/agent-status-indicator/desktop/agent_status_desktop.py
```

### GNOME does not show the extension

On X11, press `Alt+F2`, enter `r`, and press Enter. On Wayland, log out and log back in. Verify the extension with:

```bash
gnome-extensions info agent-status-indicator@Ruochen0513.github.io
```

## Privacy And Security

- Status data stays on the local machine.
- No network connection is required.
- Hook payloads are reduced to status, message, event, and session metadata.
- Linux Unix sockets use `0600` permissions.
- The project does not read full Codex or Claude Code conversation logs.

## Development

Run the test suite and static checks:

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile bin/agent-status bin/agent-status-hook bin/codex-status-exec bin/agent-status-desktop desktop/agent_status_desktop.py
bash -n install.sh scripts/*.sh uninstall.sh
```

Package the GNOME extension:

```bash
./scripts/package-extension.sh
```

## Project Layout

```text
bin/                         CLI, hook adapters, and launchers
config/                      Codex, Claude, systemd, and autostart files
desktop/                     Cross-platform Tk desktop application
gnome-extension/             GNOME Shell extension
icons/                       Legacy AppIndicator icons
scripts/                     Packaging and platform installers
tests/                       State and concurrency tests
```

## 中文说明

Agent Status Indicator 是一个用于显示 Codex 和 Claude Code 状态的本地桌面工具。

- Linux、macOS、Windows：悬浮小圆点桌面程序。
- GNOME：额外提供顶栏 Shell 插件。
- 支持多会话、状态聚合、颜色和位置自定义。
- 不访问网络，不需要 root 权限。

### 各平台启动

Linux：

```bash
sudo apt install python3-tk
bash install.sh
export PATH="$HOME/.local/bin:$PATH"
agent-status-desktop
```

macOS：

```bash
./scripts/install-macos.sh
export PATH="$HOME/.local/bin:$PATH"
agent-status-desktop
```

Windows PowerShell：

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\install-windows.ps1
```

重新打开 PowerShell 后运行：

```powershell
agent-status-desktop
```

### Hook 的作用

Hook 是 Codex/Claude Code 的生命周期回调。它们把 agent 事件转换为状态：

| 事件 | 状态 |
| --- | --- |
| `UserPromptSubmit`、`PreToolUse`、`PostToolUse` | `working` |
| `PermissionRequest`、`Notification` | `approval` |
| `Stop`、`SubagentStop` | `idle` |
| `StopFailure`、`Error` | `error` |

默认不修改用户配置，避免覆盖已有设置。启用方式：

```bash
./install.sh --merge-hooks
```

Windows hook 命令使用 `.cmd` 包装器，例如 `agent-status-hook.cmd --agent codex --event PreToolUse`。启用 hook 后需要重启 Codex 和 Claude Code。

### 常用命令

```bash
agent-status update codex working
agent-status update codex approval
agent-status update codex error
agent-status update all idle
agent-status get
```

桌面圆点支持拖动、右键菜单和 Settings 设置，可修改颜色、大小、透明度、点击行为和置顶模式。

## Architecture

The project has one local state protocol and several presentation clients:

```text
Codex / Claude lifecycle events
              |
              v
        agent-status-hook
              |
              v
  agent-status daemon or direct state update
              |
              v
  state.json + per-session state records
          /                 \
         v                   v
GNOME Shell extension   Desktop circle app
```

The state file contains two layers:

- `sessions.codex` and `sessions.claude` store each session's state, message, event, and timestamp.
- `agents.codex` and `agents.claude` contain priority-aggregated summaries for the UI.

On Linux, the daemon accepts updates over a per-user Unix socket and periodically normalizes expired sessions. On macOS and Windows, the CLI and hook adapter fall back to direct atomic state-file updates when a Unix socket daemon is unavailable. Updates use a lock file and atomic replacement so concurrent hooks do not overwrite one another. Working and idle sessions expire after two minutes by default; error sessions remain longer for diagnosis.

## 许可证

MIT
