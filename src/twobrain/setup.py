"""Explicit first-run setup. Package installation never edits agent instructions."""

import os
import re
import tempfile
from pathlib import Path

from .errors import BrainError
from .gitrepo import git, lock, remote, require_ready, require_repository
from .operations import initialize
from .records import check_atom, validate_all

CODEX_LOADER = "Coding start → run `2brain`.\n"


def expand_remote(value):
    if value and re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", value):
        owner, repository = value.split("/")
        check_atom(owner)
        check_atom(repository)
        return f"https://github.com/{owner}/{repository}.git"
    return value


def configure_codex():
    home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).expanduser().absolute()
    instructions = home / "AGENTS.md"
    override = home / "AGENTS.override.md"
    for path in (instructions, override):
        if path.is_symlink() or (path.exists() and not path.is_file()):
            raise BrainError(f"Codex setup cannot replace a symlink or non-file: {path}. Configure the loader at its owning source.")
    existing = {path: path.read_bytes() for path in (instructions, override) if path.exists()}
    replacement = CODEX_LOADER.encode("utf-8")
    if existing.get(instructions) == replacement and override not in existing:
        return {"codex_instructions": str(instructions), "instructions_changed": False}
    home.mkdir(parents=True, exist_ok=True)
    backups = home / "2brain-backups"
    if backups.is_symlink():
        raise BrainError(f"Codex backup directory is a symlink: {backups}. No instructions were changed.")
    backups.mkdir(exist_ok=True)
    backup = Path(tempfile.mkdtemp(prefix="instructions-", dir=backups)) if existing else None
    for path, contents in existing.items():
        saved = backup / path.name
        saved.write_bytes(contents)
        saved.chmod(0o600)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=home, prefix=".2brain-loader-", delete=False) as output:
            temporary = Path(output.name)
            output.write(replacement)
        # Preserve competing editor changes rather than overwriting them.
        for path in (instructions, override):
            current = path.read_bytes() if path.exists() else None
            if current != existing.get(path):
                raise BrainError(f"Codex instructions changed during setup: {path}. Retry after the edit finishes.")
        os.replace(temporary, instructions)
        if override in existing:
            override.unlink()  # Exact previous bytes are retained in the inactive backup.
    except OSError as exc:
        raise BrainError(f"Codex setup could not finish: {exc}. Previous instructions are preserved at {backup or 'their original location'}.") from exc
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)
    result = {"codex_instructions": str(instructions), "instructions_changed": True}
    if backup:
        result["instructions_backup"] = str(backup)
    return result


def setup(root, destination=None, codex=False):
    destination = expand_remote(destination)
    if not root.exists():
        if not destination:
            raise BrainError("Choose a private context repository: 2brain setup owner/repo --codex.")
        initialize(root, remote=destination)
    with lock(root):
        require_repository(root)
        require_ready(root)
        validate_all(root)
        if destination:
            configured = git(root, "remote", "get-url", "origin", check=False)
            if configured.returncode == 0 and configured.stdout.strip() != destination:
                raise BrainError("Existing context uses a different remote. No data/instructions were changed. Omit the repository to keep it, or use 2brain remote <URL> deliberately.")
            if configured.returncode:
                remote(root, destination)
        result = {"message": "Local context is ready.", "data": str(root)}
        if codex:
            result.update(configure_codex())
            result["message"] = "Context and Codex loader are ready. Restart Codex to load the instructions."
        return result
