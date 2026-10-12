"""Git history and conservative synchronization; no force/reset/stash operations."""

import os
import subprocess
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlsplit

from .errors import BrainError
from .records import validate_all


def git(root, *args, check=True, network=False):
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0", GCM_INTERACTIVE="never")
    try:
        result = subprocess.run(["git", "-C", str(root), *args], capture_output=True,
                                encoding="utf-8", errors="replace", env=env,
                                timeout=30 if network else 15)
    except FileNotFoundError as exc:
        raise BrainError("Git is required for initialization, updates and sync; local reads still work.") from exc
    except subprocess.TimeoutExpired as exc:
        raise BrainError("Git timed out. Local files/history are preserved; retry when ready.") from exc
    if check and result.returncode:
        raise BrainError((result.stderr or result.stdout).strip() or "Git command failed.")
    return result


def is_repository(root):
    return (root / ".git").is_dir()


def require_repository(root):
    if not is_repository(root):
        raise BrainError("No context Git repository. Run 2brain init first.")


def git_path(root, name):
    value = Path(git(root, "rev-parse", "--git-path", name).stdout.strip())
    return value if value.is_absolute() else root / value


@contextmanager
def lock(root):
    require_repository(root)
    directory = root / ".git/2brain.lock"
    try:
        directory.mkdir()
    except FileExistsError as exc:
        raise BrainError(f"Another update holds {directory}. If interrupted, verify it is idle, then remove that lock directory.") from exc
    try:
        (directory / "owner").write_text(f"pid={os.getpid()}\n", encoding="utf-8")
        yield
    finally:
        (directory / "owner").unlink(missing_ok=True)
        directory.rmdir()


def conflicts(root):
    return git(root, "diff", "--name-only", "--diff-filter=U", "-z").stdout.rstrip("\0").split("\0") if git_path(root, "MERGE_HEAD").exists() else []


def pending_merge(root):
    return git_path(root, "MERGE_HEAD").exists()


def require_ready(root):
    if pending_merge(root):
        raise BrainError("A merge needs resolution. Edit conflict files, then 2brain save --reason <decision>; or 2brain abort.", 3)
    if any(git_path(root, name).exists() for name in ["rebase-merge", "rebase-apply", "CHERRY_PICK_HEAD", "REVERT_HEAD"]):
        raise BrainError("Finish the current Git operation before updating personalization.")


def dirty(root):
    return bool(git(root, "status", "--porcelain", "--untracked-files=all").stdout)


def allowed_file(name):
    parts = Path(name).parts
    return name in {"general.json", ".gitattributes", "README.md"} or (
        len(parts) == 2 and parts[0] == "tools" and parts[1].endswith(".json")) or (
        len(parts) == 3 and parts[0] == "projects" and parts[2].endswith(".json"))


def check_files(root):
    names = git(root, "ls-files", "--cached", "--others", "--exclude-standard", "-z").stdout.split("\0")
    extra = sorted({name for name in names if name and not allowed_file(name)})
    if extra:
        raise BrainError(f"Context repository contains non-record files: {', '.join(extra)}. Move them out before saving/syncing; all files are preserved.")
    for name in names:
        if name and (root / name).is_symlink():
            raise BrainError(f"Symlinked context files are unsupported: {name}")


def identity(root):
    git(root, "var", "GIT_AUTHOR_IDENT")
    git(root, "var", "GIT_COMMITTER_IDENT")


def head(root):
    return git(root, "rev-parse", "HEAD").stdout.strip()


def commit(root, reason, relative=None):
    validate_all(root)
    check_files(root)
    identity(root)
    if dirty(root) or pending_merge(root):
        if relative is None:
            git(root, "add", "-A", "--", ".")
            git(root, "commit", "-m", f"2brain: {reason}")
        else:
            # Direct editors do not share our lock. Keep a one-record update
            # scoped even if unrelated work appears just before committing.
            git(root, "add", "--", relative.as_posix())
            git(root, "commit", "--only", "-m", f"2brain: {reason}", "--", relative.as_posix())
    return head(root)


def clean_for_update(root):
    require_ready(root)
    if dirty(root):
        raise BrainError("Unsaved local edits. Run 2brain save --reason <decision> before another update.")
    identity(root)


def check_remote(value):
    if not value or value.startswith("-") or any(ord(c) < 32 for c in value):
        raise BrainError("Invalid remote URL/path.")
    parsed = urlsplit(value)
    if parsed.scheme in {"http", "https"} and (parsed.username or parsed.password or parsed.query or parsed.fragment):
        raise BrainError("Store an authentication-free remote URL; use existing Git/GitHub authentication.")
    return value


def remote(root, value=None):
    require_ready(root)
    current = git(root, "remote", "get-url", "origin", check=False)
    if value is not None:
        check_remote(value)
        git(root, "remote", "set-url" if current.returncode == 0 else "add", "origin", value)
        return value
    if current.returncode:
        raise BrainError("No origin remote. Run 2brain remote <private-context-repo>.")
    return current.stdout.strip()


def sync(root):
    require_ready(root)
    # Validate and checkpoint before any network request, including missing authentication.
    local = commit(root, "preserve deliberate local edits before sync")
    try:
        destination = remote(root)
        git(root, "fetch", "origin", network=True)
        branch_result = git(root, "symbolic-ref", "--quiet", "--short", "HEAD", check=False)
        if branch_result.returncode:
            raise BrainError("Detached HEAD; switch to your context branch before syncing.")
        branch = branch_result.stdout.strip()
        reference = f"refs/remotes/origin/{branch}"
        if git(root, "show-ref", "--verify", "--quiet", reference, check=False).returncode == 0:
            result = git(root, "merge", "--no-edit", reference, check=False)
            if result.returncode:
                paths = [p for p in conflicts(root) if p]
                if paths:
                    raise BrainError(f"Sync conflict: {', '.join(paths)}. Both versions are preserved in Git. Local reads use your committed version. Edit the files, run 2brain save --reason <resolution>, then sync; or abort.", 3)
                raise BrainError((result.stderr or result.stdout).strip())
        validate_all(root)
        check_files(root)
        git(root, "push", "origin", f"HEAD:refs/heads/{branch}", network=True)
        return {"message": "Synced.", "revision": head(root), "remote": destination}
    except BrainError as exc:
        raise BrainError(f"{exc}\nLocal changes are preserved (pre-sync revision {local}); local reads remain available.", exc.code) from exc


def status(root):
    require_repository(root)
    origin = git(root, "remote", "get-url", "origin", check=False)
    return {"data": str(root), "revision": head(root), "dirty": dirty(root),
            "merge_pending": pending_merge(root), "conflicts": [p for p in conflicts(root) if p],
            "remote": origin.stdout.strip() if origin.returncode == 0 else None}
