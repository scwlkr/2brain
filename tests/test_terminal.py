import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

from support import ROOT, Scenario, record


class Presentation(Scenario):
    def test_redirected_output_stays_plain_and_color_is_explicit(self):
        data = self.initialize()
        plain = self.call(data, raw=True).stdout
        self.assertNotIn('\x1b', plain)
        self.assertTrue(plain.startswith('Shane Walker\n'))
        colored = self.call(data, '--color', 'always', raw=True).stdout
        self.assertIn('\x1b[38;2;148;180;156m', colored)
        self.assertIn('2brain / Shane Walker', colored)
        self.assertIn('Be concise.', colored)
        never = self.call(data, '--color', 'never', raw=True).stdout
        self.assertEqual(never, plain)
        light = self.call(data, '--color', 'always', '--theme', 'light', raw=True).stdout
        self.assertIn('\x1b[38;2;66;99;79m', light)
        value = self.call(data, '--color', 'always')
        self.assertEqual(value, self.call(data))

    def test_color_flag_after_action_and_json_errors(self):
        data = self.initialize()
        colored = self.call(data, 'status', '--color', 'always', raw=True).stdout
        self.assertIn('\x1b', colored)
        self.assertIn(str(data), colored)
        error = self.call(data, '--color', 'invalid', expect=2)
        self.assertEqual(error['code'], 2)
        self.assertIn('invalid choice', error['error'])

    def test_browser_rejects_json_and_nonterminal_without_escape_sequences(self):
        data = self.initialize()
        error = self.call(data, 'tui', expect=2)
        self.assertIn('does not emit JSON', error['error'])
        result = self.call(data, 'tui', raw=True, expect=2)
        self.assertIn('interactive terminal', result.stderr)
        self.assertNotIn('\x1b', result.stdout + result.stderr)

    def test_brand_export_works_without_context_and_preserves_existing_files(self):
        absent = self.root / 'no-context'
        brand = self.call(absent, 'brand')
        self.assertEqual(brand['palette']['sage'], '#94B49C')
        destination = self.root / 'brand kit'
        result = self.call(absent, 'brand', '--export', str(destination))
        self.assertEqual(result['directory'], str(destination))
        for relative in ('index.html', 'style.json', 'symbols/mark-ink.svg',
                         'references/brand-board.svg', '.wstack-brand/integration.js'):
            self.assertTrue((destination / relative).is_file(), relative)
        self.assertEqual(json.loads((destination / 'style.json').read_text()), brand['style'])
        marker = destination / 'owner.txt'
        marker.write_text('Preserve this.')
        self.call(absent, 'brand', '--export', str(destination), expect=1)
        self.assertEqual(marker.read_text(), 'Preserve this.')

    def test_standalone_archive_retains_exportable_brand_assets(self):
        archive = self.root / '2brain.pyz'
        subprocess.run([sys.executable, str(ROOT / 'project'), 'build', '--output', str(archive)],
                       capture_output=True, text=True, check=True, env=self.env)
        destination = self.root / 'archive-brand'
        result = subprocess.run([sys.executable, str(archive), 'brand', '--export', str(destination), '--json'],
                                cwd=self.root, env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue((destination / 'references/brand-board.svg').is_file())
        self.assertIn('Identity & terminal guide', (destination / 'index.html').read_text())


@unittest.skipIf(os.name == 'nt', 'PTY exercises require a POSIX host; Windows needs native qualification')
class TerminalBrowser(Scenario):
    def launch(self, data, width=100, height=24, color='always', theme='dark', initial=()):
        import fcntl
        import pty
        import struct
        import termios
        master, slave = pty.openpty()
        self.master, self.slave = master, slave
        self.addCleanup(os.close, master)
        self.addCleanup(os.close, slave)
        self.before = termios.tcgetattr(slave)
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH', height, width, 0, 0))
        env = {**self.env, 'TERM': 'xterm-256color'}
        def own_terminal():
            os.setsid()
            fcntl.ioctl(0, termios.TIOCSCTTY, 0)
        self.process = subprocess.Popen([sys.executable, str(ROOT / '2brain'), '--data', str(data),
                                         '--color', color, *initial, 'tui', '--theme', theme],
                                        stdin=slave, stdout=slave, stderr=slave, env=env, preexec_fn=own_terminal)
        self.addCleanup(self.stop)
        self.output = b''
        self.until('q quit')

    def stop(self):
        import signal
        if self.process.poll() is None:
            os.killpg(self.process.pid, signal.SIGTERM)
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                os.killpg(self.process.pid, signal.SIGKILL)
                self.process.wait(timeout=3)

    def until(self, text):
        import select
        import time
        deadline = time.monotonic() + 5
        fragment = b''
        expected = text.encode('utf-8')
        while time.monotonic() < deadline:
            if select.select([self.master], [], [], 0.05)[0]:
                chunk = os.read(self.master, 65536)
                fragment += chunk
                self.output += chunk
                if expected in fragment:
                    return fragment.decode('utf-8', errors='replace')
            if self.process.poll() is not None:
                break
        self.fail(f'Terminal did not show {text!r}: {fragment.decode("utf-8", errors="replace")}')

    def send(self, keys, expected):
        os.write(self.master, keys.encode('utf-8'))
        return self.until(expected)

    def finish(self, key='q'):
        import termios
        self.send(key, '\x1b[?1049l')
        self.process.wait(timeout=5)
        self.assertEqual(self.process.returncode, 0)
        with self.assertRaises(ProcessLookupError):
            os.killpg(self.process.pid, 0)
        self.assertEqual(termios.tcgetattr(self.slave), self.before)
        self.assertIn(b'\x1b[?25h', self.output)

    def test_open_tui_launches_the_selected_record_and_preserves_context(self):
        data = self.initialize()
        self.put(data, 'tool', 'git', record('Installed OpenTUI terminal proof.'))
        before = self.git(data, 'rev-parse', 'HEAD')
        self.launch(data, initial=('--tool', 'git'))
        self.assertIn(b'Installed OpenTUI terminal proof.', self.output)
        self.finish()
        self.assertEqual(self.git(data, 'rev-parse', 'HEAD'), before)
        self.assertFalse(self.call(data, 'status')['dirty'])

    def test_open_tui_ctrl_c_restores_terminal_modes_and_cursor(self):
        data = self.initialize()
        self.env['NO_COLOR'] = '1'
        self.launch(data, color='auto')
        self.finish('\x03')

    def test_project_shorthand_opens_the_matching_record(self):
        data = self.initialize()
        self.put(data, 'project', 'owner/repo', record('Project-specific terminal proof.'))
        self.launch(data, initial=('--project', 'REPO'))
        self.assertIn(b'Project-specific terminal proof.', self.output)
        self.finish()

    def test_invalid_option_reports_a_colored_terminal_error_without_traceback(self):
        import pty
        master, slave = pty.openpty()
        try:
            env = {**self.env, 'TERM': 'xterm-256color'}
            env.pop('NO_COLOR', None)
            result = subprocess.run([sys.executable, str(ROOT / '2brain'), '--color', 'invalid'],
                                    stdin=subprocess.DEVNULL, stdout=slave, stderr=slave, env=env, timeout=10)
            output = os.read(master, 65536)
            self.assertEqual(result.returncode, 2)
            self.assertIn(b'invalid choice', output)
            self.assertIn(b'\x1b[38;', output)
            self.assertNotIn(b'Traceback', output)
        finally:
            os.close(master)
            os.close(slave)
