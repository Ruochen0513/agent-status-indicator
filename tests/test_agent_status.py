from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "bin" / "agent-status"
LOADER = importlib.machinery.SourceFileLoader("agent_status", str(MODULE_PATH))
SPEC = importlib.util.spec_from_loader("agent_status", LOADER)
assert SPEC and SPEC.loader
agent_status = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(agent_status)


class AgentStatusTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.state_file = Path(self.temp_dir.name) / "state.json"
        agent_status.state_path = lambda: self.state_file
        agent_status.lock_path = lambda: self.state_file.with_suffix(".lock")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_malformed_state_is_recovered(self) -> None:
        self.state_file.write_text(json.dumps({"ttl_seconds": "invalid", "sessions": {"codex": {"s": {"updated_at": "invalid"}}}}))
        state = agent_status.load_state()
        self.assertEqual(state["ttl_seconds"], agent_status.DEFAULT_TTL_SECONDS)
        self.assertEqual(state["agents"]["codex"]["state"], "idle")

    def test_session_updates_do_not_clear_other_sessions(self) -> None:
        agent_status.apply_update("codex", "approval", session_id="codex:s1", event="PermissionRequest")
        agent_status.apply_update("codex", "working", session_id="codex:s2", event="PreToolUse")
        state = agent_status.load_state()
        self.assertEqual(state["sessions"]["codex"]["codex:s1"]["state"], "approval")
        self.assertEqual(state["agents"]["codex"]["state"], "approval")

        agent_status.apply_update("codex", "idle", session_id="codex:s1", event="Stop")
        state = agent_status.load_state()
        self.assertIn("codex:s2", state["sessions"]["codex"])
        self.assertEqual(state["agents"]["codex"]["state"], "working")

    def test_concurrent_updates_are_serialized(self) -> None:
        errors: list[Exception] = []

        def update(index: int) -> None:
            try:
                agent_status.apply_update("claude", "working", session_id=f"claude:{index}")
            except Exception as exc:  # pragma: no cover - assertion below reports it
                errors.append(exc)

        threads = [threading.Thread(target=update, args=(index,)) for index in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(errors, [])
        state = agent_status.load_state()
        self.assertEqual(len(state["sessions"]["claude"]), 8)

    def test_update_all_idle_clears_every_session(self) -> None:
        agent_status.apply_update("all", "working", session_id="shared")
        agent_status.apply_update("all", "idle")
        state = agent_status.load_state()
        self.assertEqual(state["sessions"]["codex"], {})
        self.assertEqual(state["sessions"]["claude"], {})

    def test_desktop_display_expires_direct_file_updates(self) -> None:
        desktop_path = Path(__file__).resolve().parents[1] / "desktop" / "agent_status_desktop.py"
        desktop_spec = importlib.util.spec_from_file_location("desktop_status", desktop_path)
        assert desktop_spec and desktop_spec.loader
        desktop_module = importlib.util.module_from_spec(desktop_spec)
        desktop_spec.loader.exec_module(desktop_module)
        state = {
            "ttl_seconds": 2,
            "sessions": {
                "codex": {"codex:old": {"state": "working", "updated_at": time.time() - 10}},
                "claude": {},
            },
        }
        visible = desktop_module.display_state(state)
        self.assertEqual(visible["agents"]["codex"]["state"], "idle")


if __name__ == "__main__":
    unittest.main()
