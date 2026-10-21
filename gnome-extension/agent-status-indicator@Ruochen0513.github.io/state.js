// SPDX-License-Identifier: MIT
// Presentation only: lifecycle events, never elapsed time, determine status.
export const PRIORITY = {idle: 0, working: 1, approval: 2, error: 3};
export const COLORS = {idle: '#8b949e', working: '#2ea043', approval: '#d29922', error: '#f85149'};

export function summarize(state) {
    if (!state || typeof state !== 'object' || Array.isArray(state))
        throw new Error('State file must contain an object');
    const agents = {};
    let status = 'idle';
    for (const name of ['codex', 'claude']) {
        let best = 'idle';
        let count = 0;
        // Session records are authoritative, including when the daemon is down.
        const items = state.sessions?.[name];
        const records = state.sessions && typeof state.sessions === 'object'
            ? Object.values(items && typeof items === 'object' ? items : {})
            : [state.agents?.[name]];
        for (const item of records) {
            const value = item?.state;
            if (typeof value !== 'string' || !Object.hasOwn(PRIORITY, value))
                continue;
            if (value !== 'idle')
                count++;
            if (PRIORITY[value] > PRIORITY[best])
                best = value;
        }
        agents[name] = {state: best, active_sessions: count};
        if (PRIORITY[best] > PRIORITY[status])
            status = best;
    }
    return {status, agents};
}
