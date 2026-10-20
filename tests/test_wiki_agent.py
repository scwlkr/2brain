import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from twobrain.wiki_agent import respond, NoRedirect
from twobrain.errors import BrainError


class AdapterTests(unittest.TestCase):
    def response(self, finish='stop', content='{"pages":{}}'):
        response = MagicMock()
        response.__enter__.return_value = response
        response.geturl.return_value = 'https://api.openai.com/v1/chat/completions'
        response.read.return_value = json.dumps({'choices': [{'finish_reason': finish, 'message': {'content': content}}]}).encode()
        return response

    @patch.dict('os.environ', {'TWOBRAIN_LLM_MODEL': 'fixture', 'TWOBRAIN_LLM_API_KEY': 'fixture-secret'}, clear=True)
    @patch('twobrain.wiki_agent.build_opener')
    def test_model_request_and_truncation(self, opener):
        opener.return_value.open.return_value = self.response()
        self.assertEqual(respond({'pending_sources': {}}), {'pages': {}})
        request = opener.return_value.open.call_args.args[0]
        self.assertEqual(json.loads(request.data)['response_format'], {'type': 'json_object'})
        opener.return_value.open.return_value = self.response(finish='length')
        with self.assertRaises(BrainError):
            respond({})

    @patch.dict('os.environ', {'TWOBRAIN_LLM_MODEL': 'fixture', 'TWOBRAIN_LLM_API_KEY': 'fixture-secret',
                               'TWOBRAIN_LLM_URL': 'http://example.invalid'}, clear=True)
    @patch('twobrain.wiki_agent.build_opener')
    def test_insecure_endpoint_and_redirect_rejected(self, opener):
        with self.assertRaises(BrainError):
            respond({})
        opener.assert_not_called()
        with self.assertRaises(BrainError):
            NoRedirect().redirect_request(None, None, 302, '', {}, 'https://other.invalid')
