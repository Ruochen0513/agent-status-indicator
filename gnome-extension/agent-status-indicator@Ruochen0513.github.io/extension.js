// SPDX-License-Identifier: MIT
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
        this._reading = false;
        this._cancellable = new Gio.Cancellable();
        this._stateFile = Gio.File.new_for_path(GLib.build_filenamev([
            GLib.get_user_cache_dir(), 'agent-status-indicator', 'state.json',
        ]));
        this._button = new PanelMenu.Button(0.0, 'Agent Status Indicator', false);
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
        this._button.menu.addAction('Set up agent hooks…', () => {
            try {
                Gio.AppInfo.launch_default_for_uri(`${this.metadata.url}#enabling-agent-hooks`, null);
            } catch (error) {
                this._reportError(`Cannot open setup instructions: ${error.message}`);
            }
        });
        Main.panel.addToStatusArea(this.uuid, this._button, 0, 'left');
        this._render('', true);
        this._safeRefresh();
        this._timeoutId = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, 1, () => {
            this._safeRefresh();
            return GLib.SOURCE_CONTINUE;
        });
    }

    disable() {
        if (this._timeoutId) {
            GLib.source_remove(this._timeoutId);
            this._timeoutId = 0;
        }
        this._cancellable?.cancel();
        this._cancellable = null;
        this._stateFile = null;
        this._reading = false;
        this._button?.destroy();
        this._button = null;
        this._dot = null;
        this._summary = null;
        this._detail = null;
        this._lastState = null;
        this._lastError = '';
    }

    _reportError(message) {
        if (message !== this._lastError)
            console.error(`Agent Status: ${message}`);
        this._lastError = message;
    }

    _safeRefresh() {
        try {
            this._refresh();
        } catch (error) {
            this._reading = false;
            this._reportError(error.message);
        }
    }

    _refresh() {
        if (this._reading || !this._cancellable)
            return;
        this._reading = true;
        const cancellable = this._cancellable;
        this._stateFile.load_contents_async(cancellable, (file, result) => {
            let candidate = null;
            let failure = '';
            let missing = false;
            try {
                const [, bytes] = file.load_contents_finish(result);
                candidate = JSON.parse(new TextDecoder().decode(bytes));
                summarize(candidate);
            } catch (error) {
                candidate = null;
                if (cancellable.is_cancelled())
                    return;
                if (error instanceof GLib.Error && error.matches(Gio.IOErrorEnum, Gio.IOErrorEnum.NOT_FOUND))
                    missing = true;
                else
                    failure = `Cannot read status: ${error.message}`;
            }
            // A callback from a previous enable cycle must not touch new actors.
            if (this._cancellable !== cancellable || cancellable.is_cancelled())
                return;
            this._reading = false;
            if (candidate)
                this._lastState = candidate;
            else if (missing)
                this._lastState = {};
            try {
                this._render(failure, missing);
            } catch (error) {
                this._reportError(error.message);
            }
        });
    }

    _render(failure, missing) {
        const {status, agents} = summarize(this._lastState);
        const visible = failure ? 'error' : status;
        const detail = ['codex', 'claude']
            .map(name => `${name}: ${agents[name].state} (${agents[name].active_sessions})`)
            .join(' | ');
        const description = failure || (missing ? 'No status received. Set up the companion and agent hooks.' : detail);
        this._dot.set_style(`color: ${COLORS[visible]};`);
        this._button.set_accessible_name(`Agent status: ${visible}. ${description}`);
        this._summary.label.set_text(`Agent status: ${visible}`);
        this._detail.label.set_text(description);
        this._button.show();
        if (failure)
            this._reportError(failure);
        else
            this._lastError = '';
    }
}
