# Changelog

## Unreleased

- Prepare a GNOME Extensions submission archive containing only JavaScript, metadata and the MIT license.
- Replace the extension's Python reset subprocess with setup instructions, add missing-companion guidance, and make state reads asynchronous with cancellation across enable/disable cycles.
- Add archive validation and submission/reviewer documentation; keep declared compatibility limited to GNOME Shell 46.

- Verify actual Codex hook registration and trust with `doctor --check-codex`; untrusted hooks are reported as inactive even when configuration files exist.
- Generate Codex hook configurations from the installed runtime event capabilities and explain the mandatory trust review during installation.

- Replace two-minute active-session expiry with explicit lifecycle transitions; migrate version 2 state without expiring long tasks.
- Share the Python status model across CLI and display clients, use OS-managed writer locks, and remove socket dependence from hooks.
- Ignore subagent completion, compaction initialization, unknown events and ordinary notifications; track interruption/session end and guard against delayed events from old turns.
- Recover GNOME refreshes after bad state reads, use a consistently sized icon, and expose session counts and reset in its menu.
- Upgrade the older GNOME UUID in place and replace owned hook definitions without duplicating stale matchers or altering unrelated hooks.
- Add `agent-status doctor`, explicit corrupt-state recovery, desktop position recovery and wrapper cleanup.
- Add regression coverage for long tasks, real process concurrency, crashed lock owners, hook sequences, extension lifecycle and installer upgrades.

- Add a cross-platform floating desktop indicator for Linux, macOS, and Windows.
- Add persistent desktop position and customization for colors, size, opacity, click behavior, and always-on-top mode.
- Fix concurrent state updates, malformed state handling, and cross-session clearing of approval and stop events.
- Make the installer skip Linux-only systemd operations on other platforms.
- Add GNOME Shell top-bar indicator for Codex and Claude Code status.
- Add session-scoped status aggregation so concurrent agent sessions do not overwrite each other.
- Add hook adapters for Codex and Claude Code lifecycle events.
- Add optional `codex-status-exec` wrapper for non-interactive Codex runs.
- Add user-level systemd service for the local status daemon.
