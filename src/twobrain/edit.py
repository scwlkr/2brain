"""VS Code drafts with validation, local history and conservative recovery."""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from .errors import BrainError
from .gitrepo import clean_for_update, head, lock
from .operations import put
from .records import check_text, read_file, safe_path, select


def vscode_command():
    launcher = shutil.which("code")
    if not launcher:
        raise BrainError("VS Code's 'code' command is required. Install VS Code and enable its command on PATH.")
    launcher = Path(launcher).resolve()
    env = dict(os.environ)
    if sys.platform != "win32" or launcher.suffix.lower() not in {".cmd", ".bat"}:
        return [str(launcher)], env
    # Invoke the same native entry point as code.cmd, without a command shell.
    # Recent VS Code installs keep cli.js in a versioned directory.
    script = launcher.read_text(encoding="utf-8-sig")
    match = re.search(r'"%~dp0([^"\r\n]*[\\/]cli\.js)"', script, re.IGNORECASE)
    installation = launcher.parent.parent
    executable = installation / "Code.exe"
    entry = (launcher.parent / match[1].replace("\\", "/")).resolve() if match else None
    if not entry or not entry.is_relative_to(installation) or not entry.is_file() or not executable.is_file():
        raise BrainError(f"Cannot locate VS Code's native CLI from {launcher}. Repair VS Code's command on PATH.")
    env.update(ELECTRON_RUN_AS_NODE="1", VSCODE_DEV="")
    return [str(executable), str(entry)], env


def edit(root, kind, name, reason=None):
    with lock(root):
        clean_for_update(root)
        relative, key = select(root, kind, name)
        scope = "general" if kind == "general" else f"{kind} {key}"
        reason = f"edited {scope} guidance" if reason is None else reason
        check_text(reason, 500, "reason")
        source = safe_path(root, relative)
        original = read_file(source, kind == "general")
        revision = head(root)
        command, env = vscode_command()
        recovery = root / ".git/2brain-drafts"
        recovery.mkdir(exist_ok=True)
        directory = Path(tempfile.mkdtemp(prefix="edit-", dir=recovery))
        draft = directory / relative.name
        draft.write_bytes(source.read_bytes())

    try:
        print(f"Editing {relative.as_posix()} in VS Code. Save the file and close its tab to finish.", file=sys.stderr)
        result = subprocess.run([*command, "--wait", str(draft)], env=env,
                                capture_output=True, encoding="utf-8", errors="replace")
        if result.returncode:
            detail = (result.stderr or result.stdout).strip()
            raise BrainError(f"VS Code exited with status {result.returncode}. {detail}".strip())
        value = read_file(draft, kind == "general")
        # The editor waits outside the lock. Recheck both pending and committed
        # work before replacing anything, so stale drafts cannot overwrite it.
        with lock(root):
            clean_for_update(root)
            if head(root) != revision:
                raise BrainError("Context changed while VS Code was open. Start a fresh edit before saving this draft.")
            if value == original:
                saved = {"message": "No changes; nothing saved.", "revision": revision}
            else:
                saved = put(root, kind, key, json.dumps(value, ensure_ascii=False), reason)
    except (BrainError, OSError, UnicodeError, KeyboardInterrupt) as exc:
        code = 130 if isinstance(exc, KeyboardInterrupt) else exc.code if isinstance(exc, BrainError) else 1
        message = "Editing interrupted." if isinstance(exc, KeyboardInterrupt) else str(exc)
        raise BrainError(f"{message}\nDraft retained at {draft}. Correct it and save with 2brain put, or start a fresh edit.", code) from exc

    try:
        draft.unlink()
        directory.rmdir()
    except OSError:
        saved["warnings"] = [f"Temporary edit files remain at {directory}."]
    return saved
