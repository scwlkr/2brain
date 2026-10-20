"""Explicit local Ollama preparation and an actual JSON inference check."""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, build_opener
from http.client import HTTPException

from .errors import BrainError
from .wiki_agent import NoRedirect, respond, settings

BASE_MODEL = 'qwen3.5:35b'
ALIAS = '2brain-wiki'
CONTEXT = 32768
MODELFILE = f'FROM {BASE_MODEL}\nPARAMETER num_ctx {CONTEXT}\n'


def setup_cache(origin):
    if sys.platform == 'darwin':
        root = Path.home() / 'Library/Caches'
    elif os.name == 'nt':
        root = Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData/Local')) / 'Cache'
    else:
        root = Path(os.environ.get('XDG_CACHE_HOME', Path.home() / '.cache'))
    return root / '2brain/local-models' / (hashlib.sha256(origin.encode()).hexdigest() + '.json')


def model_digests(origin):
    """Read full manifest identities without relying on local model storage layout."""
    try:
        endpoint = origin + '/api/tags'
        with build_opener(NoRedirect, ProxyHandler({})).open(endpoint, timeout=30) as response:
            if response.geturl() != endpoint:
                raise BrainError('Local Ollama metadata redirected; configure its final loopback URL explicitly.')
            raw = response.read(4 * 1024 * 1024 + 1)
        if len(raw) > 4 * 1024 * 1024:
            raise ValueError('Oversized model metadata')
        models = json.loads(raw)['models']
        result = {item['name']: item['digest'] for item in models}
        if any(not isinstance(value, str) or not re.fullmatch(r'[0-9a-f]{64}', value) for value in result.values()):
            raise ValueError('Invalid model manifest digest')
        return result
    except (OSError, HTTPException, ValueError, KeyError, TypeError) as exc:
        raise BrainError('Unable to inspect local Ollama model digests; check the selected loopback daemon.') from exc


def alias_record(origin, digests):
    base, alias = digests.get(BASE_MODEL), digests.get(ALIAS + ':latest')
    if not base:
        raise BrainError('The local Ollama model list is missing the Qwen3.5 base model after setup.')
    return {'endpoint': origin, 'base_digest': base, 'alias_digest': alias,
            'modelfile_sha256': hashlib.sha256(MODELFILE.encode()).hexdigest()}


def save_setup_cache(destination, record):
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=destination.parent, delete=False) as output:
        temporary = Path(output.name)
        try:
            json.dump(record, output)
            output.close()
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)


def run(setup=False):
    config = settings(local=True)
    executable = shutil.which('ollama')
    if not executable:
        raise BrainError('Ollama is not installed or not on PATH. Install the official Mac app from https://ollama.com/download, start it, then run 2brain wiki local --setup.')
    url = urlsplit(config['endpoint'])
    origin = f'{url.scheme}://{url.netloc}'
    environment = dict(os.environ, OLLAMA_HOST=origin, OLLAMA_NO_CLOUD='1')

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
        cache = setup_cache(origin)
        try:
            previous = json.loads(cache.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            previous = None
        record = alias_record(origin, model_digests(origin))
        # GGUF exposes a shared blob path; MLX emits each model's own name.
        # After a known creation, full manifest digests prove neither changed.
        shared_blob = source and target and source[1] == target[1] and source[1].startswith(('/', 'sha256:'))
        verified = record['alias_digest'] and (previous == record or (previous is None and shared_blob))
        if alias.returncode or not verified or not context or int(context[1]) != CONTEXT:
            with tempfile.TemporaryDirectory(prefix='2brain-ollama-') as directory:
                modelfile = Path(directory) / 'Modelfile'
                modelfile.write_text(MODELFILE, encoding='utf-8')
                command('create', ALIAS, '-f', str(modelfile))
            changed = True
            record = alias_record(origin, model_digests(origin))
            if not record['alias_digest']:
                raise BrainError('Ollama created the alias but did not report its manifest digest; rerun local setup.')
        save_setup_cache(cache, record)
    result = respond({'instructions': 'Return exactly the JSON object {"ok":true}. This is a local inference health check.'}, local=True)
    if set(result) != {'ok'} or result['ok'] is not True:
        raise BrainError('Local model answered, but did not return the expected JSON object {"ok":true}.')
    return {'ready': True, 'local': True, 'model': config['model'], 'endpoint': config['endpoint'],
            'alias_updated': changed, 'message': 'Local JSON inference passed. No hosted API was used.'}
