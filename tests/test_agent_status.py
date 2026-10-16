from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bin"))


def load_module(name, path):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


agent_status = load_module("agent_status", ROOT / "bin/agent-status")
hook = load_module("status_hook", ROOT / "bin/agent-status-hook")
desktop = load_module("desktop_status", ROOT / "desktop/agent_status_desktop.py")
wrapper = load_module("exec_status", ROOT / "bin/codex-status-exec")


class AgentStatusTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.state_file = Path(self.temp_dir.name) / "state.json"
        self.patch_path = patch.object(agent_status, "state_path", lambda: self.state_file)
        self.patch_path.start()
        self.addCleanup(self.patch_path.stop)

    def test_invalid_json_is_reported_without_data_loss(self):
        self.state_file.write_text('{broken')
        with self.assertRaises(ValueError):
            agent_status.apply_update("codex", "working")
        self.assertEqual(self.state_file.read_text(), '{broken')
        agent_status.apply_update("all", "idle")
        backups = list(self.state_file.parent.glob("state.corrupt-*.json"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(), '{broken')
        self.assertEqual(agent_status.load_state()["agents"]["codex"]["state"], "idle")

    def test_malformed_records_are_normalized(self):
        for malformed in (None, [], "invalid"):
            state = agent_status.normalize_state({"agents": malformed, "sessions": {"codex": malformed}})
            self.assertEqual(state["agents"]["codex"]["state"], "idle")
        state = agent_status.normalize_state({"updated_at": float('nan'), "sessions": {"codex": {
            "a": {"state": [], "updated_at": "invalid"},
            "b": {"state": "working", "updated_at": float('inf')},
        }}})
        json.dumps(state, allow_nan=False)
        self.assertEqual(state["agents"]["codex"]["active_sessions"], 1)

    def test_active_states_never_expire_even_with_old_ttl(self):
        for name in ("working", "approval", "error"):
            with self.subTest(state=name):
                state = {"version": 2, "ttl_seconds": 1, "sessions": {
                    "codex": {"s": {"state": name, "updated_at": time.time() - 86400 * 30}},
                }}
                visible = agent_status.normalize_state(state)
                self.assertEqual(visible["agents"]["codex"]["state"], name)
                self.assertEqual(desktop.display_state(state)["agents"]["codex"], visible["agents"]["codex"])
                self.assertNotIn("ttl_seconds", visible)
                self.assertEqual(visible["version"], 3)

    def test_summary_only_migration(self):
        state = agent_status.normalize_state({"agents": {"codex": {"state": "working"}}})
        self.assertEqual(state["agents"]["codex"]["state"], "working")
        state["sessions"]["codex"].clear()
        self.assertEqual(agent_status.normalize_state(state)["agents"]["codex"]["state"], "idle")

    def test_session_updates_do_not_clear_other_sessions(self):
        agent_status.apply_update("codex", "approval", session_id="s1", event="PermissionRequest")
        agent_status.apply_update("codex", "working", session_id="s2", event="PreToolUse")
        self.assertEqual(agent_status.load_state()["agents"]["codex"]["state"], "approval")
        agent_status.apply_update("codex", "idle", session_id="s1", event="Stop")
        state = agent_status.load_state()
        self.assertEqual(state["agents"]["codex"]["state"], "working")
        self.assertIn("s2", state["sessions"]["codex"])

    def test_approval_resume_and_error_recovery(self):
        for name in ("working", "approval", "working", "error", "working", "idle"):
            result = agent_status.apply_update("claude", name, session_id="s")
            self.assertEqual(result["agents"]["claude"]["state"], name)
            self.assertEqual(agent_status.load_state()["agents"]["claude"]["state"], name)

    def test_priority_across_agents(self):
        agent_status.apply_update("codex", "working", session_id="s1")
        agent_status.apply_update("claude", "approval", session_id="s2")
        self.assertEqual(desktop.combined_state(agent_status.load_state()), "approval")
        agent_status.apply_update("codex", "error", session_id="s3")
        self.assertEqual(desktop.combined_state(agent_status.load_state()), "error")

    def test_concurrent_updates_are_serialized(self):
        errors = []
        def update(index):
            try:
                agent_status.apply_update("claude", "working", session_id=f"claude:{index}")
            except Exception as exc:
                errors.append(exc)
        threads = [threading.Thread(target=update, args=(index,)) for index in range(24)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(errors, [])
        self.assertEqual(len(agent_status.load_state()["sessions"]["claude"]), 24)

    @unittest.skipUnless(os.name == "posix", "POSIX lock crash integration")
    def test_process_concurrency_and_lock_recovery_after_kill(self):
        cache = Path(self.temp_dir.name) / "cache"
        env = {**os.environ, "XDG_CACHE_HOME": str(cache)}
        command = [sys.executable, str(ROOT / "bin/agent-status"), "update", "codex", "working", "--session"]
        processes = [subprocess.Popen(command + [str(index)], env=env) for index in range(12)]
        for proc in processes:
            self.assertEqual(proc.wait(timeout=10), 0)
        path = cache / "agent-status-indicator/state.json"
        self.assertEqual(len(json.loads(path.read_text())["sessions"]["codex"]), 12)
        holder = subprocess.Popen([sys.executable, "-u", "-c", "import fcntl,sys,time; f=open(sys.argv[1],'a'); fcntl.flock(f,fcntl.LOCK_EX); print('locked',flush=True); time.sleep(30)", str(path.with_suffix('.lock'))], stdout=subprocess.PIPE, text=True)
        self.addCleanup(lambda: holder.poll() is None and holder.kill())
        self.assertEqual(holder.stdout.readline().strip(), "locked")
        holder.kill()
        holder.wait(timeout=3)
        holder.stdout.close()
        self.assertEqual(subprocess.run(command + ["after-crash"], env=env, timeout=5).returncode, 0)
        self.assertEqual(len(json.loads(path.read_text())["sessions"]["codex"]), 13)

    def test_late_previous_turn_and_stopped_turn_cannot_overwrite(self):
        ts = time.time()
        agent_status.apply_update("codex", "working", session_id="s", event="UserPromptSubmit", turn_id="t1", observed_at=ts)
        agent_status.apply_update("codex", "working", session_id="s", event="UserPromptSubmit", turn_id="t2", observed_at=ts + 1)
        agent_status.apply_update("codex", "idle", session_id="s", event="Stop", turn_id="t1", observed_at=ts + 2)
        self.assertEqual(agent_status.load_state()["agents"]["codex"]["state"], "working")
        agent_status.apply_update("codex", "idle", session_id="s", event="Stop", turn_id="t2", observed_at=ts + 3)
        agent_status.apply_update("codex", "working", session_id="s", event="PostToolUse", turn_id="t2", observed_at=ts + 4)
        self.assertEqual(agent_status.load_state()["agents"]["codex"]["state"], "idle")
        agent_status.apply_update("codex", "working", session_id="s", event="UserPromptSubmit", turn_id="t3", observed_at=ts + 5)
        agent_status.apply_update("codex", "error", session_id="s", observed_at=ts)
        self.assertEqual(agent_status.load_state()["agents"]["codex"]["state"], "working")

    def test_agent_reset_does_not_clear_other_agent(self):
        agent_status.apply_update("codex", "working", session_id="c1")
        agent_status.apply_update("claude", "working", session_id="c2")
        agent_status.apply_update("codex", "idle")
        state = agent_status.load_state()
        self.assertEqual(state["sessions"]["codex"], {})
        self.assertEqual(state["agents"]["claude"]["state"], "working")

    def test_update_all_idle_clears_every_session(self):
        agent_status.apply_update("all", "working", session_id="shared")
        agent_status.apply_update("all", "idle")
        for sessions in agent_status.load_state()["sessions"].values():
            self.assertEqual(sessions, {})

    def test_silent_socket_client_is_bounded(self):
        server, client = socket.socketpair()
        with client:
            started = time.monotonic()
            thread = threading.Thread(target=agent_status.handle_client, args=(server,))
            thread.start()
            thread.join(timeout=2)
            self.assertFalse(thread.is_alive())
            self.assertLess(time.monotonic() - started, 2)
            self.assertFalse(json.loads(client.recv(4096))["ok"])

    def test_bad_socket_payload_does_not_break_next_update(self):
        for payload in (b'[]\n', b'{"action":"bad"}\n', b'x' * 70000 + b'\n'):
            server, client = socket.socketpair()
            with client:
                thread = threading.Thread(target=agent_status.handle_client, args=(server,))
                thread.start()
                client.sendall(payload)
                self.assertFalse(json.loads(client.recv(4096))["ok"])
                thread.join(timeout=3)
        agent_status.apply_update("codex", "working")
        self.assertEqual(agent_status.load_state()["agents"]["codex"]["state"], "working")


class CodexDiagnosticsTests(unittest.TestCase):
    def response(self, trust="trusted", enabled=True, events=("userPromptSubmit", "stop")):
        return {"result": {"data": [{"errors": [], "hooks": [
            {"eventName": event, "trustStatus": trust, "enabled": enabled,
             "command": "/path/agent-status-hook --agent codex", "sourcePath": "/path/hooks.json"}
            for event in events
        ]}]}}

    def test_configured_but_untrusted_hooks_are_not_ready(self):
        for trust in ("untrusted", "modified"):
            result = agent_status.codex_hook_report(self.response(trust=trust), ["UserPromptSubmit", "Stop"])
            self.assertEqual(result["status"], "needs_trust")

    def test_disabled_missing_and_unsupported_hooks_are_distinguished(self):
        self.assertEqual(agent_status.codex_hook_report(self.response(enabled=False), [])["status"], "disabled")
        self.assertEqual(agent_status.codex_hook_report(self.response(events=()), [])["status"], "not_registered")
        self.assertEqual(agent_status.codex_hook_report(self.response(events=("preToolUse",)), [])["status"], "missing_lifecycle_events")
        result = agent_status.codex_hook_report(self.response(), ["UserPromptSubmit", "Stop", "SessionEnd", "Interrupt"])
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["configured_events_not_registered"], ["SessionEnd", "Interrupt"])

    def test_rpc_and_configuration_errors_are_not_ready(self):
        self.assertEqual(agent_status.codex_hook_report({"error": "unsupported method"}, [])["status"], "unavailable")
        response = self.response()
        response["result"]["data"][0]["errors"] = [{"message": "bad configuration"}]
        self.assertEqual(agent_status.codex_hook_report(response, [])["status"], "configuration_error")

    def test_unrelated_trusted_hook_does_not_count_as_integration(self):
        response = self.response()
        for hook_info in response["result"]["data"][0]["hooks"]:
            hook_info["command"] = "some-other-hook"
        self.assertEqual(agent_status.codex_hook_report(response, [])["status"], "not_registered")


class HookTests(unittest.TestCase):
    def test_nonterminal_events_are_ignored(self):
        for event, payload in [("SubagentStop", {}), ("SubagentStart", {}), ("Unknown", {}), ("Notification", {}), ("Notification", {"notification_type": "idle_prompt"}), ("SessionStart", {"source": "compact"})]:
            self.assertIsNone(hook.state_for_event(event, payload))
        self.assertEqual(hook.state_for_event("Notification", {"notification_type": "permission_prompt"}), "approval")
        self.assertEqual(hook.state_for_event("Interrupt", {}), "idle")
        self.assertEqual(hook.state_for_event("SessionEnd", {}), "idle")

    def test_identity_uses_ids_before_transcript_and_directory(self):
        self.assertEqual(hook.session_from_payload({"cwd": "/same", "params": {"thread_id": "t"}}, "codex"), "codex:t")
        self.assertNotEqual(hook.session_from_payload({"session_id": "a", "cwd": "/same"}, "codex"), hook.session_from_payload({"session_id": "b", "cwd": "/same"}, "codex"))
        with patch.dict(os.environ, {"PWD": "/same"}, clear=True):
            self.assertEqual(hook.session_from_payload({"cwd": "/same"}, "codex"), "")

    def test_real_hook_lifecycle_without_daemon(self):
        with tempfile.TemporaryDirectory() as directory:
            env = {**os.environ, "XDG_CACHE_HOME": directory}
            path = Path(directory) / "agent-status-indicator/state.json"
            for event, extra, expected in [
                ("UserPromptSubmit", {}, "working"),
                ("SessionStart", {"source": "compact"}, "working"),
                ("SubagentStop", {"agent_id": "child"}, "working"),
                ("Notification", {"notification_type": "idle_prompt"}, "working"),
                ("PermissionRequest", {}, "approval"),
                ("PostToolUse", {}, "working"),
                ("Interrupt", {}, "idle"),
                ("UserPromptSubmit", {"turn_id": "next"}, "working"),
                ("SessionEnd", {"turn_id": ""}, "idle"),
            ]:
                payload = {"session_id": "s", "turn_id": "turn", **extra}
                result = subprocess.run([sys.executable, str(ROOT / "bin/agent-status-hook"), "--agent", "codex", "--event", event], input=json.dumps(payload), text=True, env=env, capture_output=True, timeout=5)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(path.read_text())["agents"]["codex"]["state"], expected, event)

    def test_invalid_payload_does_not_create_phantom_work(self):
        with tempfile.TemporaryDirectory() as directory:
            env = {"PATH": os.environ["PATH"], "XDG_CACHE_HOME": directory}
            for payload in ("null", "[]", "bad json"):
                result = subprocess.run([sys.executable, str(ROOT / "bin/agent-status-hook"), "--agent", "codex", "--event", "PreToolUse"], input=payload, text=True, env=env, capture_output=True)
                self.assertEqual(result.returncode, 1)
            self.assertFalse((Path(directory) / "agent-status-indicator/state.json").exists())


