"""Repeatable OpenTUI setup, separate from context and ordinary CLI reads."""

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from importlib.resources import files
from pathlib import Path

from .errors import BrainError
from .tui_download import cache_home, install_bun


def sources():
    return files("twobrain").joinpath("opentui")


def verify_renderer(bun, app, env=None):
    code = "import {createTestRenderer} from '@opentui/core/testing'; const t=await createTestRenderer({width:40,height:12}); await t.renderOnce(); await t.dispose();"
    try:
        probe = subprocess.run([str(bun), "-e", code], cwd=app, env=env,
                               capture_output=True, text=True, timeout=30)
    except subprocess.TimeoutExpired as exc:
        raise BrainError("OpenTUI's native renderer did not respond. Retry 2brain tui --setup.") from exc
    if probe.returncode:
        raise BrainError(f"OpenTUI's native library could not load: {probe.stderr.strip()}")


def prepare(development=False):
    source = sources()
    metadata = json.loads(source.joinpath("runtime.json").read_text())
    retained = {child.name: child.read_bytes() for child in source.iterdir()
                if child.is_file() and (child.suffix in {".ts", ".json"} or child.name == "bun.lock")
                and (development or not child.name.endswith(".test.ts"))}
    digest = hashlib.sha256()
    for name, data in sorted(retained.items()):
        digest.update(name.encode() + b"\0" + data)
    cache = cache_home()
    destination = cache / (digest.hexdigest()[:16] + ("-dev" if development else ""))
    installed = destination / "node_modules/@opentui/core/package.json"
    marker = destination / ".ready"
    if not marker.is_file():
        print("Preparing OpenTUI (first launch)...", file=sys.stderr, flush=True)
    bun = install_bun(cache, metadata)
    if marker.is_file() and installed.is_file():
        return bun, destination, metadata
    cache.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="opentui-install-", dir=cache) as temporary:
        staging = Path(temporary) / "app"
        staging.mkdir()
        for name, data in retained.items():
            (staging / name).write_bytes(data)
        env = {**os.environ, "BUN_INSTALL_CACHE_DIR": str(cache / "packages")}
        command = [str(bun), "install", "--frozen-lockfile"]
        if not development:
            command.append("--production")
        try:
            result = subprocess.run(command, cwd=staging, env=env, text=True, capture_output=True, timeout=180)
        except subprocess.TimeoutExpired as exc:
            raise BrainError("OpenTUI installation timed out. Check access to registry.npmjs.org and retry 2brain tui --setup.") from exc
        if result.returncode:
            raise BrainError(f"OpenTUI installation failed: {result.stderr.strip() or result.stdout.strip()}. Retry 2brain tui --setup after correcting the reported prerequisite.")
        actual = json.loads((staging / "node_modules/@opentui/core/package.json").read_text())
        if actual["version"] != metadata["opentui"]:
            raise BrainError("Installed OpenTUI does not match the pinned version.")
        # Load the real native renderer now; presence of files alone is not readiness.
        verify_renderer(bun, staging, env)
        (staging / ".ready").write_text(metadata["opentui"] + "\n")
        if destination.exists():
            # A failed prior installation is ours; do not replace arbitrary files.
            if not (destination / ".ready").is_file():
                raise BrainError(f"Incomplete OpenTUI cache at {destination}. Remove this directory and retry setup.")
            return bun, destination, metadata
        try:
            staging.rename(destination)
        except FileExistsError:
            if not marker.is_file():
                raise
    return bun, destination, metadata


def setup():
    bun, app, metadata = prepare()
    verify_renderer(bun, app)
    return {"engine": "OpenTUI", "version": metadata["opentui"], "bun": metadata["bun"],
            "ready": True, "runtime": str(bun), "app": str(app)}
