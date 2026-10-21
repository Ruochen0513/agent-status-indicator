// Run with node --experimental-vm-modules tests/test_extension.mjs.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const base = new URL('../gnome-extension/agent-status-indicator@Ruochen0513.github.io/', import.meta.url);
const loggedErrors = [];
const context = vm.createContext({TextDecoder, console: {error(message) { loggedErrors.push(message); }}});
const model = new vm.SourceTextModule(fs.readFileSync(new URL('state.js', base), 'utf8'), {context});
await model.link(() => { throw Error('unexpected import'); });
await model.evaluate();
const {summarize} = model.namespace;
for (const state of ['working', 'approval', 'error']) {
    const result = summarize({ttl_seconds: 1, sessions: {codex: {s: {state, updated_at: 1}}}});
    assert.equal(result.status, state);
}
assert.throws(() => summarize(null));
assert.throws(() => summarize([]));
assert.equal(summarize({agents: {codex: {state: 'error'}}, sessions: {codex: {}}}).status, 'idle');
assert.equal(summarize({agents: {codex: {state: 'working'}}}).status, 'working');
assert.equal(summarize({sessions: {codex: {s: {state: 'working'}}, claude: {s: {state: 'approval'}}}}).status, 'approval');

let payload = '{}';
let readError = null;
let schedule = null;
let removed = 0;
const pendingReads = [];
const openedUrls = [];
class Cancellable {
    cancelled = false;
    cancel() { this.cancelled = true; }
    is_cancelled() { return this.cancelled; }
}
class GLibError extends Error {
    constructor(message, code) { super(message); this.code = code; }
    matches(_domain, code) { return this.code === code; }
}
function completeRead(index = 0) {
    const request = pendingReads.splice(index, 1)[0];
    assert(request, 'expected a pending asynchronous read');
    request.callback(request.file, {payload, error: readError, cancellable: request.cancellable});
}

