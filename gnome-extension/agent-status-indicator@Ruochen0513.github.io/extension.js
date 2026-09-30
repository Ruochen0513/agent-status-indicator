import GLib from 'gi://GLib';
import St from 'gi://St';
import Clutter from 'gi://Clutter';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';

const PRIORITY = {
    idle: 0,
    working: 1,
    approval: 2,
    error: 3,
};

export default class AgentStatusExtension extends Extension {
    enable() {
        this._timeoutId = 0;
        this._button = new PanelMenu.Button(0.0, 'Agent Status Indicator', false);

        this._box = new St.BoxLayout({
            style_class: 'agent-status-box',
            y_align: Clutter.ActorAlign.CENTER,
        });

        this._dot = new St.Widget({
            style_class: 'agent-status-dot agent-status-idle',
        });
        this._box.add_child(this._dot);
        this._button.add_child(this._box);
        Main.panel.addToStatusArea('agent-status', this._button, 0, 'left');

        this._refresh();
        this._timeoutId = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, 1, () => {
            this._refresh();
            return GLib.SOURCE_CONTINUE;
        });
    }

    disable() {
        if (this._timeoutId) {
            GLib.source_remove(this._timeoutId);
            this._timeoutId = 0;
        }
        if (this._button) {
            this._button.destroy();
            this._button = null;
        }
    }

    _statePath() {
        const cacheHome = GLib.getenv('XDG_CACHE_HOME') || GLib.build_filenamev([GLib.get_home_dir(), '.cache']);
        return GLib.build_filenamev([cacheHome, 'agent-status-indicator', 'state.json']);
    }

    _readState() {
        try {
            const [, bytes] = GLib.file_get_contents(this._statePath());
            return JSON.parse(new TextDecoder().decode(bytes));
        } catch (_) {
            return {agents: {codex: {state: 'idle'}, claude: {state: 'idle'}}};
        }
    }

    _combinedState(state) {
        let result = 'idle';
        const agents = state.agents || {};
        for (const name of ['codex', 'claude']) {
            const agentState = agents[name]?.state || 'idle';
            if (Object.prototype.hasOwnProperty.call(PRIORITY, agentState) &&
                PRIORITY[agentState] > PRIORITY[result])
                result = agentState;
        }
        return result;
    }

    _refresh() {
        const state = this._readState();
        const status = this._combinedState(state);
        const agents = state.agents || {};
        const active = ['codex', 'claude']
            .map(name => `${name}:${agents[name]?.state || 'idle'}`)
            .join(' ');
        this._dot.set_style_class_name(`agent-status-dot agent-status-${status}`);
        this._button.set_accessible_name(`Agent status: ${status} ${active}`);
    }
}