class WrapperTests(unittest.TestCase):
    def test_wrapper_keeps_one_identity_and_cleans_up(self):
        proc = unittest.mock.MagicMock()
        proc.stdout = ['null\n', 'not json\n', '{"type":"thread.started","thread_id":"abc"}\n', '{"type":"turn.completed"}\n']
        proc.wait.return_value = 0
        with patch.object(wrapper.subprocess, "Popen", return_value=proc), patch.object(wrapper, "update") as update:
            self.assertEqual(wrapper.main(["hello"]), 0)
            self.assertEqual(len({call.args[2] for call in update.call_args_list}), 1)
            self.assertEqual(update.call_args_list[-1].args[0], "idle")

    def test_spawn_failure_and_failed_turn_stay_red(self):
        with patch.object(wrapper.subprocess, "Popen", side_effect=FileNotFoundError("codex missing")), patch.object(wrapper, "update") as update:
            self.assertEqual(wrapper.main([]), 127)
            self.assertEqual(update.call_args_list[-1].args[0], "error")
        proc = unittest.mock.MagicMock()
        proc.stdout = ['{"type":"turn.failed"}\n']
        proc.wait.return_value = 0
        with patch.object(wrapper.subprocess, "Popen", return_value=proc), patch.object(wrapper, "update") as update:
            wrapper.main([])
            self.assertEqual(update.call_args_list[-1].args[0], "error")