const registrations = new Map();
class Button {
    constructor() {
        this.actions = [];
        this.menu = {addMenuItem() {}, addAction: (label, callback) => this.actions.push({label, callback})};
    }
    add_child(icon) { this.icon = icon; }
    set_accessible_name(value) { this.accessible = value; }
    show() { this.visible = true; }
    destroy() { this.destroyed = true; registrations.delete('test-extension'); }
}
class Icon {
    constructor(props) { Object.assign(this, props); }
    set_style(style) { this.style = style; }
}
class MenuItem {
    constructor() { this.label = {set_text: value => { this.text = value; }}; }
}
const imports = {
    'gi://GLib': {default: {
        PRIORITY_DEFAULT: 0, SOURCE_CONTINUE: true, Error: GLibError,
        get_user_cache_dir: () => '/cache', get_home_dir: () => '/home/test',
        build_filenamev: parts => parts.join('/'),
        timeout_add_seconds: (_priority, _seconds, callback) => { schedule = callback; return 7; },
        source_remove: id => { assert.equal(id, 7); removed++; },
    }},
    'gi://Gio': {default: {
        Cancellable,
        AppInfo: {launch_default_for_uri: url => openedUrls.push(url)},
        File: {new_for_path: () => ({
            load_contents_async(cancellable, callback) { pendingReads.push({file: this, cancellable, callback}); },
            load_contents_finish(result) {
                if (result.cancellable.is_cancelled()) throw new GLibError('cancelled', 2);
                if (result.error) throw result.error;
                return [true, Buffer.from(result.payload)];
            },
        })},
        IOErrorEnum: {NOT_FOUND: 1},
    }},
    'gi://St': {default: {Icon}},
    'gi://Clutter': {default: {ActorAlign: {CENTER: 1}}},
    'resource:///org/gnome/shell/ui/main.js': {panel: {addToStatusArea(id, button, position, side) {
        assert.equal(side, 'left'); assert.equal(position, 0);
        assert(!registrations.has(id)); registrations.set(id, button);
    }}},
    'resource:///org/gnome/shell/ui/panelMenu.js': {Button},
    'resource:///org/gnome/shell/ui/popupMenu.js': {PopupMenuItem: MenuItem},
    'resource:///org/gnome/shell/extensions/extension.js': {Extension: class {uuid = 'test-extension'; metadata = {url: 'https://github.com/Ruochen0513/agent-status-indicator'};}},
};
const extension = new vm.SourceTextModule(fs.readFileSync(new URL('extension.js', base), 'utf8'), {context});
await extension.link(async specifier => {
    if (specifier === './state.js') return model;
    const values = imports[specifier];
    assert(values, specifier);
    const module = new vm.SyntheticModule(Object.keys(values), function() {
        for (const [key, value] of Object.entries(values)) this.setExport(key, value);
    }, {context});
    await module.link(() => {});
    await module.evaluate();
    return module;
});
await extension.evaluate();
const instance = new extension.namespace.default();
for (let cycle = 0; cycle < 3; cycle++) {
    payload = JSON.stringify({sessions: {codex: {s: {state: 'working', updated_at: 1}}}});
    instance.enable();
    assert.equal(pendingReads.length, 1);
    const tick = schedule;
    assert.equal(tick(), true);
    assert.equal(pendingReads.length, 1, 'only one read may be in flight');
    completeRead();
    assert.equal(instance._dot.icon_size, 14);
    assert.match(instance._dot.style, /#2ea043/);
    assert(instance._button.visible);
    assert.equal(instance._button.actions.length, 1);
    assert.match(instance._button.actions[0].label, /Set up agent hooks/);
    instance._button.actions[0].callback();
    assert.match(openedUrls.at(-1), /#enabling-agent-hooks$/);
    for (const invalid of ['null', '[]', '{broken']) {
        payload = invalid;
        assert.equal(tick(), true);
        completeRead();
        assert.match(instance._dot.style, /#f85149/);
        assert.match(instance._detail.text, /Cannot read status/);
    }
    readError = Error('temporary I/O failure');
    assert.equal(tick(), true);
    completeRead();
    const loggedBefore = loggedErrors.length;
    assert.equal(tick(), true);
    completeRead();
    assert.equal(loggedErrors.length, loggedBefore, 'do not log the same error every second');
    readError = new GLibError('not found', 1);
    assert.equal(tick(), true);
    completeRead();
    assert.match(instance._dot.style, /#8b949e/);
    assert.match(instance._detail.text, /Set up the companion/);
    readError = null;
    payload = JSON.stringify({sessions: {codex: {s: {state: 'approval'}}}});
    assert.equal(tick(), true);
    completeRead();
    assert.match(instance._dot.style, /#d29922/);
    // A rendering failure must not stop future reads.
    const setStyle = instance._dot.set_style;
    instance._dot.set_style = () => { throw Error('temporary actor error'); };
    assert.equal(tick(), true);
    completeRead();
    assert.equal(instance._reading, false);
    instance._dot.set_style = setStyle;
    assert.equal(tick(), true);
    completeRead();
    // Leave a read pending across disable/enable, as when locking the screen.
    assert.equal(tick(), true);
    const oldCancellable = instance._cancellable;
    instance.disable();
    assert(oldCancellable.is_cancelled());
    assert.equal(registrations.size, 0);
    assert.equal(instance._timeoutId, 0);
    completeRead();
    assert.equal(instance._button, null);
}
assert.equal(removed, 3);
// A late callback from an old enable cycle must not alter the new cycle.
instance.enable();
instance.disable();
instance.enable();
assert.equal(pendingReads.length, 2);
completeRead(0);
assert.equal(instance._reading, true);
completeRead(0);
assert.equal(instance._reading, false);
assert.match(instance._dot.style, /#d29922/);
instance.disable();
assert.equal(pendingReads.length, 0);
console.log('GNOME model, asynchronous reads, cancellation, setup and enable/disable lifecycle passed');
