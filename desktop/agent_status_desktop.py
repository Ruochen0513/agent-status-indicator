#!/usr/bin/env python3
"""Cross-platform floating desktop indicator for local agent status."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tkinter as tk
import time
from pathlib import Path
from tkinter import colorchooser, messagebox, ttk
from typing import Any


APP_NAME = "agent-status-indicator"
STATES = ("idle", "working", "approval", "error")
PRIORITY = {"idle": 0, "working": 1, "approval": 2, "error": 3}
DEFAULT_COLORS = {
    "idle": "#8b949e",
    "working": "#2ea043",
    "approval": "#d29922",
    "error": "#f85149",
}
DEFAULT_CONFIG: dict[str, Any] = {
    "x": None,
    "y": None,
    "size": 38,
    "opacity": 0.96,
    "always_on_top": True,
    "click_action": "menu",
    "colors": DEFAULT_COLORS,
}
COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


def config_dir() -> Path:
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / APP_NAME
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / APP_NAME


def state_path() -> Path:
    if sys.platform == "win32":
        root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    elif sys.platform == "darwin":
        root = Path.home() / "Library" / "Caches"
    else:
        root = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return root / APP_NAME / "state.json"


def config_path() -> Path:
    return config_dir() / "desktop.json"


def load_config() -> dict[str, Any]:
    config = json.loads(json.dumps(DEFAULT_CONFIG))
    try:
        loaded = json.loads(config_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        loaded = {}
    if not isinstance(loaded, dict):
        loaded = {}
    for key in ("x", "y", "size", "opacity", "always_on_top", "click_action"):
        if key in loaded:
            config[key] = loaded[key]
    if isinstance(loaded.get("colors"), dict):
        config["colors"].update(loaded["colors"])
    return normalize_config(config)


def normalize_config(config: dict[str, Any]) -> dict[str, Any]:
    for key in ("x", "y"):
        value = config.get(key)
        if not isinstance(value, int):
            config[key] = None
    try:
        config["size"] = max(24, min(128, int(config.get("size", 38))))
    except (TypeError, ValueError):
        config["size"] = 38
    try:
        config["opacity"] = max(0.35, min(1.0, float(config.get("opacity", 0.96))))
    except (TypeError, ValueError):
        config["opacity"] = 0.96
    config["always_on_top"] = bool(config.get("always_on_top", True))
    if config.get("click_action") not in {"menu", "settings", "none"}:
        config["click_action"] = "menu"
    colors = config.setdefault("colors", {})
    for state in STATES:
        if not isinstance(colors.get(state), str) or not COLOR_RE.fullmatch(colors[state]):
            colors[state] = DEFAULT_COLORS[state]
    return config


def save_config(config: dict[str, Any]) -> None:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(normalize_config(config), indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def read_state() -> dict[str, Any]:
    try:
        loaded = json.loads(state_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"agents": {}}
    return loaded if isinstance(loaded, dict) else {"agents": {}}


def display_state(state: dict[str, Any]) -> dict[str, Any]:
    """Rebuild agent summaries so direct file updates also honor session TTL."""
    try:
        ttl = max(1, int(state.get("ttl_seconds", 120)))
    except (TypeError, ValueError):
        ttl = 120
    sessions = state.get("sessions")
    if not isinstance(sessions, dict):
        return state
    agents: dict[str, dict[str, Any]] = {}
    for agent in ("codex", "claude"):
        items = sessions.get(agent)
        if not isinstance(items, dict):
            items = {}
        best: dict[str, Any] = {"state": "idle", "message": "", "active_sessions": 0}
        for session_id, item in items.items():
            if not isinstance(item, dict):
                continue
            state_name = item.get("state", "idle")
            if state_name not in STATES:
                continue
            try:
                age = time.time() - float(item.get("updated_at", time.time()))
            except (TypeError, ValueError):
                age = 0
            if (state_name in {"idle", "working"} and age > ttl) or (state_name == "error" and age > ttl * 10):
                continue
            if state_name != "idle":
                best["active_sessions"] += 1
            if PRIORITY[state_name] > PRIORITY[best["state"]]:
                best.update({"state": state_name, "message": str(item.get("message") or ""), "session": session_id})
        agents[agent] = best
    state["agents"] = agents
    return state


def combined_state(state: dict[str, Any]) -> str:
    result = "idle"
    agents = state.get("agents")
    if not isinstance(agents, dict):
        return result
    for item in agents.values():
        if not isinstance(item, dict):
            continue
        state_name = item.get("state", "idle")
        if PRIORITY.get(state_name, 0) > PRIORITY[result]:
            result = state_name
    return result


def agent_summary(state: dict[str, Any]) -> str:
    agents = state.get("agents")
    if not isinstance(agents, dict):
        agents = {}
    parts = []
    for agent in ("codex", "claude"):
        item = agents.get(agent)
        item = item if isinstance(item, dict) else {}
        status = str(item.get("state", "idle"))
        message = str(item.get("message") or "").strip()
        parts.append(f"{agent.capitalize()}: {status}" + (f" ({message})" if message else ""))
    return " | ".join(parts)


def status_cli() -> str | None:
    bundled = Path(__file__).resolve().parent.parent / "bin" / "agent-status"
    if bundled.exists():
        return str(bundled)
    return shutil.which("agent-status")


class DesktopIndicator:
    def __init__(self) -> None:
        self.config = load_config()
        self.state: dict[str, Any] = {"agents": {}}
        self.state_mtime: float | None = None
        self.drag_start: tuple[int, int, int, int] | None = None
        self.settings_window: tk.Toplevel | None = None

        self.root = tk.Tk()
        self.root.title("Agent Status Indicator")
        self.root.overrideredirect(True)
        self.root.resizable(False, False)
        self._configure_transparency()
        self.canvas = tk.Canvas(self.root, highlightthickness=0, bd=0)
        self.canvas.pack()
        self.canvas.bind("<ButtonPress-1>", self._drag_start)
        self.canvas.bind("<B1-Motion>", self._drag_move)
        self.canvas.bind("<ButtonRelease-1>", self._drag_end)
        self.canvas.bind("<Button-3>", self._show_menu)
        self.canvas.bind("<Double-Button-1>", lambda _event: self.open_settings())
        self._set_geometry()
        self._refresh()
        self.root.after(400, self._poll)

    def _configure_transparency(self) -> None:
        self.transparent_color = "#010203"
        self.root.configure(bg=self.transparent_color)
        if sys.platform == "win32":
            try:
                self.root.wm_attributes("-transparentcolor", self.transparent_color)
            except tk.TclError:
                pass
        try:
            self.root.wm_attributes("-topmost", self.config["always_on_top"])
            self.root.wm_attributes("-alpha", self.config["opacity"])
        except tk.TclError:
            pass

    def _set_geometry(self) -> None:
        size = self.config["size"]
        self.canvas.configure(width=size, height=size, bg=self.transparent_color)
        x, y = self.config.get("x"), self.config.get("y")
        if not isinstance(x, int) or not isinstance(y, int):
            self.root.update_idletasks()
            x = max(0, self.root.winfo_screenwidth() - size - 24)
            y = max(0, self.root.winfo_screenheight() - size - 72)
        self.root.geometry(f"{size}x{size}+{x}+{y}")

    def _refresh(self) -> None:
        try:
            mtime = state_path().stat().st_mtime
        except OSError:
            mtime = None
        if mtime != self.state_mtime:
            self.state_mtime = mtime
            self.state = display_state(read_state())
        status = combined_state(self.state)
        size = self.config["size"]
        pad = max(3, size // 10)
        self.canvas.delete("all")
        self.canvas.create_oval(pad, pad, size - pad, size - pad, fill=self.config["colors"][status], outline="#ffffff", width=1)
        summary = agent_summary(self.state)
        self.canvas.configure(cursor="hand2" if self.config["click_action"] != "none" else "arrow")
        self.root.title(f"Agent Status: {status} | {summary}")

    def _poll(self) -> None:
        self._refresh()
        self.root.after(400, self._poll)

    def _drag_start(self, event: tk.Event) -> None:
        self.drag_start = (event.x_root, event.y_root, self.root.winfo_x(), self.root.winfo_y())

    def _drag_move(self, event: tk.Event) -> None:
        if not self.drag_start:
            return
        start_x, start_y, origin_x, origin_y = self.drag_start
        self.root.geometry(f"+{origin_x + event.x_root - start_x}+{origin_y + event.y_root - start_y}")

    def _drag_end(self, event: tk.Event) -> None:
        if not self.drag_start:
            return
        start_x, start_y, _, _ = self.drag_start
        moved = abs(event.x_root - start_x) + abs(event.y_root - start_y)
        self.config["x"], self.config["y"] = self.root.winfo_x(), self.root.winfo_y()
        self.drag_start = None
        save_config(self.config)
        if moved < 5:
            action = self.config["click_action"]
            if action == "menu":
                self._show_menu(event)
            elif action == "settings":
                self.open_settings()

    def _show_menu(self, event: tk.Event) -> None:
        menu = tk.Menu(self.root, tearoff=False)
        menu.add_command(label=f"Agent Status: {combined_state(self.state)}", state="disabled")
        menu.add_command(label=agent_summary(self.state), state="disabled")
        menu.add_separator()
        menu.add_command(label="Settings", command=self.open_settings)
        menu.add_command(label="Set all idle", command=self.set_all_idle)
        menu.add_separator()
        menu.add_command(label="Quit", command=self.root.destroy)
        menu.tk_popup(event.x_root, event.y_root)

    def set_all_idle(self) -> None:
        executable = status_cli()
        if executable:
            command = [executable, "update", "all", "idle"]
            if not os.access(executable, os.X_OK) and executable.endswith((".py", "agent-status")):
                command.insert(0, sys.executable)
            subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def open_settings(self) -> None:
        if self.settings_window and self.settings_window.winfo_exists():
            self.settings_window.lift()
            return
        window = self.settings_window = tk.Toplevel(self.root)
        window.title("Agent Status Indicator Settings")
        window.resizable(False, False)
        window.transient(self.root)
        frame = ttk.Frame(window, padding=14)
        frame.grid(sticky="nsew")
        size_var = tk.IntVar(value=self.config["size"])
        opacity_var = tk.DoubleVar(value=self.config["opacity"])
        top_var = tk.BooleanVar(value=self.config["always_on_top"])
        action_var = tk.StringVar(value=self.config["click_action"])
        color_vars = {state: tk.StringVar(value=self.config["colors"][state]) for state in STATES}

        ttk.Label(frame, text="Size").grid(row=0, column=0, sticky="w", pady=4)
        ttk.Spinbox(frame, from_=24, to=128, textvariable=size_var, width=8).grid(row=0, column=1, sticky="w")
        ttk.Label(frame, text="Opacity").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Scale(frame, from_=0.35, to=1.0, variable=opacity_var, orient="horizontal", length=160).grid(row=1, column=1, sticky="w")
        ttk.Checkbutton(frame, text="Keep on top", variable=top_var).grid(row=2, column=0, columnspan=2, sticky="w", pady=4)
        ttk.Label(frame, text="Click action").grid(row=3, column=0, sticky="w", pady=4)
        ttk.OptionMenu(frame, action_var, action_var.get(), "menu", "settings", "none").grid(row=3, column=1, sticky="w")
        ttk.Label(frame, text="Status colors").grid(row=4, column=0, sticky="nw", pady=(10, 4))
        colors_frame = ttk.Frame(frame)
        colors_frame.grid(row=4, column=1, sticky="w", pady=(10, 4))
        for index, state in enumerate(STATES):
            ttk.Label(colors_frame, text=state.capitalize(), width=10).grid(row=index, column=0, sticky="w")
            entry = ttk.Entry(colors_frame, textvariable=color_vars[state], width=10)
            entry.grid(row=index, column=1, padx=3, pady=2)
            ttk.Button(colors_frame, text="Choose", command=lambda s=state: self._choose_color(color_vars[s])).grid(row=index, column=2, padx=3)

        buttons = ttk.Frame(frame)
        buttons.grid(row=5, column=0, columnspan=2, sticky="e", pady=(14, 0))
        ttk.Button(buttons, text="Reset position", command=self._reset_position).pack(side="left", padx=4)
        ttk.Button(buttons, text="Cancel", command=window.destroy).pack(side="left", padx=4)
        ttk.Button(buttons, text="Save", command=lambda: self._save_settings(window, size_var, opacity_var, top_var, action_var, color_vars)).pack(side="left")

    @staticmethod
    def _choose_color(variable: tk.StringVar) -> None:
        selected = colorchooser.askcolor(color=variable.get(), title="Choose status color")
        if selected and selected[1]:
            variable.set(selected[1])

    def _reset_position(self) -> None:
        self.config["x"], self.config["y"] = None, None
        self._set_geometry()

    def _save_settings(self, window: tk.Toplevel, size_var: tk.IntVar, opacity_var: tk.DoubleVar, top_var: tk.BooleanVar, action_var: tk.StringVar, color_vars: dict[str, tk.StringVar]) -> None:
        colors = {state: color_vars[state].get().strip() for state in STATES}
        if any(not COLOR_RE.fullmatch(value) for value in colors.values()):
            messagebox.showerror("Invalid color", "Colors must use #RRGGBB format.", parent=window)
            return
        self.config.update({"size": size_var.get(), "opacity": opacity_var.get(), "always_on_top": top_var.get(), "click_action": action_var.get(), "colors": colors})
        self.config = normalize_config(self.config)
        save_config(self.config)
        self._configure_transparency()
        self._set_geometry()
        self._refresh()
        window.destroy()
        self.settings_window = None

    def run(self) -> None:
        self.root.mainloop()


def main() -> int:
    try:
        DesktopIndicator().run()
    except tk.TclError as exc:
        print(f"Unable to start desktop indicator: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
