"""Explicit writes, initialization and reversible history operations."""

import json
import os
import re
import shutil
import tempfile
from pathlib import Path

from .errors import BrainError
from .gitrepo import (check_files, check_remote, clean_for_update, commit, git,
                      head, identity, pending_merge, require_ready)
from .records import (check_text, discover, parse, record_path, safe_path,
                      select, validate_all, write_record)


def initialize(root, remote=None, seed=None):
    if root.exists():
        raise BrainError(f"Data directory already exists: {root}. No files were changed.")
    if remote:
        check_remote(remote)
    if seed:
        validate_all(seed)
    root.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".2brain-init-", dir=root.parent))
    try:
        if remote:
            git(root.parent, "clone", "--", remote, str(staging), network=True)
            validate_all(staging)
            check_files(staging)
        else:
            git(staging, "init", "-b", "main")
            if seed:
                inventory = discover(seed)
                paths = [Path("general.json")]
                paths += [record_path("tool", name) for name in inventory["tools"]]
                paths += [record_path("project", name) for name in inventory["projects"]]
                for relative in paths:
                    target = safe_path(staging, relative)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(safe_path(seed, relative), target)
            else:
                write_record(staging / "general.json", {"schema_version": 1, "guidance": [], "pointers": []})
            (staging / ".gitattributes").write_text("*.json text eol=lf\n", encoding="utf-8")
            commit(staging, "initialize supplied context" if seed else "initialize empty context")
        if root.exists():
            raise BrainError(f"Destination appeared during initialization: {root}.")
        staging.rename(root)
        return {"message": "Initialized local context.", "data": str(root), "revision": head(root)}
    except (BrainError, OSError) as exc:
        raise BrainError(f"Initialization failed: {exc}. Existing data was untouched. Partial work is preserved at {staging}.") from exc


def put(root, kind, name, source, reason):
    clean_for_update(root)
    check_text(reason, 500, "reason")
    relative = record_path(kind, name)
    # Preserve existing spelling on case-insensitive machines and avoid duplicate identities.
    if kind != "general":
        names = discover(root)["tools" if kind == "tool" else "projects"]
        matches = [key for key in names if key.lower() == name.lower()]
        if matches:
            relative = record_path(kind, matches[0])
    value = parse(source, kind == "general")
    validate_all(root)
    check_files(root)
    write_record(safe_path(root, relative), value)
    revision = commit(root, f"update {relative.as_posix()}: {reason}", relative)
    return {"message": f"Saved {relative.as_posix()} locally.", "revision": revision}


def remove(root, kind, name, reason):
    clean_for_update(root)
    check_text(reason, 500, "reason")
    if kind == "general":
        raise BrainError("Replace general guidance with an empty record to clear it; keep general.json.")
    relative, _ = select(root, kind, name)
    validate_all(root)
    check_files(root)
    safe_path(root, relative).unlink()
    return {"message": f"Removed {relative.as_posix()} locally.", "revision": commit(root, f"remove {relative.as_posix()}: {reason}")}


def save(root, reason):
    check_text(reason, 500, "reason")
    if not pending_merge(root):
        require_ready(root)
    revision = commit(root, reason)
    return {"message": "Saved deliberate edits locally.", "revision": revision}


def abort(root):
    if not pending_merge(root):
        raise BrainError("No pending merge to abort.")
    # Back up conflict-resolution work before Git restores pre-merge files.
    backup = root / ".git/2brain-recovery" / head(root)[:12]
    backup.mkdir(parents=True, exist_ok=True)
    snapshot = Path(tempfile.mkdtemp(prefix="abort-", dir=backup))
    for path in root.rglob("*.json"):
        relative = path.relative_to(root)
        if ".git" not in relative.parts and not path.is_symlink():
            target = snapshot / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
    git(root, "merge", "--abort")
    return {"message": "Merge aborted; local commits and remote edits remain in Git.",
            "recovery": str(snapshot), "revision": head(root)}


def history(root, limit, kind=None, name=None):
    arguments = ["log", f"--max-count={limit}", "--format=%H%x00%aI%x00%s"]
    if kind:
        # History is available even after a record has been removed.
        if kind == "project" and "/" not in name:
            relative, _ = select(root, kind, name)
        else:
            relative = record_path(kind, name)
        arguments += ["--", relative.as_posix()]
    output = git(root, *arguments).stdout
    return {"history": [{"revision": row[0], "date": row[1], "message": row[2]}
                        for row in (line.split("\0", 2) for line in output.splitlines())]}


def undo(root, revision, reason):
    clean_for_update(root)
    check_text(reason, 500, "reason")
    if not re.fullmatch(r"[0-9a-fA-F]{7,40}", revision):
        raise BrainError("Use a commit SHA from 2brain history.")
    resolved = git(root, "rev-parse", "--verify", f"{revision}^{{commit}}").stdout.strip()
    parents = git(root, "rev-list", "--parents", "-n", "1", resolved).stdout.split()
    if len(parents) != 2:
        raise BrainError("Undo supports ordinary updates, not initial/merge commits. Restore a chosen record with put instead.")
    if git(root, "merge-base", "--is-ancestor", resolved, "HEAD", check=False).returncode:
        raise BrainError("That revision is not in this copy's current history.")
    identity(root)
    result = git(root, "revert", "--no-commit", resolved, check=False)
    if result.returncode:
        raise BrainError("Undo conflicts with later edits; Git preserved both versions. Resolve and use git revert --continue, or git revert --abort. Reads of unresolved records use the committed local version.", 3)
    try:
        revision = commit(root, f"undo {resolved}: {reason}")
    except BrainError as exc:
        raise BrainError(f"Undo is preserved as local edits but is not committed: {exc}") from exc
    return {"message": "Undone with a new history entry.", "revision": revision}
