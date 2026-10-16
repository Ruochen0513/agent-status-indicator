import GLib from 'gi://GLib';
import Gio from 'gi://Gio';
import St from 'gi://St';
import Clutter from 'gi://Clutter';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import {summarize, COLORS} from './state.js';

export default class AgentStatusExtension extends Extension {
    enable() {
        this._timeoutId = 0;
        this._lastState = {};
        this._lastError = '';
        try {
            this._button = new PanelMenu.Button(0.0, 'Agent Status Indicator', false);
            // An explicitly sized symbolic icon remains visible without CSS sizing
            // and aligns correctly when the panel/monitor scale changes.
            this._dot = new St.Icon({
                icon_name: 'media-record-symbolic',
                icon_size: 14,
                style_class: 'system-status-icon',
                y_align: Clutter.ActorAlign.CENTER,
            });
            this._button.add_child(this._dot);
            this._summary = new PopupMenu.PopupMenuItem('Agent status', {reactive: false});
            this._detail = new PopupMenu.PopupMenuItem('', {reactive: false});
            this._button.menu.addMenuItem(this._summary);
            this._button.menu.addMenuItem(this._detail);
            this._button.menu.addAction('Reset all sessions to idle', () => {
                try {
                    Gio.Subprocess.new([
                        GLib.build_filenamev([GLib.get_home_dir(), '.local', 'bin', 'agent-status']),
                        'update', 'all', 'idle',
                    ], Gio.SubprocessFlags.NONE);
                } catch (error) {
                    console.error(`Agent Status reset: ${error.message}`);
                }
            });
            Main.panel.addToStatusArea(this.uuid, this._button, 0, 'left');
            this._safeRefresh();
            this._timeoutId = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, 1, () => {
                this._safeRefresh();
                return GLib.SOURCE_CONTINUE;
            });
        } catch (error) {
            this.disable();
            throw error;
        }
    }

    disable() {
        if (this._timeoutId) {
            GLib.source_remove(this._timeoutId);
            this._timeoutId = 0;
        }
        this._button?.destroy();
        this._button = null;
        this._dot = null;
        this._summary = null;
        this._detail = null;
        this._lastState = null;
    }

    _statePath() {
        return GLib.build_filenamev([GLib.get_user_cache_dir(), 'agent-status-indicator', 'state.json']);
    }

    _safeRefresh() {
        // An exception must never remove the repeating source. Retry next tick.
        try {
            this._refresh();
        } catch (error) {
            if (this._lastError !== error.message)
                console.error(`Agent Status refresh: ${error.message}`);
            this._lastError = error.message;
        }
    }

    _refresh() {
        let failure = '';
        try {
            const file = Gio.File.new_for_path(this._statePath());
            const [, bytes] = file.load_contents(null);
            const candidate = JSON.parse(new TextDecoder().decode(bytes));
            summarize(candidate); // Validate before replacing the last good state.
            this._lastState = candidate;
        } catch (error) {
            if (error.matches?.(Gio.IOErrorEnum, Gio.IOErrorEnum.NOT_FOUND))
                this._lastState = {};
            else
                failure = `Cannot read status: ${error.message}`;
        }
        const {status, agents} = summarize(this._lastState);
        const visible = failure ? 'error' : status;
        const detail = ['codex', 'claude']
            .map(name => `${name}: ${agents[name].state} (${agents[name].active_sessions})`)
            .join(' | ');
        this._dot.set_style(`color: ${COLORS[visible]};`);
        this._button.set_accessible_name(`Agent status: ${visible}. ${failure || detail}`);
        this._summary.label.set_text(`Agent status: ${visible}`);
        this._detail.label.set_text(failure || detail);
        this._button.show();
        if (failure && failure !== this._lastError)
            console.error(`Agent Status: ${failure}`);
        this._lastError = failure;
    }
}
