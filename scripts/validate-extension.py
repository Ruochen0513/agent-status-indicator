#!/usr/bin/env python3
"""Validate the review archive without claiming approval by GNOME reviewers."""
import json
from pathlib import PurePosixPath
import re
import sys
from zipfile import ZipFile


def validate(path):
    with ZipFile(path) as archive:
        names = archive.namelist()
        expected = {'metadata.json', 'extension.js', 'state.js', 'LICENSE'}
        if len(names) != len(set(names)) or set(names) != expected:
            raise ValueError(f'Unexpected archive contents: {names}')
        for name in names:
            if PurePosixPath(name).is_absolute() or '..' in PurePosixPath(name).parts:
                raise ValueError(f'Unsafe archive member: {name}')
        metadata = json.loads(archive.read('metadata.json'))
        if metadata.get('uuid') != 'agent-status-indicator@Ruochen0513.github.io':
            raise ValueError('Submission must use the canonical UUID')
        for field in ('name', 'description', 'url'):
            if not isinstance(metadata.get(field), str) or not metadata[field].strip():
                raise ValueError(f'Missing metadata field: {field}')
        if not metadata['url'].startswith('https://github.com/Ruochen0513/agent-status-indicator'):
            raise ValueError('Unexpected project URL')
        if metadata.get('shell-version') != ['46']:
            raise ValueError('Only GNOME Shell 46 is declared for the initial submission')
        if 'version' in metadata:
            raise ValueError('EGO assigns the numeric submission version')
        if not re.fullmatch(r'(?=.*[a-zA-Z0-9])[a-zA-Z0-9 .]{1,16}', metadata.get('version-name', '')):
            raise ValueError('Invalid version-name')
        extension = archive.read('extension.js').decode()
        for pattern in ('Gio.Subprocess', 'spawn_command_line', 'load_contents(null)', 'GLib.file_get_contents'):
            if pattern in extension:
                raise ValueError(f'Unexpected subprocess or blocking read: {pattern}')
        if 'MIT License' not in archive.read('LICENSE').decode():
            raise ValueError('Missing MIT license text')
    print('Extension archive validated: GNOME 46, JavaScript and license only.')


if __name__ == '__main__':
    try:
        validate(sys.argv[1])
    except (ValueError, KeyError) as exc:
        raise SystemExit(str(exc))
