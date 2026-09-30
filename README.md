# Agent Status Indicator

[English](#agent-status-indicator) | [中文](#中文说明)

Agent Status Indicator is a cross-platform desktop indicator and GNOME Shell extension for showing local Codex and Claude Code activity.

It is designed for people who keep multiple coding-agent terminals open and want a quick desktop-level signal for whether an agent is working, idle, waiting for approval, or errored. The desktop app is a small floating circle that can be dragged anywhere and customized without GNOME.

## Effect

The extension displays a small colored dot on the left side of the GNOME top bar.

| Color | Meaning |
| --- | --- |
| Gray | Idle, no active prompt, or no active agent session |
| Green | At least one agent session is working |
| Yellow | At least one agent session is waiting for user approval |
| Red | At least one agent session failed or errored |

When multiple sessions are active, the highest-priority state wins:

```text
red > yellow > green > gray
```

Example: if one Codex session is working and another Codex session is waiting for approval, the indicator is yellow.

Approval requests are cleared as soon as the same session reports `working` again. `Stop`-style events clear only the session that emitted the event, so concurrent sessions do not interrupt each other. Idle and working sessions expire after the configured state TTL (two minutes by default); error sessions remain visible longer for diagnosis.

## Features

- GNOME Shell top-bar indicator.
- Cross-platform floating desktop app for Linux, macOS, and Windows.
- Drag-to-position circle with persistent location and settings.
- Custom colors, size, opacity, click action, and always-on-top behavior.
- Codex hook integration.
- Claude Code hook integration.
- Per-session state tracking, so concurrent sessions do not overwrite each other.
- Local user-level daemon with a Unix socket.
- CLI for manual testing and diagnostics.
- Optional wrapper for `codex exec --json`.
- No network access and no root install required.

## How It Works

```text
Codex / Claude lifecycle hooks
        |
        v
agent-status-hook
        |
        v
agent-status daemon  <---- agent-status CLI / codex-status-exec
        |
        v
~/.cache/agent-status-indicator/state.json
        |
        v
GNOME Shell extension or desktop app reads state.json
```

The status daemon stores state in two levels:

- `sessions.codex` and `sessions.claude`: individual session state.
- `agents.codex` and `agents.claude`: aggregated state used by the GNOME extension.

This avoids the common problem where two agent sessions race and overwrite one global status value. State mutations use a small cross-platform lock and atomic file replacement.

The default version does not scan running processes. Existing Codex or Claude Code sessions must be restarted after hook installation so they load the hook configuration.

## Requirements

- GNOME mode: Ubuntu or another GNOME Shell desktop. GNOME Shell 46 is tested.
- Desktop mode: Python 3.10+ with Tkinter, or a packaged build created with PyInstaller.
- Linux daemon mode additionally uses `systemd --user`; macOS and Windows use direct state-file updates when a Unix socket is unavailable.
- Codex and/or Claude Code for automatic status updates.

Install common Ubuntu dependencies:

```bash
sudo apt install python3-gi gir1.2-gtk-3.0
```

The legacy AppIndicator script is included for older Ubuntu environments. If you want to use it, also install:

```bash
sudo apt install gir1.2-ayatanaappindicator3-0.1
```

## Install From GitHub

Clone the repository:

```bash
git clone https://github.com/Ruochen0513/agent-status-indicator.git
cd agent-status-indicator
```

Install the GNOME extension, CLI scripts, icons, and user-level daemon:

```bash
./install.sh
```

The installer also installs the `agent-status-desktop` command. Start the floating indicator with:

```bash
agent-status-desktop
```

The first launch places the circle near the bottom-right corner. Drag it to any position, right-click it, and open **Settings** to customize colors, size, opacity, click behavior, and always-on-top mode. Settings are stored in the platform user configuration directory.

For a standalone desktop executable, build on the target platform:

```bash
python3 -m pip install pyinstaller
./scripts/build-desktop.sh
```

The generated `dist/AgentStatusIndicator` application is platform-specific. Tkinter is included in the Windows and macOS Python installers; on Debian/Ubuntu install `python3-tk` for source execution. On Linux, optional desktop autostart is available by copying `config/autostart/agent-status-indicator.desktop` to `~/.config/autostart/`.

On Windows, run `powershell -ExecutionPolicy Bypass -File scripts/install-windows.ps1` from the repository, open a new terminal, and run `agent-status-desktop`. The installer adds the command wrappers to the current user's `PATH` and stores state under `%LOCALAPPDATA%`.

By default, the installer does not modify Codex or Claude Code hook files. To merge the provided hook examples into your user config:

```bash
./install.sh --merge-hooks
```

Or merge only one agent config:

```bash
./install.sh --merge-codex-hooks
./install.sh --merge-claude-hooks
```

After installing or changing hooks:

1. Restart existing Codex and Claude Code sessions.
2. In Codex, run `/hooks` and trust the new hook definitions.
3. Start a new prompt and confirm the dot turns green.

## Manual Hook Setup

If you do not want the installer to merge configs, copy or merge these files yourself:

- Codex: `config/codex/hooks.json` -> `~/.codex/hooks.json`
- Claude Code: `config/claude/settings.example.json` -> `~/.claude/settings.json`

Keep existing settings and merge the `hooks` object rather than replacing the whole file.

## Usage

Manual tests:

```bash
agent-status update codex working
agent-status update codex approval
agent-status update codex error
agent-status update all idle
```

Diagnostics:

```bash
agent-status get
agent-status get codex
systemctl --user status agent-status.service
gnome-extensions info agent-status-indicator@Ruochen0513.github.io
```

Session-scoped manual test:

```bash
agent-status update codex working "session one" --session codex:s1
agent-status update codex approval "session two" --session codex:s2
agent-status get codex
agent-status update codex idle --session codex:s1
agent-status update codex idle --session codex:s2
```

Non-interactive Codex wrapper:

```bash
codex-status-exec "summarize this repository"
```

It runs `codex exec --json`, passes JSONL output through unchanged, and mirrors lifecycle events into the indicator.

## Files Modified Or Created

The default installer creates or modifies these files and directories:

```text
~/.local/bin/agent-status
~/.local/bin/agent-status-hook
~/.local/bin/agent-status-indicator
~/.local/bin/codex-status-exec
~/.local/bin/agent-status-desktop
~/.local/share/gnome-shell/extensions/agent-status-indicator@Ruochen0513.github.io/
~/.local/share/agent-status-indicator/icons/
~/.config/systemd/user/agent-status.service
~/.config/systemd/user/agent-status-indicator.service
```

At runtime, the daemon creates:

```text
~/.cache/agent-status-indicator/state.json
$XDG_RUNTIME_DIR/agent-status-indicator/agent-status.sock
~/.config/agent-status-indicator/desktop.json (Linux; platform equivalent on macOS/Windows)
```

The installer also runs:

```bash
systemctl --user daemon-reload
systemctl --user enable --now agent-status.service
systemctl --user restart agent-status.service
gnome-extensions enable agent-status-indicator@Ruochen0513.github.io
```

The default installer disables the legacy AppIndicator user service if present:

```bash
systemctl --user disable --now agent-status-indicator.service
```

With `--merge-codex-hooks`, it creates or modifies:

```text
~/.codex/hooks.json
```

If the file already exists, the installer writes a timestamped backup next to it:

```text
~/.codex/hooks.json.bak-YYYYMMDD-HHMMSS
```

With `--merge-claude-hooks`, it creates or modifies:

```text
~/.claude/settings.json
```

If the file already exists, the installer writes a timestamped backup next to it:

```text
~/.claude/settings.json.bak-YYYYMMDD-HHMMSS
```

## What It Does Not Do

- It does not require root privileges.
- It does not install system-wide files.
- It does not send data to the network.
- It does not scan running processes in the default version; an agent must emit a hook event.
- It does not edit project files.
- It does not read full Codex or Claude conversation logs. It only receives the small JSON hook payload passed by the agent runtime.

## Privacy And Security

Hook payloads are used only to extract status, message, event name, and session identifier. The status daemon stores this small state locally in:

```text
~/.cache/agent-status-indicator/state.json
```

The daemon listens on a per-user Unix socket under:

```text
$XDG_RUNTIME_DIR/agent-status-indicator/agent-status.sock
```

The socket is created with `0600` permissions so only the current user can write to it.

## Uninstall

```bash
./uninstall.sh
```

The uninstaller removes installed scripts, the GNOME extension, icons, and user systemd services. It does not edit `~/.codex/hooks.json` or `~/.claude/settings.json`; remove hook entries manually if you merged them.

To leave local state/cache files untouched:

```bash
./uninstall.sh --keep-config
```

## Troubleshooting

If the dot stays gray:

1. Check the extension:

   ```bash
   gnome-extensions info agent-status-indicator@Ruochen0513.github.io
   ```

2. Check the daemon:

   ```bash
   systemctl --user status agent-status.service
   ```

3. Check current state:

   ```bash
   agent-status get
   ```

4. Restart Codex or Claude Code so hooks are loaded.

5. In Codex, run `/hooks` and trust the hook definitions.

If the extension was just installed and GNOME does not see it, refresh GNOME Shell on X11:

```text
Alt+F2, type r, press Enter
```

On Wayland, log out and log back in.

If the indicator stays yellow after approval, make sure `PostToolUse` exists in your Codex hook config and restart Codex:

```bash
rg "PostToolUse" ~/.codex/hooks.json
```

## Project Layout

```text
bin/
  agent-status            status daemon and CLI
  agent-status-desktop    cross-platform floating desktop app
  agent-status-hook       Codex/Claude hook adapter
  codex-status-exec       wrapper for codex exec --json
  agent-status-indicator  legacy AppIndicator UI
config/
  codex/hooks.json
  claude/settings.example.json
  systemd/*.service
gnome-extension/
  agent-status-indicator@Ruochen0513.github.io/
icons/
scripts/
  build-desktop.sh
  install-windows.ps1
  package-extension.sh
install.sh
uninstall.sh
```


## License

MIT


---

# 中文说明

Agent Status Indicator 是一个 GNOME Shell 顶栏插件和本地状态守护进程，用于在 Ubuntu/GNOME 顶栏显示本机 Codex 与 Claude Code 的运行状态。

它适合经常同时打开多个 coding agent 终端的人：你可以不用切回终端，就能从桌面顶栏快速判断 agent 是正在工作、空闲、等待授权，还是出错。

## 显示效果

插件会在 GNOME 顶栏左侧显示一个小圆点。

| 颜色 | 含义 |
| --- | --- |
| 灰色 | 空闲、没有活跃 prompt，或没有活跃 agent 会话 |
| 绿色 | 至少一个 agent 会话正在工作 |
| 黄色 | 至少一个 agent 会话正在等待用户授权 |
| 红色 | 至少一个 agent 会话失败或报错 |

多个会话同时存在时，按优先级聚合显示：

```text
红色 > 黄色 > 绿色 > 灰色
```

例如：一个 Codex 会话正在 working，另一个 Codex 会话正在等待授权，此时顶栏显示黄色。

授权请求会在同一个 session 后续上报 `working` 时被清除。`Stop` 类事件只清理产生该事件的 session，并发会话不会互相中断。working/idle 状态在两分钟没有新事件后自动过期，error 状态会保留更长时间用于诊断。

## 功能

- GNOME Shell 顶栏状态点。
- 支持 Linux、macOS、Windows 的悬浮桌面圆点程序。
- 圆点可拖动到任意位置，并保存位置和设置。
- 可自定义颜色、大小、透明度、点击行为和置顶模式。
- Codex hook 集成。
- Claude Code hook 集成。
- 按 session 记录状态，多个并发会话不会互相覆盖。
- 本地用户级 daemon，通过 Unix socket 接收状态更新。
- 提供 CLI，方便手动测试和诊断。
- 提供 `codex exec --json` 的可选 wrapper。
- 不访问网络，不需要 root 安装。

## 实现原理

```text
Codex / Claude 生命周期 hooks
        |
        v
agent-status-hook
        |
        v
agent-status daemon  <---- agent-status CLI / codex-status-exec
        |
        v
~/.cache/agent-status-indicator/state.json
        |
        v
GNOME Shell extension 或桌面程序读取 state.json
```

状态文件分两层：

- `sessions.codex` 和 `sessions.claude`：每个会话自己的状态。
- `agents.codex` 和 `agents.claude`：聚合后的状态，供 GNOME 插件显示。

这样可以避免多个 agent 会话同时运行时互相覆盖同一个全局状态值。状态更新使用跨平台锁和原子替换，避免并发 hook 丢失更新。

默认版本不会扫描运行中的进程。安装 hooks 后，已经打开的 Codex 或 Claude Code 会话需要重启，才能加载新的 hook 配置。

## 环境要求

- GNOME 模式：Ubuntu 或其他 GNOME Shell 桌面环境，已测试 GNOME Shell 46。
- 桌面模式：Python 3.10+ 和 Tkinter，或使用 PyInstaller 构建的独立程序。
- Linux daemon 模式额外需要 `systemd --user`；macOS 和 Windows 在 Unix socket 不可用时会直接更新状态文件。
- 如果需要自动状态更新，需要安装 Codex 和/或 Claude Code。

Ubuntu 常见依赖：

```bash
sudo apt install python3-gi gir1.2-gtk-3.0
```

仓库中仍保留旧版 AppIndicator 脚本，但默认禁用。如果你想实验 AppIndicator 版本，还需要：

```bash
sudo apt install gir1.2-ayatanaappindicator3-0.1
```

## 从 GitHub 安装

克隆仓库：

```bash
git clone https://github.com/Ruochen0513/agent-status-indicator.git
cd agent-status-indicator
```

安装 GNOME 插件、CLI 脚本、图标和用户级 daemon：

```bash
./install.sh
```

安装脚本也会安装 `agent-status-desktop`。启动跨平台悬浮圆点：

```bash
agent-status-desktop
```

首次启动会把圆点放在屏幕右下角。拖动圆点即可改变位置；右键打开菜单并进入 **Settings**，可以修改颜色、大小、透明度、点击行为和置顶模式。设置会保存在当前用户的配置目录。

需要独立桌面程序时，请在目标平台构建：

```bash
python3 -m pip install pyinstaller
./scripts/build-desktop.sh
```

生成的 `dist/AgentStatusIndicator` 仅适用于构建它的平台。Debian/Ubuntu 从源码运行时需要 `python3-tk`。Linux 可选地将 `config/autostart/agent-status-indicator.desktop` 复制到 `~/.config/autostart/` 实现登录自动启动。

Windows 可以在仓库目录执行 `powershell -ExecutionPolicy Bypass -File scripts/install-windows.ps1`，打开新的终端后运行 `agent-status-desktop`。脚本会把命令包装器加入当前用户的 `PATH`，状态文件保存在 `%LOCALAPPDATA%`。

默认情况下，安装脚本不会修改 Codex 或 Claude Code 的 hook 配置。若要把项目提供的 hook 示例合并到用户配置中：

```bash
./install.sh --merge-hooks
```

也可以只合并其中一个：

```bash
./install.sh --merge-codex-hooks
./install.sh --merge-claude-hooks
```

安装或修改 hooks 后：

1. 重启已打开的 Codex 和 Claude Code 会话。
2. 在 Codex 中运行 `/hooks`，review 并 trust 新增 hook。
3. 开始一个新 prompt，确认顶栏圆点变绿。

## 手动配置 Hooks

如果你不想让安装脚本自动合并配置，可以手动复制或合并：

- Codex：`config/codex/hooks.json` -> `~/.codex/hooks.json`
- Claude Code：`config/claude/settings.example.json` -> `~/.claude/settings.json`

注意保留原有配置，只合并 `hooks` 对象，不要直接覆盖整个文件。

## 使用方法

手动测试：

```bash
agent-status update codex working
agent-status update codex approval
agent-status update codex error
agent-status update all idle
```

诊断命令：

```bash
agent-status get
agent-status get codex
systemctl --user status agent-status.service
gnome-extensions info agent-status-indicator@Ruochen0513.github.io
```

按 session 测试：

```bash
agent-status update codex working "session one" --session codex:s1
agent-status update codex approval "session two" --session codex:s2
agent-status get codex
agent-status update codex idle --session codex:s1
agent-status update codex idle --session codex:s2
```

非交互 Codex wrapper：

```bash
codex-status-exec "summarize this repository"
```

它会运行 `codex exec --json`，原样透传 JSONL 输出，并把生命周期事件同步到顶栏状态。

## 会创建或修改哪些文件

默认安装会创建或修改：

```text
~/.local/bin/agent-status
~/.local/bin/agent-status-hook
~/.local/bin/agent-status-indicator
~/.local/bin/codex-status-exec
~/.local/bin/agent-status-desktop
~/.local/share/gnome-shell/extensions/agent-status-indicator@Ruochen0513.github.io/
~/.local/share/agent-status-indicator/icons/
~/.config/systemd/user/agent-status.service
~/.config/systemd/user/agent-status-indicator.service
```

运行时 daemon 会创建：

```text
~/.cache/agent-status-indicator/state.json
$XDG_RUNTIME_DIR/agent-status-indicator/agent-status.sock
~/.config/agent-status-indicator/desktop.json（Linux；macOS/Windows 使用对应平台目录）
```

安装脚本还会执行：

```bash
systemctl --user daemon-reload
systemctl --user enable --now agent-status.service
systemctl --user restart agent-status.service
gnome-extensions enable agent-status-indicator@Ruochen0513.github.io
```

如果存在旧版 AppIndicator user service，默认安装会禁用它：

```bash
systemctl --user disable --now agent-status-indicator.service
```

使用 `--merge-codex-hooks` 时，会创建或修改：

```text
~/.codex/hooks.json
```

如果文件已经存在，安装脚本会在同目录创建时间戳备份：

```text
~/.codex/hooks.json.bak-YYYYMMDD-HHMMSS
```

使用 `--merge-claude-hooks` 时，会创建或修改：

```text
~/.claude/settings.json
```

如果文件已经存在，安装脚本会在同目录创建时间戳备份：

```text
~/.claude/settings.json.bak-YYYYMMDD-HHMMSS
```

## 不会做什么

- 不需要 root 权限。
- 不安装系统级文件。
- 不向网络发送数据。
- 默认版本不扫描运行中的进程。
- 不修改你的项目文件。
- 不读取完整的 Codex 或 Claude 对话日志。它只接收 agent runtime 传给 hook 的小型 JSON payload。

## 隐私与安全

hook payload 只用于提取状态、消息、事件名和 session id。状态 daemon 会把这份小状态保存在本机：

```text
~/.cache/agent-status-indicator/state.json
```

daemon 监听当前用户自己的 Unix socket：

```text
$XDG_RUNTIME_DIR/agent-status-indicator/agent-status.sock
```

socket 权限为 `0600`，只有当前用户可以写入。

## 卸载

```bash
./uninstall.sh
```

卸载脚本会删除已安装脚本、GNOME 插件、图标和 user systemd service。它不会编辑 `~/.codex/hooks.json` 或 `~/.claude/settings.json`；如果你曾经合并过 hook，需要手动移除对应条目。

保留本地状态/cache：

```bash
./uninstall.sh --keep-config
```

## 故障排查

如果圆点一直是灰色：

1. 检查扩展：

   ```bash
   gnome-extensions info agent-status-indicator@Ruochen0513.github.io
   ```

2. 检查 daemon：

   ```bash
   systemctl --user status agent-status.service
   ```

3. 查看当前状态：

   ```bash
   agent-status get
   ```

4. 重启 Codex 或 Claude Code，让 hooks 重新加载。

5. 在 Codex 中运行 `/hooks` 并 trust hook 定义。

如果 GNOME 刚安装后没有识别插件，X11 下可以刷新 GNOME Shell：

```text
Alt+F2，输入 r，回车
```

Wayland 下需要注销并重新登录。

如果授权后一直保持黄色，确认 Codex hook 配置中包含 `PostToolUse`，然后重启 Codex：

```bash
rg "PostToolUse" ~/.codex/hooks.json
```

## 项目结构

```text
bin/
  agent-status            状态 daemon 和 CLI
  agent-status-hook       Codex/Claude hook 适配器
  codex-status-exec       codex exec --json wrapper
  agent-status-indicator  旧版 AppIndicator UI
config/
  codex/hooks.json
  claude/settings.example.json
  systemd/*.service
gnome-extension/
  agent-status-indicator@Ruochen0513.github.io/
icons/
scripts/
  package-extension.sh
install.sh
uninstall.sh
```


## 许可证

MIT
