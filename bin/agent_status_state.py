"""Canonical, event-driven status model shared by Python clients.

Silence is not completion: active sessions persist until a terminal event or reset.
Version 2 TTL settings are intentionally ignored on migration.
"""
from __future__ import annotations

import math
import time
from typing import Any

AGENTS = ("codex", "claude")
PRIORITY = {"idle": 0, "working": 1, "approval": 2, "error": 3}
VALID_STATES = set(PRIORITY)


def timestamp(value: Any, fallback: float) -> float:
    try:
        result = float(value)
        return result if math.isfinite(result) and result >= 0 else fallback
    except (TypeError, ValueError, OverflowError):
        return fallback


def empty_state() -> dict[str, Any]:
    return normalize_state({})


def aggregate_agent(agent: str, sessions: dict, current: float) -> dict[str, Any]:
    active = [(sid, item) for sid, item in sessions.items() if item["state"] != "idle"]
    result = {"state": "idle", "message": "", "updated_at": current, "active_sessions": len(active)}
    if active:
        sid, item = max(active, key=lambda entry: (PRIORITY[entry[1]["state"]], entry[1]["updated_at"], entry[0]))
        result.update(item, session=sid)
    return result


def normalize_state(state: Any) -> dict[str, Any]:
    current = time.time()
    if not isinstance(state, dict):
        state = {}
    raw_sessions = state.get("sessions")
    raw_agents = state.get("agents")
    sessions = {}
    for agent in AGENTS:
        items = raw_sessions.get(agent, {}) if isinstance(raw_sessions, dict) else {}
        # Migrate old summary-only state once; session records are authoritative.
        if raw_sessions is None and isinstance(raw_agents, dict):
            item = raw_agents.get(agent)
            if isinstance(item, dict) and isinstance(item.get("state"), str) and item["state"] in VALID_STATES - {"idle"}:
                items = {f"{agent}:legacy": item}
        cleaned = {}
        for sid, item in (items.items() if isinstance(items, dict) else []):
            if not isinstance(item, dict) or not isinstance(item.get("state"), str):
                continue
            if item["state"] not in VALID_STATES:
                continue
            if item["state"] == "idle" and current - timestamp(item.get("updated_at"), current) > 86400:
                continue
            cleaned[str(sid)] = {
                "state": item["state"],
                "message": str(item.get("message") or "")[:500],
                "event": str(item.get("event") or ""),
                "turn_id": str(item.get("turn_id") or ""),
                "updated_at": timestamp(item.get("updated_at"), current),
            }
        sessions[agent] = cleaned
    return {
        "version": 3,
        "updated_at": timestamp(state.get("updated_at"), current),
        "sessions": sessions,
        "agents": {agent: aggregate_agent(agent, sessions[agent], current) for agent in AGENTS},
    }


def combined_state(state: dict) -> str:
    agents = state.get("agents")
    if not isinstance(agents, dict):
        return "idle"
    states = [item.get("state") for item in agents.values() if isinstance(item, dict)]
    return max((s for s in states if isinstance(s, str) and s in PRIORITY), key=PRIORITY.get, default="idle")
