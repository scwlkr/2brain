"""Real loopback transport, local workflows, setup and isolation boundaries."""
import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from support import Scenario

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from twobrain.errors import BrainError
from twobrain.wiki_agent import respond, settings
from twobrain.wiki_local import run as local_run


class LocalTests(Scenario):
    def setUp(self):
        super().setUp()
        owner = self
        self.requests = []
        self.model_tags = {}
        self.mode = 'ok'

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                if self.path != '/api/tags':
                    self.send_error(404)
                    return
                raw = json.dumps({'models': [{'name': name, 'digest': digest}
                                              for name, digest in owner.model_tags.items()]}).encode()
                self.send_response(200)
                self.send_header('Content-Length', str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                owner.requests.append((body, dict(self.headers)))
                if owner.mode == 'redirect':
                    self.send_response(302)
                    self.send_header('Location', 'https://hosted.invalid/v1/chat/completions')
                    self.end_headers()
                    return
                if owner.mode == 'http-error':
                    self.send_response(503)
                    self.end_headers()
                    return
                prompt = json.loads(body['messages'][1]['content'])
                if 'pending_sources' in prompt:
                    keys = list(prompt['pending_sources'])
                    result = {'pages': {'memory.md': '# Memory\n\nUse Markdown memory.\n\n## Sources\n' +
                              '\n'.join(f'- [Source](../raw/{key}.md)' for key in keys) + '\n'},
                              'summary': 'Recorded Markdown memory.', 'sources': keys}
                    if owner.mode == 'generated-index':
                        result['pages'].update({'index.md': 'Model-owned index must be discarded',
                                                'log.md': 'Model-owned log must be discarded'})
                elif 'context' in prompt:
                    # Conflicting compilation/narrative schemas caused real local models
                    # to return pages instead of a cited answer.
                    if 'Compilation output is JSON only' in prompt['instructions']:
                        result = {'pages': {}, 'summary': 'Wrong task', 'sources': []}
                    else:
                        result = {'content': 'Use Markdown. [Memory](wiki/memory.md)', 'citations': ['wiki/memory.md']}
                else:
                    result = {'ok': True}
                response = {'choices': [{'finish_reason': 'length' if owner.mode == 'truncated' else 'stop',
                                        'message': {'content': json.dumps(result)}}]}
                raw = b'{malformed' if owner.mode == 'malformed' else json.dumps(response).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.local_env = {
            'TWOBRAIN_LOCAL_LLM_URL': f'http://127.0.0.1:{self.server.server_port}/v1/chat/completions',
            'TWOBRAIN_LOCAL_LLM_MODEL': '2brain-wiki',
            'TWOBRAIN_LLM_URL': 'https://hosted.invalid/v1/chat/completions',
            'TWOBRAIN_LLM_MODEL': 'hosted-model', 'TWOBRAIN_LLM_API_KEY': 'do-not-send-this',
            'HTTP_PROXY': 'http://127.0.0.1:1', 'HTTPS_PROXY': 'http://127.0.0.1:1',
            'ALL_PROXY': 'http://127.0.0.1:1', 'NO_PROXY': '', 'no_proxy': ''}
        self.env.update(self.local_env)

    def wiki(self):
        data = self.initialize()
        self.call(data, 'wiki', 'init')
        source = self.root / 'source.txt'
        source.write_text('Decision: use Markdown memory.')
        key = self.call(data, 'wiki', 'ingest', '--file', str(source))['source']
        return data, key

    def test_local_compile_query_digest_and_agent(self):
        data, key = self.wiki()
        self.mode = 'generated-index'
        self.call(data, 'wiki', 'compile', '--local')
        self.assertIn(key, (data / 'wiki/memory.md').read_text())
        self.assertNotIn('Model-owned', (data / 'wiki/index.md').read_text())
        self.assertNotIn('Model-owned', (data / 'wiki/log.md').read_text())
        self.assertTrue(self.call(data, 'wiki', 'lint')['ok'])
        self.assertIn('wiki/memory.md', self.call(data, 'wiki', 'query', 'memory', '--local')['citations'])
        self.assertIn('wiki/memory.md', self.call(data, 'wiki', 'query', 'What have we learned?', '--local')['citations'])
        self.assertIn('wiki/memory.md', self.call(data, 'wiki', 'digest', '--local')['citations'])
        result = self.call(self.root / 'absent', 'wiki', 'agent', '--local', stdin='{}')
        self.assertEqual(result, {'ok': True})
        for body, headers in self.requests:
            self.assertEqual(body['model'], '2brain-wiki')
            self.assertEqual(body['reasoning_effort'], 'none')
            self.assertEqual(body['temperature'], 0)
            self.assertEqual(body['response_format'], {'type': 'json_object'})
            self.assertNotIn('Authorization', headers)
            self.assertNotIn('do-not-send-this', json.dumps((body, headers)))

    def test_failure_preserves_pending_sources_and_never_falls_back(self):
        data, key = self.wiki()
        revision = self.git(data, 'rev-parse', 'HEAD')
        original = (data / f'raw/{key}.md').read_bytes()
        for mode in ('http-error', 'truncated', 'malformed', 'redirect'):
            self.mode = mode
            self.call(data, 'wiki', 'compile', '--local', expect=1)
            self.assertIn(key, self.call(data, 'wiki', 'compile')['pending_sources'])
            self.assertEqual(self.git(data, 'rev-parse', 'HEAD'), revision)
            self.assertEqual((data / f'raw/{key}.md').read_bytes(), original)
        self.assertEqual(len(self.requests), 4)
        self.assertFalse(self.call(data, 'status')['dirty'])

    def test_local_cycle_and_mutually_exclusive_flags(self):
        data = self.initialize()
        self.call(data, 'wiki', 'init')
        inbox = self.root / 'inbox'
        inbox.mkdir()
        (inbox / 'source.txt').write_text('Use Markdown memory.')
        self.assertTrue(self.call(data, 'wiki', 'cycle', '--inbox', str(inbox), '--local')['lint']['ok'])
        for action in ('compile', 'query', 'digest', 'cycle'):
            extra = ('--inbox', str(inbox)) if action == 'cycle' else ()
            self.call(data, 'wiki', action, *extra, '--local', '--agent', 'unused', expect=2)
        self.assertEqual(len(self.requests), 1)

    def test_settings_validate_loopback_and_ignore_hosted_credentials(self):
        with patch.dict(os.environ, self.local_env, clear=True):
            self.assertIsNone(settings(local=True)['key'])
            self.assertEqual(respond({}, local=True), {'ok': True})
            for endpoint in ('http://example.com/v1/chat/completions', 'http://127.0.0.1.evil.invalid/x',
                             'http://127.0.0.1:bad/x', 'http://127.0.0.1:0/x',
                             'http://user@localhost/x', 'http://localhost/x?q=1',
                             'http://localhost/x#fragment', 'http://localhost/\npath', 'http:///x'):
                os.environ['TWOBRAIN_LOCAL_LLM_URL'] = endpoint
                with self.assertRaises(BrainError):
                    settings(local=True)
            for endpoint in ('http://localhost:11434/v1/chat/completions', 'http://[::1]:11434/v1/chat/completions',
                             'http://127.2.3.4:11434/v1/chat/completions'):
                os.environ['TWOBRAIN_LOCAL_LLM_URL'] = endpoint
                self.assertEqual(settings(local=True)['endpoint'], endpoint)
            os.environ['TWOBRAIN_LOCAL_LLM_MODEL'] = 'qwen3.5:cloud'
            with self.assertRaises(BrainError):
                settings(local=True)
            os.environ['TWOBRAIN_LLM_URL'] = 'http://localhost:11434/v1/chat/completions'
            with self.assertRaises(BrainError):
                settings()
        self.assertEqual(len(self.requests), 1)

    def test_health_before_context_init_and_missing_runtime(self):
        binary = self.root / 'ollama'
        binary.write_text('#!' + sys.executable + '\nimport sys\nassert sys.argv[1:] == ["list"]\n')
        binary.chmod(0o755)
        data = self.root / 'absent'
        result = self.call(data, 'wiki', 'local', env={'PATH': str(self.root) + os.pathsep + os.environ['PATH']})
        self.assertTrue(result['ready'])
        self.assertFalse(data.exists())
        with patch('twobrain.wiki_local.shutil.which', return_value=None), patch.dict(os.environ, self.local_env):
            with self.assertRaisesRegex(BrainError, 'not installed'):
                local_run()

    def test_setup_is_idempotent_and_pins_loopback(self):
        calls = []
        installed = set()
        alias_context = 32768
        cache = self.root / 'local-setup-cache.json'

        def execute(arguments, **kwargs):
            calls.append((arguments, kwargs))
            args = arguments[1:]
            code, output = 0, ''
            if args[:2] == ['show', '--modelfile']:
                code = 0 if args[2] in installed else 1
                # MLX reports each model's own name, rather than a shared blob.
                output = 'FROM ' + args[2] + '\n' + (f'PARAMETER num_ctx {alias_context}\n' if args[2] == '2brain-wiki' else '')
            elif args[0] == 'pull':
                installed.add(args[1])
                self.model_tags['qwen3.5:35b'] = 'a' * 64
            elif args[0] == 'create':
                installed.add(args[1])
                self.model_tags['2brain-wiki:latest'] = 'b' * 64
                self.assertEqual(Path(args[3]).read_text(), 'FROM qwen3.5:35b\nPARAMETER num_ctx 32768\n')
            return subprocess.CompletedProcess(arguments, code, output, '')

        with patch.dict(os.environ, self.local_env), patch('twobrain.wiki_local.shutil.which', return_value='/bin/ollama'), \
                patch('twobrain.wiki_local.subprocess.run', side_effect=execute), \
                patch('twobrain.wiki_local.setup_cache', return_value=cache):
            self.assertTrue(local_run(setup=True)['alias_updated'])
            self.assertFalse(local_run(setup=True)['alias_updated'])
            self.assertEqual(sum(args[1] == 'create' for args, _ in calls), 1)
            self.model_tags['qwen3.5:35b'] = 'c' * 64
            self.assertTrue(local_run(setup=True)['alias_updated'])
            self.assertFalse(local_run(setup=True)['alias_updated'])
            self.model_tags['2brain-wiki:latest'] = 'd' * 64
            self.assertTrue(local_run(setup=True)['alias_updated'])
            self.assertFalse(local_run(setup=True)['alias_updated'])
            alias_context = 8192
            self.assertTrue(local_run(setup=True)['alias_updated'])
            alias_context = 32768
            cache.write_text('{corrupt')
            self.assertTrue(local_run(setup=True)['alias_updated'])
            self.assertFalse(local_run(setup=True)['alias_updated'])
        self.assertEqual(sum(args[1] == 'pull' for args, _ in calls), 1)
        self.assertEqual(sum(args[1] == 'create' for args, _ in calls), 5)
        record = json.loads(cache.read_text())
        self.assertEqual(record['base_digest'], 'c' * 64)
        self.assertEqual(record['alias_digest'], 'b' * 64)
        self.assertNotIn('do-not-send-this', cache.read_text())
        for _, kwargs in calls:
            self.assertEqual(kwargs['env']['OLLAMA_HOST'], self.local_env['TWOBRAIN_LOCAL_LLM_URL'].removesuffix('/v1/chat/completions'))
            self.assertEqual(kwargs['env']['OLLAMA_NO_CLOUD'], '1')
