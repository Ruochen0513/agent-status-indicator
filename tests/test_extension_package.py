"""Catch marketplace packaging regressions before uploading."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / 'gnome-extension/agent-status-indicator@Ruochen0513.github.io'
spec = importlib.util.spec_from_file_location('validate_extension', ROOT / 'scripts/validate-extension.py')
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


class PackageTests(unittest.TestCase):
    def make_archive(self, directory, extra=None, metadata_update=None, source=None):
        path = Path(directory) / 'extension.zip'
        metadata = json.loads((EXTENSION / 'metadata.json').read_text())
        metadata.update(metadata_update or {})
        with ZipFile(path, 'w') as archive:
            archive.writestr('metadata.json', json.dumps(metadata))
            archive.writestr('extension.js', source if source is not None else (EXTENSION / 'extension.js').read_text())
            archive.write(EXTENSION / 'state.js', 'state.js')
            archive.write(ROOT / 'LICENSE', 'LICENSE')
            if extra:
                archive.writestr(extra, 'unwanted payload')
        return path

    def test_submission_archive_is_self_contained_javascript_with_license(self):
        with tempfile.TemporaryDirectory() as directory:
            validator.validate(self.make_archive(directory))

    def test_companion_and_unnecessary_files_are_not_distributed_by_ego(self):
        with tempfile.TemporaryDirectory() as directory:
            for name in ('agent-status', 'agent-status-hook.py', 'install.sh', '../outside'):
                with self.subTest(name=name), self.assertRaises(ValueError):
                    validator.validate(self.make_archive(directory, extra=name))

    def test_legacy_uuid_unverified_versions_and_numeric_version_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            for metadata in ({'uuid': 'agent-status-indicator@yuhaozhang.github.io'}, {'shell-version': ['46', '50']}, {'version': 1}):
                with self.subTest(metadata=metadata), self.assertRaises(ValueError):
                    validator.validate(self.make_archive(directory, metadata_update=metadata))

    def test_custom_subprocess_and_blocking_reads_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            for source in ('Gio.Subprocess.new([]);', 'file.load_contents(null);'):
                with self.subTest(source=source), self.assertRaises(ValueError):
                    validator.validate(self.make_archive(directory, source=source))
