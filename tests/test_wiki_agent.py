import json
import sys
import unittest
from http.client import IncompleteRead
from pathlib import Path
from unittest.mock import patch, MagicMock
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from twobrain.wiki_agent import respond, settings, NoRedirect
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
        self.assertEqual(request.get_header('Authorization'), 'Bearer fixture-secret')
        self.assertNotIn('reasoning_effort', json.loads(request.data))
        opener.assert_called_with(NoRedirect)  # Nonloopback HTTPS retains normal proxy/TLS behavior.
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

    @patch.dict('os.environ', {'TWOBRAIN_LLM_MODEL': 'fixture', 'TWOBRAIN_LLM_API_KEY': 'fixture-secret'}, clear=True)
    @patch('twobrain.wiki_agent.build_opener')
    def test_response_shapes_and_transport_errors_are_sanitized(self, opener):
        for value in ([], None, {}, {'choices': []}, {'choices': [None]},
                      {'choices': [{'message': []}]}, {'choices': [{'message': {'content': []}}]}):
            response = self.response()
            response.read.return_value = json.dumps(value).encode()
            opener.return_value.open.return_value = response
            with self.assertRaisesRegex(BrainError, 'complete JSON'):
                respond({})
        opener.return_value.open.side_effect = IncompleteRead(b'secret partial response')
        with self.assertRaises(BrainError) as error:
            respond({})
        self.assertNotIn('secret', str(error.exception))

    @patch.dict('os.environ', {'TWOBRAIN_LLM_MODEL': 'fixture', 'TWOBRAIN_LLM_API_KEY': 'fixture-secret'}, clear=True)
    def test_hosted_configuration_rejects_malformed_urls_and_keys(self):
        for endpoint in ('https:///path', 'https://host:bad/path', 'https://host:0/path',
                         'https://host:65536/path', 'https://user:pass@host/path',
                         'https://host/\npath', 'https://host/path?key=secret', 'https://host/path#fragment'):
            with patch.dict('os.environ', {'TWOBRAIN_LLM_URL': endpoint}):
                with self.assertRaises(BrainError):
                    settings()
        for key in ('', '  ', 'key\nheader', 'non-ascii-\u00e9'):
            with patch.dict('os.environ', {'TWOBRAIN_LLM_API_KEY': key}):
                with self.assertRaises(BrainError):
                    settings()
