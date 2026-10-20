"""Explicit local Ollama preparation and an actual JSON inference check."""
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

from .errors import BrainError
from .wiki_agent import respond, settings

BASE_MODEL = 'qwen3.5:35b'
ALIAS = '2brain-wiki'
CONTEXT = 32768
MODELFILE = f'FROM {BASE_MODEL}\nPARAMETER num_ctx {CONTEXT}\n'


def run(setup=False):
    config = settings(local=True)
    executable = shutil.which('ollama')
    if not executable:
        raise BrainError('Ollama is not installed or not on PATH. Install the official Mac app from https://ollama.com/download, start it, then run 2brain wiki local --setup.')
    url = urlsplit(config['endpoint'])
    environment = dict(os.environ, OLLAMA_HOST=f'{url.scheme}://{url.netloc}', OLLAMA_NO_CLOUD='1')

    def command(*arguments, check=True, stream=False):
        try:
            result = subprocess.run([executable, *arguments], env=environment,
                                    text=True,
                                    stdout=sys.stderr if stream else subprocess.PIPE,
                                    stderr=sys.stderr if stream else subprocess.PIPE, timeout=3600 if stream else 60)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise BrainError('Ollama command failed or timed out; check the local runtime and retry.') from exc
        if check and result.returncode:
            raise BrainError('Ollama command failed; start the local Ollama server and check available disk space/models. No hosted fallback was attempted.')
        return result

    command('list')  # Verify the selected loopback daemon before attempting setup.
    changed = False
    if setup:
        base = command('show', '--modelfile', BASE_MODEL, check=False)
        if base.returncode:
            command('pull', BASE_MODEL, stream=True)
            base = command('show', '--modelfile', BASE_MODEL)
        alias = command('show', '--modelfile', ALIAS, check=False)
        source = re.search(r'^FROM\s+(.+)$', base.stdout, re.MULTILINE)
        target = re.search(r'^FROM\s+(.+)$', alias.stdout or '', re.MULTILINE)
        context = re.search(r'^PARAMETER\s+num_ctx\s+(\d+)\s*$', alias.stdout or '', re.MULTILINE)
        if (alias.returncode or not source or not target or source[1] != target[1]
                or not context or int(context[1]) != CONTEXT):
            with tempfile.TemporaryDirectory(prefix='2brain-ollama-') as directory:
                modelfile = Path(directory) / 'Modelfile'
                modelfile.write_text(MODELFILE, encoding='utf-8')
                command('create', ALIAS, '-f', str(modelfile))
            changed = True
    result = respond({'instructions': 'Return exactly the JSON object {"ok":true}. This is a local inference health check.'}, local=True)
    if set(result) != {'ok'} or result['ok'] is not True:
        raise BrainError('Local model answered, but did not return the expected JSON object {"ok":true}.')
    return {'ready': True, 'local': True, 'model': config['model'], 'endpoint': config['endpoint'],
            'alias_updated': changed, 'message': 'Local JSON inference passed. No hosted API was used.'}
