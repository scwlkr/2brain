"""Synthetic chat-completions provider behind the real adapter; never opens a socket."""
import json
import re
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src'))
from twobrain.wiki_agent import main


class Response:
    def __init__(self, request):
        self.url = request.full_url
        payload = json.loads(request.data)
        assert payload['model'] == 'synthetic-model'
        assert payload['response_format'] == {'type': 'json_object'}
        assert request.get_header('Authorization') == 'Bearer synthetic-key'
        prompt = json.loads(payload['messages'][1]['content'])
        if 'pending_sources' in prompt:
            # Preserve citations from earlier runs while incorporating changed exports.
            keys = set(prompt['pending_sources'])
            for body in prompt['pages'].values():
                keys.update(re.findall(r'../raw/([0-9a-f]{64})\.md', body))
            body = '# Daily workflow\n\nRun a morning review; retain Friday as the release target.\n\n## Sources\n'
            body += ''.join(f'- [Export](../raw/{key}.md)\n' for key in sorted(keys))
            output = {'pages': {'daily-workflow.md': body},
                      'sources': list(prompt['pending_sources']), 'summary': 'Connected synthetic planning exports.'}
        else:
            output = {'content': 'Run a morning review [Daily workflow](wiki/daily-workflow.md).',
                      'citations': ['wiki/daily-workflow.md']}
        self.raw = json.dumps({'choices': [{'finish_reason': 'stop',
                                           'message': {'content': json.dumps(output)}}]}).encode()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def geturl(self):
        return self.url

    def read(self, limit):
        return self.raw[:limit]


class Provider:
    def open(self, request, timeout):
        assert timeout == 540
        return Response(request)


with patch('twobrain.wiki_agent.build_opener', return_value=Provider()):
    raise SystemExit(main())
