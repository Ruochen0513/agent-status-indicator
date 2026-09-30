# Changelog

## Unreleased

- Add a cross-platform floating desktop indicator for Linux, macOS, and Windows.
- Add persistent desktop position and customization for colors, size, opacity, click behavior, and always-on-top mode.
- Fix concurrent state updates, malformed state handling, and cross-session clearing of approval and stop events.
- Make the installer skip Linux-only systemd operations on other platforms.
- Add GNOME Shell top-bar indicator for Codex and Claude Code status.
- Add session-scoped status aggregation so concurrent agent sessions do not overwrite each other.
- Add hook adapters for Codex and Claude Code lifecycle events.
- Add optional `codex-status-exec` wrapper for non-interactive Codex runs.
- Add user-level systemd service for the local status daemon.