class DesktopTests(unittest.TestCase):
    def test_bad_state_read_preserves_last_good_then_recovers(self):
        indicator = desktop.DesktopIndicator.__new__(desktop.DesktopIndicator)
        indicator.state = agent_status.normalize_state({"sessions": {"codex": {"s": {"state": "working"}}}})
        indicator.config = dict(desktop.DEFAULT_CONFIG)
        indicator.canvas = unittest.mock.MagicMock()
        indicator.root = unittest.mock.MagicMock()
        with patch.object(desktop, "read_state", side_effect=ValueError("broken")):
            indicator._refresh()
        self.assertEqual(desktop.combined_state(indicator.state), "working")
        self.assertIn("broken", indicator.read_error)
        self.assertEqual(indicator.canvas.create_oval.call_args.kwargs["fill"], desktop.DEFAULT_COLORS["error"])
        with patch.object(desktop, "read_state", return_value=indicator.state):
            indicator._refresh()
        self.assertEqual(indicator.read_error, "")
        self.assertEqual(indicator.canvas.create_oval.call_args.kwargs["fill"], desktop.DEFAULT_COLORS["working"])

    def test_poll_is_rescheduled_on_failure(self):
        indicator = desktop.DesktopIndicator.__new__(desktop.DesktopIndicator)
        indicator.root = unittest.mock.MagicMock()
        indicator._refresh = unittest.mock.Mock(side_effect=ValueError("bad"))
        with self.assertRaises(ValueError):
            indicator._poll()
        indicator.root.after.assert_called_once_with(400, indicator._poll)

    def test_offscreen_position_is_recovered(self):
        indicator = desktop.DesktopIndicator.__new__(desktop.DesktopIndicator)
        indicator.config = {**desktop.DEFAULT_CONFIG, "x": 9999, "y": -500}
        indicator.canvas = unittest.mock.MagicMock()
        indicator.root = unittest.mock.MagicMock()
        indicator.root.winfo_screenwidth.return_value = 1920
        indicator.root.winfo_screenheight.return_value = 1080
        indicator.transparent_color = '#010203'
        indicator._set_geometry()
        indicator.root.geometry.assert_called_once_with('38x38+1882+0')


if __name__ == "__main__":
    unittest.main()
