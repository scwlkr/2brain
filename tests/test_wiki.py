"""End-to-end wiki lifecycle, trust boundaries, and existing context compatibility."""
import json
import sys
from support import Scenario


class WikiTests(Scenario):
    def wiki(self):
        data = self.initialize()
        self.call(data, 'wiki', 'init')
        source = self.root / 'meeting.txt'
        source.write_text('Decision: use Markdown as durable memory. Evidence stays immutable.')
        captured = self.call(data, 'wiki', 'ingest', '--file', str(source), '--origin', 'fixture:meeting')
        return data, source, captured['source']

    def compilation(self, key):
        return {'pages': {'durable-memory.md': '# Durable memory\n\nStore durable memory in Markdown.\n\n## Sources\n- [Meeting](../raw/' + key + '.md)\n'},
                'summary': 'Recorded the durable memory decision.', 'sources': [key]}

    def apply(self, data, value, base=None, expect=0):
        output = self.root / 'compilation.json'
        output.write_text(json.dumps(value))
        base = base or self.git(data, 'rev-parse', 'HEAD')
        return self.call(data, 'wiki', 'compile', '--file', str(output), '--base', base, expect=expect)

    def test_lifecycle_and_idempotency(self):
        data, source, key = self.wiki()
        rev = self.git(data, 'rev-parse', 'HEAD')
        self.call(data, 'wiki', 'ingest', '--file', str(source), '--origin', 'fixture:meeting')
        self.assertEqual(rev, self.git(data, 'rev-parse', 'HEAD'))
        bundle = self.call(data, 'wiki', 'compile')
        self.assertIn(key, bundle['pending_sources'])
        self.apply(data, self.compilation(key), bundle['base_revision'])
        self.assertFalse(self.call(data, 'wiki', 'compile')['pending_sources'])
        self.assertTrue(self.call(data, 'wiki', 'lint')['ok'])
        answer = self.call(data, 'wiki', 'query', 'durable memory')
        self.assertEqual(answer['matches'][0]['path'], 'wiki/durable-memory.md')
        self.assertIn(key, answer['matches'][0]['content'])
        self.assertIn('Recorded the durable memory decision.', self.call(data, 'wiki', 'digest', '--since', '2000-01-01')['content'])
        self.assertEqual(self.call(data, 'wiki', 'digest', '--podcast')['format'], 'podcast-script')
        self.assertEqual(self.call(data)['general']['person'], 'Fixture User')
        self.assertFalse(self.call(data, 'status')['dirty'])

    def test_validation_before_mutation_and_stale_output(self):
        data, _, key = self.wiki()
        base = self.git(data, 'rev-parse', 'HEAD')
        bad = self.compilation(key)
        bad['pages']['../escape.md'] = '# escape'
        self.apply(data, bad, expect=1)
        self.assertFalse(self.call(data, 'status')['dirty'])
        bad = self.compilation(key)
        bad['pages']['durable-memory.md'] += '\n[Missing](missing.md)\n'
        self.apply(data, bad, expect=1)
        self.assertFalse(self.call(data, 'status')['dirty'])
        self.put(data, 'tool', 'fixture', {'schema_version': 1, 'guidance': [], 'pointers': []})
        self.apply(data, self.compilation(key), base=base, expect=1)
        self.assertFalse((data / 'wiki/durable-memory.md').exists())

    def test_save_rejects_raw_and_manifest_tampering(self):
        data, _, key = self.wiki()
        import hashlib
        raw = data / f'raw/{key}.md'
        raw.write_text('changed evidence')
        state_path = data / 'wiki/state.json'
        state = json.loads(state_path.read_text())
        state['sources'][key]['sha256'] = hashlib.sha256(raw.read_bytes()).hexdigest()
        state_path.write_text(json.dumps(state))
        result = self.call(data, 'save', '--reason', 'tamper', expect=1)
        self.assertIn('Immutable raw', result['error'])

    def test_symlinks_and_uncited_sources_rejected(self):
        data, _, key = self.wiki()
        bad = self.compilation(key)
        bad['pages']['durable-memory.md'] = '# Memory\n\n## Sources\nNo evidence\n'
        self.apply(data, bad, expect=1)
        (data / 'wiki/durable-memory.md').symlink_to(self.root / 'outside')
        self.apply(data, self.compilation(key), expect=1)
        self.assertFalse((self.root / 'outside').exists())

    def test_agent_cycle_and_sync_roundtrip(self):
        data = self.initialize()
        self.call(data, 'wiki', 'init')
        inbox = self.root / 'inbox'
        inbox.mkdir()
        (inbox / 'source.md').write_text('Durable memory in Markdown.')
        agent = self.root / 'agent.py'
        agent.write_text('import json,sys\nb=json.load(sys.stdin)\nk=next(iter(b["pending_sources"]))\n' +
                         'print(json.dumps({"pages":{"memory.md":"# Memory\\n\\nDurable memory.\\n\\n## Sources\\n- [Source](../raw/"+k+".md)\\n"},"summary":"Added memory.","sources":[k]}))\n')
        import shlex
        command = shlex.join([sys.executable, str(agent)])
        first = self.call(data, 'wiki', 'cycle', '--inbox', str(inbox), '--agent', command)
        self.assertTrue(first['lint']['ok'])
        rev = self.git(data, 'rev-parse', 'HEAD')
        self.call(data, 'wiki', 'cycle', '--inbox', str(inbox), '--agent', command)
        self.assertEqual(rev, self.git(data, 'rev-parse', 'HEAD'))
        remote = self.root / 'remote.git'
        self.git(self.root, 'init', '--bare', '-b', 'main', str(remote))
        self.call(data, 'remote', str(remote))
        self.call(data, 'sync')
        clone = self.root / 'clone'
        self.call(clone, 'init', '--remote', str(remote))
        self.assertTrue(self.call(clone, 'wiki', 'lint')['ok'])
        self.assertIn('Durable memory', self.call(clone, 'wiki', 'query', '--page', 'memory.md')['content'])

    def test_cited_narrative_audio_and_missing_evidence(self):
        import shlex
        data, _, key = self.wiki()
        self.apply(data, self.compilation(key))
        script = self.root / 'narrative.py'
        script.write_text('import sys,json\njson.load(sys.stdin)\nprint(json.dumps({"content":"A decision [Memory](wiki/durable-memory.md)","citations":["wiki/durable-memory.md"]}))\n')
        command = shlex.join([sys.executable, str(script)])
        answer = self.call(data, 'wiki', 'query', 'memory', '--agent', command)
        self.assertIn('wiki/durable-memory.md', answer['citations'])
        # Citation to a real page is still invalid if that page was not supplied to the agent.
        self.call(data, 'wiki', 'query', 'unfindableterm', '--agent', command, expect=1)
        tts = self.root / 'tts.py'
        tts.write_text('import sys\ns=sys.stdin.read()\nassert "A decision" in s\nsys.stdout.buffer.write(b"RIFF-fixture")\n')
        output = self.root / 'daily.wav'
        result = self.call(data, 'wiki', 'digest', '--podcast', '--agent', command,
                           '--tts', shlex.join([sys.executable, str(tts)]), '--audio', str(output))
        self.assertEqual(output.read_bytes(), b'RIFF-fixture')
        self.assertEqual(result['audio'], str(output))
        self.call(data, 'wiki', 'digest', '--tts', command, '--audio', str(output), expect=1)
        self.assertFalse(self.call(data, 'status')['dirty'])

    def test_validation_errors_do_not_echo_generated_payloads(self):
        data, _, key = self.wiki()
        revision = self.git(data, 'rev-parse', 'HEAD')
        raw = (data / f'raw/{key}.md').read_bytes()
        sentinel = 'SYNTHETIC_PRIVATE_PROVIDER_PAYLOAD'
        bad = self.compilation(key)
        bad['pages'] = {sentinel: bad['pages']['durable-memory.md']}
        error = self.apply(data, bad, expect=1)
        self.assertIn('Invalid compilation page', error['error'])
        self.assertNotIn(sentinel, error['error'])
        for target, message in [(sentinel, 'broken or unsupported local link'),
                                ('../raw/' + 'a' * 64 + '.md', 'unknown source')]:
            bad = self.compilation(key)
            bad['pages']['durable-memory.md'] += '\n[Bad link](' + target + ')\n'
            error = self.apply(data, bad, expect=1)
            self.assertIn(message, error['error'])
            self.assertNotIn(target, error['error'])
        self.assertEqual(revision, self.git(data, 'rev-parse', 'HEAD'))
        self.assertEqual(raw, (data / f'raw/{key}.md').read_bytes())
        self.assertEqual(set(self.call(data, 'wiki', 'compile')['pending_sources']), {key})
        self.assertFalse(self.call(data, 'status')['dirty'])
