"""Offline setup and daily operation through real CLI/adapter subprocesses."""
import shlex
import sys
from support import ROOT, Scenario


class WikiSetupTests(Scenario):
    def test_configuration_check_needs_no_repository_or_stdin(self):
        missing = self.root / 'absent-context'
        env = {'TWOBRAIN_LLM_MODEL': '', 'TWOBRAIN_LLM_API_KEY': '', 'TWOBRAIN_LLM_URL': ''}
        error = self.call(missing, 'wiki', 'agent', '--check', env=env, expect=1)
        self.assertIn('TWOBRAIN_LLM_URL', error['error'])
        env.update(TWOBRAIN_LLM_URL='https://example.invalid/v1/chat/completions')
        error = self.call(missing, 'wiki', 'agent', '--check', env=env, expect=1)
        self.assertIn('TWOBRAIN_LLM_MODEL and TWOBRAIN_LLM_API_KEY', error['error'])
        env.update(TWOBRAIN_LLM_MODEL='synthetic-model', TWOBRAIN_LLM_API_KEY='synthetic-key')
        ready = self.call(missing, 'wiki', 'agent', '--check', env=env)
        self.assertTrue(ready['ready'])
        self.assertFalse(ready['network_checked'])
        self.assertFalse(missing.exists())

    def test_daily_exports_failure_retry_updates_and_cited_outputs(self):
        data = self.initialize()
        context = self.call(data)
        self.call(data, 'wiki', 'init')
        inbox = self.root / 'exports'
        inbox.mkdir()
        meeting = inbox / 'planning.md'
        meeting.write_text('# Planning\nDecision: run a morning review. Release target: Friday.\n', encoding='utf-8')
        (inbox / 'thread.json').write_text(
            '{"channel":"synthetic-planning","messages":[{"text":"Agreed: review daily; release Friday."}]}',
            encoding='utf-8')
        (inbox / 'image.png').write_bytes(b'unsupported fixture')
        builtin = shlex.join([sys.executable, str(ROOT / '2brain'), 'wiki', 'agent'])
        env = {'TWOBRAIN_LLM_MODEL': 'synthetic-model', 'TWOBRAIN_LLM_API_KEY': '',
               'TWOBRAIN_LLM_URL': 'https://example.invalid/v1/chat/completions'}
        failed = self.call(data, 'wiki', 'cycle', '--inbox', str(inbox), '--agent', builtin, env=env, expect=1)
        self.assertIn('wiki agent --check', failed['error'])
        self.assertIn('retained for retry', failed['error'])
        pending = self.call(data, 'wiki', 'compile')['pending_sources']
        self.assertEqual(len(pending), 2)
        self.assertFalse(self.call(data, 'status')['dirty'])
        fixture = shlex.join([sys.executable, str(ROOT / 'tests/fixtures/wiki_provider.py')])
        env['TWOBRAIN_LLM_API_KEY'] = 'synthetic-key'
        result = self.call(data, 'wiki', 'cycle', '--inbox', str(inbox), '--agent', fixture, env=env)
        self.assertTrue(result['lint']['ok'])
        self.assertFalse(self.call(data, 'wiki', 'compile')['pending_sources'])
        revision = self.git(data, 'rev-parse', 'HEAD')
        # A repeat with no pending exports does not need a configured model.
        self.call(data, 'wiki', 'cycle', '--inbox', str(inbox), '--agent', builtin,
                  env={**env, 'TWOBRAIN_LLM_API_KEY': ''})
        self.assertEqual(revision, self.git(data, 'rev-parse', 'HEAD'))
        meeting.write_text(meeting.read_text() + 'Review starts at 09:00 UTC.\n', encoding='utf-8')
        self.call(data, 'wiki', 'cycle', '--inbox', str(inbox), '--agent', fixture, env=env)
        self.assertEqual(len(list((data / 'raw').glob('[0-9a-f]' * 64 + '.md'))), 3)
        for key, body in pending.items():
            self.assertEqual((data / f'raw/{key}.md').read_text(), body)
        answer = self.call(data, 'wiki', 'query', 'morning review', '--agent', fixture, env=env)
        report = self.call(data, 'wiki', 'digest', '--podcast', '--agent', fixture, env=env)
        for result in (answer, report):
            self.assertEqual(result['citations'], ['wiki/daily-workflow.md'])
            self.assertIn('[Daily workflow](wiki/daily-workflow.md)', result['content'])
        self.assertEqual(self.call(data), context)
        self.assertTrue(self.call(data, 'wiki', 'lint')['ok'])
        self.assertFalse(self.call(data, 'status')['dirty'])
