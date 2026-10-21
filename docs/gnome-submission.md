# GNOME Extensions submission

This document prepares a first review submission. It does not mean the extension has been uploaded or approved.

## Upload artifact

Build from the repository root:

```bash
bash scripts/package-extension.sh
```

Upload `agent-status-indicator@Ruochen0513.github.io.shell-extension.zip` at <https://extensions.gnome.org/upload/> after signing in. The archive is produced with `gnome-extensions pack` when available, with a ZIP fallback for other platforms. Its only files are `metadata.json`, `extension.js`, `state.js` and `LICENSE`. The build validates the archive before reporting success.

Keep the UUID `agent-status-indicator@Ruochen0513.github.io` for all marketplace updates. The older local-install UUID is not the marketplace identity. The initial display version is `1.0.0`; the website assigns its own numeric submission version. Only GNOME Shell 46 is declared. Test additional Shell versions before adding them.

## Listing text

Name:

> Agent Status Indicator

Description:

> Show local Codex and Claude Code session status in the top bar: working, waiting for approval, idle, or error.
>
> Requires the separately installed agent-status companion and configured agent hooks. See the project website for setup and Codex hook trust instructions. The extension reads only a local status file; it does not access conversation logs or the network.

Project / issue tracker:

- <https://github.com/Ruochen0513/agent-status-indicator>
- <https://github.com/Ruochen0513/agent-status-indicator/issues>

If screenshots are requested, capture the actual GNOME 46 top bar and expanded status menu with a real or explicitly identified demo session. Do not include unrelated desktop content or private agent messages. No screenshot has been fabricated for this submission.

## Reviewer notes

The archive contains the GNOME presentation client only. It monitors `$XDG_CACHE_HOME/agent-status-indicator/state.json` (or `~/.cache/agent-status-indicator/state.json`). The separately installed Python companion writes this file atomically from agent lifecycle callbacks. Installing the companion and enabling hooks are deliberate user actions outside the extension; the extension does not install or run Python, a shell command or a custom subprocess.

The extension reads the file asynchronously once per second with one read in flight. `disable()` cancels pending reads, removes the timer and destroys the panel button. Callbacks from a previous enable cycle cannot update new actors. Missing data gives a visible setup message, and malformed data gives an error with recovery on the next read. The only external action is opening the public setup URL with the desktop's default URI handler when the user selects it.

The status priority is error, approval, working, idle. Active states do not expire based on elapsed time. The extension reads status summaries, not conversation transcripts. It has no clipboard, telemetry, network, lock-screen mode, administrator or password access. The source is readable ES-module JavaScript. The MIT license is included; the companion and its installers are not in the archive.

## Validation and remaining release actions

On 2026-10-21, all 32 Python tests, the asynchronous JavaScript harness, module syntax checks and shell syntax checks passed. The archive was built with GNOME's pack command and passed content validation. The exact packaged UI has not yet received a final manual smoke test in a fresh GNOME 46 session.

Run:

```bash
node --experimental-vm-modules tests/test_extension.mjs
python3 -m unittest discover -s tests -v
bash -n install.sh scripts/*.sh uninstall.sh
bash scripts/package-extension.sh
```

The JavaScript harness tests state priority, long tasks, asynchronous reads, read errors, cancellation, missing-file guidance, and callbacks crossing disable/enable cycles. Python tests cover the companion, installation and archive validation. These checks do not replace a final manual GNOME 46 smoke test of the exact packaged version.

Before submitting:

1. A human maintainer must read and understand the JavaScript, be able to explain it to reviewers, and undertake ongoing maintenance. Development used AI assistance; do not represent the work as entirely handwritten or hide that fact if asked.
2. Test this exact package in a GNOME 46 session: missing companion, working/approval/idle/error, recovery from malformed JSON, and disable/enable (including locking/unlocking). Keep the result and environment in the release notes.
3. Publish the corresponding source revision so reviewers can inspect the same code.
4. Sign in, select the ZIP, read the current upload agreement, and approve its terms personally before final submission. If this chat assists with submission, confirmation of any legal agreement must happen at that step.
5. Save the actual review URL and respond to reviewer feedback. A successful upload is a request for review, not immediate public availability.

References checked on 2026-10-21: [review rules](https://gjs.guide/extensions/review-guidelines/review-guidelines.html), [maintainership guidance](https://gjs.guide/extensions/review-guidelines/best-practices.html), [metadata and packaging](https://gjs.guide/extensions/overview/anatomy.html).
