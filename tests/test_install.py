"""Exercise installation and upgrades in an isolated user directory."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]


class InstallTests(unittest.TestCase):
    def test_upgrade_preserves_unrelated_hooks_and_existing_extension_identity(self):
        with tempfile.TemporaryDirectory(prefix='status install ') as directory:
            home = Path(directory)
            legacy_uuid = 'agent-status-indicator@yuhaozhang.github.io'
            extension = home / '.local/share/gnome-shell/extensions' / legacy_uuid
            extension.mkdir(parents=True)
            hook_file = home / '.codex/hooks.json'
            hook_file.parent.mkdir()
            hook_file.write_text(json.dumps({'unrelated': 42, 'hooks': {
                'PreToolUse': [{'matcher': '*', 'hooks': [
                    {'type': 'command', 'command': 'agent-status-hook --agent codex --event PreToolUse'},
                    {'type': 'command', 'command': 'my-existing-hook'},
                ]}],
                'SubagentStop': [{'hooks': [{'type': 'command', 'command': 'agent-status-hook --agent codex --event SubagentStop'}]}],
            }}))
            # Environment overrides are confined to the child installer process.
            env = {**os.environ, 'HOME': str(home)}
            fake_bin = home / 'fake-bin'
            fake_bin.mkdir()
            fake_codex = fake_bin / 'codex'
            fake_codex.write_text(f"#!{sys.executable}\n" + "import sys,json\nfrom pathlib import Path\np=Path(sys.argv[sys.argv.index('--out')+1])/'v2'/'HooksListResponse.json'\np.parent.mkdir(parents=True,exist_ok=True)\np.write_text(json.dumps({'definitions':{'HookEventName':{'enum':['sessionStart','userPromptSubmit','preToolUse','permissionRequest','postToolUse','stop']}}}))\n")
            fake_codex.chmod(0o755)
            env['PATH'] = str(fake_bin) + os.pathsep + os.environ['PATH']
            for key in ('CODEX_HOME', 'XDG_DATA_HOME', 'XDG_CONFIG_HOME'):
                env.pop(key, None)
            for _ in range(2):
                result = subprocess.run(['bash', str(ROOT / 'install.sh'), '--no-start', '--merge-hooks'], env=env, capture_output=True, text=True, timeout=15)
                self.assertEqual(result.returncode, 0, result.stderr)
                config = json.loads(hook_file.read_text())
                self.assertEqual(config['unrelated'], 42)
                groups = config['hooks']['PreToolUse']
                self.assertEqual(len(groups), 2)
                self.assertEqual(groups[0]['hooks'][0]['command'], 'my-existing-hook')
                self.assertEqual(groups[1]['matcher'], '.*')
                self.assertIn(str(home / '.local/bin/agent-status-hook'), groups[1]['hooks'][0]['command'])
                self.assertNotIn('SubagentStop', config['hooks'])
                self.assertNotIn('Interrupt', config['hooks'])
                self.assertNotIn('SessionEnd', config['hooks'])
                self.assertIn('omitted: SessionEnd, Interrupt', result.stdout)
                self.assertIn('reviewed and trusted', result.stdout)
            self.assertEqual(json.loads((extension / 'metadata.json').read_text())['uuid'], legacy_uuid)
            self.assertTrue((extension / 'state.js').exists())
            self.assertFalse((extension.parent / 'agent-status-indicator@Ruochen0513.github.io').exists())
            backups = list(hook_file.parent.glob('hooks.json.bak-*'))
            self.assertEqual(len(backups), 2)
            self.assertTrue(any('SubagentStop' in backup.read_text() for backup in backups))
            for module in [home / '.local/bin/agent_status_state.py', home / '.local/share/agent-status-indicator/desktop/agent_status_state.py']:
                self.assertEqual(module.read_bytes(), (ROOT / 'bin/agent_status_state.py').read_bytes())
            env['XDG_CACHE_HOME'] = str(home / 'cache')
            result = subprocess.run([str(home / '.local/bin/agent-status'), 'update', 'codex', 'working'], env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            result = subprocess.run([str(home / '.local/bin/agent-status'), 'get', 'codex'], env=env, capture_output=True, text=True)
            self.assertEqual(json.loads(result.stdout)['state'], 'working')
