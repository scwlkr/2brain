import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from twobrain.wiki_agent import respond, NoRedirect, check_configuration
from urllib.error import HTTPError, URLError
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

    @patch.dict('os.environ', {'TWOBRAIN_LLM_MODEL': 'fixture', 'TWOBRAIN_LLM_API_KEY': 'fixture-secret'}, clear=True)
    @patch('twobrain.wiki_agent.build_opener')
    def test_offline_configuration_check_does_not_expose_values(self, opener):
        result = check_configuration()
        self.assertTrue(result['ready'])
        self.assertFalse(result['network_checked'])
        self.assertNotIn('fixture', json.dumps(result))
        opener.assert_not_called()

    @patch.dict('os.environ', {}, clear=True)
    @patch('twobrain.wiki_agent.build_opener')
    def test_missing_configuration_names_only_missing_variables(self, opener):
        with self.assertRaisesRegex(BrainError, 'TWOBRAIN_LLM_MODEL and TWOBRAIN_LLM_API_KEY'):
            check_configuration()
        with patch.dict('os.environ', {'TWOBRAIN_LLM_MODEL': 'fixture'}):
            with self.assertRaises(BrainError) as error:
                check_configuration()
            self.assertIn('TWOBRAIN_LLM_API_KEY', str(error.exception))
            self.assertNotIn('TWOBRAIN_LLM_MODEL', str(error.exception))
        opener.assert_not_called()

    @patch.dict('os.environ', {'TWOBRAIN_LLM_MODEL': 'fixture', 'TWOBRAIN_LLM_API_KEY': 'fixture-secret'}, clear=True)
    @patch('twobrain.wiki_agent.build_opener')
    def test_invalid_configuration_rejected_without_network_or_value_leaks(self, opener):
        invalid = [
            ('TWOBRAIN_LLM_URL', 'https:///no-host'),
            ('TWOBRAIN_LLM_URL', 'https://[broken'),
            ('TWOBRAIN_LLM_URL', 'https://example.invalid:bad'),
            ('TWOBRAIN_LLM_URL', 'https://example.invalid:99999'),
            ('TWOBRAIN_LLM_URL', 'https://example.invalid:0'),
            ('TWOBRAIN_LLM_URL', 'https://@example.invalid'),
            ('TWOBRAIN_LLM_URL', 'https://user:fixture-secret@example.invalid'),
            ('TWOBRAIN_LLM_URL', 'https://example.invalid?key=fixture-secret'),
            ('TWOBRAIN_LLM_URL', 'https://example.invalid/\nfixture-secret'),
            ('TWOBRAIN_LLM_MODEL', 'fixture\nsecret'),
            ('TWOBRAIN_LLM_API_KEY', 'fixture-secret\n'),
            ('TWOBRAIN_LLM_API_KEY', 'fixture-secreté'),
            ('TWOBRAIN_LLM_MODEL', '   '),
            ('TWOBRAIN_LLM_API_KEY', '   '),
        ]
        for variable, value in invalid:
            with self.subTest(variable=variable, value=value), patch.dict('os.environ', {variable: value}):
                with self.assertRaises(BrainError) as error:
                    check_configuration()
                self.assertIn(variable, str(error.exception))
                self.assertNotIn('fixture-secret', str(error.exception))
        opener.assert_not_called()

    @patch.dict('os.environ', {'TWOBRAIN_LLM_MODEL': 'fixture', 'TWOBRAIN_LLM_API_KEY': 'fixture-secret'}, clear=True)
    @patch('twobrain.wiki_agent.build_opener')
    def test_provider_errors_are_actionable_and_redacted(self, opener):
        for code, advice in [(401, 'TWOBRAIN_LLM_API_KEY'), (403, 'permissions'),
                             (404, 'TWOBRAIN_LLM_URL'), (429, 'quota'), (500, 'JSON-object')]:
            with self.subTest(code=code):
                opener.return_value.open.side_effect = HTTPError(
                    'https://example.invalid', code, 'fixture-secret', {}, None)
                with self.assertRaises(BrainError) as error:
                    respond({})
                self.assertIn(str(code), str(error.exception))
                self.assertIn(advice, str(error.exception))
                self.assertNotIn('fixture-secret', str(error.exception))
        for failure in [URLError('fixture-secret'), TimeoutError('fixture-secret'), OSError('fixture-secret')]:
            with self.subTest(failure=type(failure).__name__):
                opener.return_value.open.side_effect = failure
                with self.assertRaises(BrainError) as error:
                    respond({})
                self.assertIn('network', str(error.exception))
                self.assertNotIn('fixture-secret', str(error.exception))

    @patch.dict('os.environ', {'TWOBRAIN_LLM_MODEL': 'fixture', 'TWOBRAIN_LLM_API_KEY': 'fixture-secret'}, clear=True)
    @patch('twobrain.wiki_agent.build_opener')
    def test_malformed_provider_protocol_and_shapes_are_redacted_on_stderr(self, opener):
        import io
        from contextlib import redirect_stderr, redirect_stdout
        from http.client import BadStatusLine, IncompleteRead
        from twobrain.wiki_agent import main
        sentinel = 'SYNTHETIC_PRIVATE_PROVIDER_PAYLOAD'
        malformed = [None, [], {'choices': []}, {'choices': [None]},
                     {'choices': [sentinel]}, {'choices': [42]},
                     {'choices': [{'message': sentinel}]},
                     {'choices': [{'message': {'content': sentinel}}]}]
        for body in malformed:
            with self.subTest(body=body):
                response = self.response()
                response.read.return_value = json.dumps(body).encode()
                opener.return_value.open.side_effect = None
                opener.return_value.open.return_value = response
                output, error = io.StringIO(), io.StringIO()
                with patch('sys.stdin', io.StringIO('{}')), redirect_stdout(output), redirect_stderr(error):
                    self.assertEqual(main(), 1)
                self.assertEqual(output.getvalue(), '')
                self.assertIn('complete JSON chat-completions result', error.getvalue())
                self.assertNotIn(sentinel, error.getvalue())
                self.assertNotIn('fixture-secret', error.getvalue())
                self.assertNotIn('Traceback', error.getvalue())
        for failure in [BadStatusLine(sentinel), IncompleteRead(sentinel.encode())]:
            with self.subTest(failure=type(failure).__name__):
                opener.return_value.open.side_effect = failure
                output, error = io.StringIO(), io.StringIO()
                with patch('sys.stdin', io.StringIO('{}')), redirect_stdout(output), redirect_stderr(error):
                    self.assertEqual(main(), 1)
                self.assertEqual(output.getvalue(), '')
                self.assertIn('invalid or incomplete HTTP response', error.getvalue())
                self.assertNotIn(sentinel, error.getvalue())
                self.assertNotIn('fixture-secret', error.getvalue())
                self.assertNotIn('Traceback', error.getvalue())

    @patch.dict('os.environ', {'TWOBRAIN_LLM_MODEL': 'SYNTHETIC_MODEL', 'TWOBRAIN_LLM_API_KEY': 'SYNTHETIC_KEY'}, clear=True)
    def test_cli_preflight_never_reads_input_or_uses_network(self):
        import io
        from contextlib import redirect_stderr, redirect_stdout
        from twobrain.cli import main
        output, error = io.StringIO(), io.StringIO()
        blocked = AssertionError('Preflight attempted input, network or repository access')
        with patch('sys.stdin') as stdin, patch('socket.socket', side_effect=blocked), \
                patch('socket.getaddrinfo', side_effect=blocked), \
                patch('socket.create_connection', side_effect=blocked), \
                patch('twobrain.wiki_agent.build_opener', side_effect=blocked), \
                patch('twobrain.cli.require_repository', side_effect=blocked), \
                redirect_stdout(output), redirect_stderr(error):
            stdin.read.side_effect = blocked
            stdin.readline.side_effect = blocked
            stdin.buffer.read.side_effect = blocked
            self.assertEqual(main(['wiki', 'agent', '--check', '--json']), 0)
            stdin.read.assert_not_called()
            stdin.readline.assert_not_called()
            stdin.buffer.read.assert_not_called()
        self.assertTrue(json.loads(output.getvalue())['ready'])
        self.assertFalse(json.loads(output.getvalue())['network_checked'])
        self.assertNotIn('SYNTHETIC_', output.getvalue() + error.getvalue())
