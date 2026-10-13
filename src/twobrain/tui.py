"""Launch the packaged OpenTUI application against the existing Python CLI."""

import json
import os
import signal
import subprocess
import sys
from pathlib import Path

from .appearance import use_color
from .branding import palette
from .errors import BrainError
from .records import discover, select
from .tui_runtime import prepare


def backend_command(root):
    package_root = str(Path(__file__).parent.parent)
    adapter = f"import sys; sys.path.insert(0, {package_root!r}); from twobrain.cli import main; raise SystemExit(main())"
    return [sys.executable, "-c", adapter, "--data", str(root)]


def browse(root, theme="dark", color="auto", kind="general", name=None):
    if not sys.stdin.isatty() or not sys.stdout.isatty() or os.environ.get("TERM") == "dumb":
        raise BrainError("OpenTUI needs an interactive terminal. Use 2brain --list or --json for redirected output.", 2)
    discover(root)
    initial = {"kind": kind, "name": "General"}
    if name:
        _, initial["name"] = select(root, kind, name)
    bun, app, _ = prepare()
    settings = {"theme": theme, "color": use_color(color, sys.stdout), "palette": palette(), "initial": initial}
    env = {**os.environ, "TWOBRAIN_BACKEND": json.dumps(backend_command(root)),
           "TWOBRAIN_UI_SETTINGS": json.dumps(settings)}
    process = subprocess.Popen([str(bun), str(app / "main.ts")], cwd=app, env=env)
    try:
        code = process.wait()
    except KeyboardInterrupt:
        if process.poll() is None and os.name != "nt":
            process.send_signal(signal.SIGINT)
        try:
            code = process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.terminate()
            code = process.wait(timeout=5)
    if code:
        raise BrainError(f"OpenTUI exited with status {code}. Run 2brain tui --setup to verify its runtime.")
