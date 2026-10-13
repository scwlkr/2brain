import base64
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from support import ROOT

sys.path.insert(0, str(ROOT / 'src'))
from twobrain.errors import BrainError
from twobrain.tui_download import platform_package, verify_integrity


class Runtime(unittest.TestCase):
    def test_bootstrap_rejects_corrupt_artifacts_before_installing_them(self):
        with tempfile.TemporaryDirectory() as temporary:
            artifact = Path(temporary) / 'download.tgz'
            artifact.write_bytes(b'Authoritative artifact bytes.')
            checksum = 'sha512-' + base64.b64encode(hashlib.sha512(artifact.read_bytes()).digest()).decode()
            verify_integrity(artifact, checksum)
            artifact.write_bytes(b'Corrupt or substituted bytes.')
            with self.assertRaisesRegex(BrainError, 'checksum mismatch'):
                verify_integrity(artifact, checksum)

    def test_mac_and_windows_use_supported_pinned_platform_distributions(self):
        with patch('platform.system', return_value='Darwin'), patch('platform.machine', return_value='arm64'):
            self.assertEqual(platform_package(), 'bun-darwin-aarch64')
        with patch('platform.system', return_value='Windows'), patch('platform.machine', return_value='AMD64'):
            self.assertEqual(platform_package(), 'bun-windows-x64-baseline')

    def test_runtime_setup_works_without_context_and_is_repeatable(self):
        command = [sys.executable, str(ROOT / '2brain'), '--data', '/nonexistent-context', 'tui', '--setup', '--json']
        first = subprocess.run(command, capture_output=True, text=True, check=True, timeout=180)
        second = subprocess.run(command, capture_output=True, text=True, check=True, timeout=30)
        ready = json.loads(first.stdout)
        self.assertEqual(json.loads(second.stdout), ready)
        self.assertEqual(ready['engine'], 'OpenTUI')
        self.assertEqual(ready['version'], '0.6.2')
        self.assertTrue(ready['ready'])
        self.assertNotIn('Preparing OpenTUI', second.stderr)

    def test_standalone_archive_contains_the_complete_opentui_installation(self):
        with tempfile.TemporaryDirectory() as temporary:
            archive = Path(temporary) / '2brain.pyz'
            subprocess.run([sys.executable, str(ROOT / 'project'), 'build', '--output', str(archive)],
                           capture_output=True, text=True, check=True, timeout=15)
            result = subprocess.run([sys.executable, str(archive), 'tui', '--setup', '--json'],
                                    cwd=temporary, capture_output=True, text=True, check=True, timeout=60)
            ready = json.loads(result.stdout)
            self.assertTrue(ready['ready'])
            app = Path(ready['app'])
            self.assertTrue((app / 'main.ts').is_file())
            self.assertTrue((app / 'bun.lock').is_file())
            self.assertTrue((app / 'node_modules/@opentui/core/package.json').is_file())
