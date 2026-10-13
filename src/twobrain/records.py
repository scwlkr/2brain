"""Record validation and selective local reads. No network or Git required."""

import json
import os
import re
import sys
import tempfile
from pathlib import Path

from .errors import BrainError

ATOM = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,99}\Z")


def default_home():
    override = os.environ.get("TWOBRAIN_HOME")
    if override:
        return Path(override).expanduser()
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) / "2brain"
    if sys.platform == "darwin":
        return Path.home() / "Library/Application Support/2brain"
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "2brain"


def check_atom(value):
    if not ATOM.fullmatch(value) or value.endswith("."):
        raise BrainError(f"Invalid name: {value!r}. Use an actual tool or repository name.")
    # These filenames cannot be represented portably on Windows.
    stem = value.split(".")[0].upper()
    if stem in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)),
                *(f"LPT{i}" for i in range(1, 10))}:
        raise BrainError(f"Name is reserved on Windows: {value!r}.")
    return value


def record_path(kind, name=None):
    if kind == "general":
        return Path("general.json")
    if kind == "tool":
        return Path("tools") / f"{check_atom(name)}.json"
    parts = name.split("/")
    if len(parts) != 2:
        raise BrainError("Use owner/repo when creating or updating a project record.")
    return Path("projects") / check_atom(parts[0]) / f"{check_atom(parts[1])}.json"


def parse(raw, general=False):
    try:
        value = json.loads(raw)
    except (ValueError, UnicodeError) as exc:
        raise BrainError(f"Invalid record JSON: {exc}") from exc
    allowed = {"schema_version", "guidance", "pointers"} | ({"person"} if general else set())
    if not isinstance(value, dict) or set(value) - allowed:
        raise BrainError("Records allow schema_version, guidance, pointers; general also allows person.")
    if type(value.get("schema_version")) is not int or value["schema_version"] != 1:
        raise BrainError("Record schema_version must be 1.")
    guidance = value.get("guidance")
    if not isinstance(guidance, list) or len(guidance) > (6 if general else 16):
        raise BrainError("guidance must be a list (at most 6 general or 16 specific entries).")
    for item in guidance:
        check_text(item, 300, "guidance", multiline=True)
    if general and sum(map(len, guidance)) > 1000:
        raise BrainError("General guidance exceeds 1,000 characters; move detail to tool/project records.")
    if "person" in value:
        check_text(value["person"], 100, "person")
    pointers = value.get("pointers", [])
    if not isinstance(pointers, list) or len(pointers) > (4 if general else 8):
        raise BrainError("pointers must be a list (at most 4 general or 8 specific entries).")
    for pointer in pointers:
        if not isinstance(pointer, dict) or set(pointer) != {"label", "target"}:
            raise BrainError("Each pointer needs exactly label and target.")
        check_text(pointer["label"], 80, "pointer label")
        check_text(pointer["target"], 300, "pointer target")
    value["pointers"] = pointers
    return value


def check_text(value, limit, label, *, multiline=False):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise BrainError(f"{label} must contain 1–{limit} characters.")
    for char in value:
        code = ord(char)
        if code == 127 or (code < 32 and not (multiline and char == "\n")):
            if multiline:
                raise BrainError(f"{label} must not contain control characters.")
            raise BrainError(f"{label} must be one line without control characters.")


def safe_path(root, relative):
    path = root / relative
    if not path.resolve().is_relative_to(root.resolve()):
        raise BrainError(f"Record escapes the data directory: {relative}")
    for parent in [path, *path.parents]:
        if parent == root.parent:
            break
        if parent.is_symlink():
            raise BrainError(f"Symlinked records are unsupported: {relative}")
    return path


def read_file(path, general=False):
    if path.stat().st_size > 32768:
        raise BrainError(f"Record exceeds 32 KiB: {path.name}")
    return parse(path.read_text(encoding="utf-8"), general)


def discover(root):
    if not root.is_dir():
        raise BrainError("No local context. Run 2brain init --remote <private-context-repo>.")
    tools = sorted(p.stem for p in (root / "tools").glob("*.json"))
    projects = sorted(f"{p.parent.name}/{p.stem}" for p in (root / "projects").glob("*/*.json"))
    return {"tools": tools, "projects": projects}


def select(root, kind, name):
    if kind == "general":
        return record_path(kind), None
    inventory = discover(root)["tools" if kind == "tool" else "projects"]
    if kind == "project":
        for part in name.split("/"):
            check_atom(part)
    else:
        check_atom(name)
    matches = [key for key in inventory if key.lower() == name.lower() or
               (kind == "project" and "/" not in name and key.split("/")[1].lower() == name.lower())]
    if len(matches) > 1:
        raise BrainError(f"Ambiguous {kind} {name!r}; use one of: {', '.join(matches)}.")
    if not matches:
        raise BrainError(f"No {kind} record for {name!r}. Use 2brain --list.")
    return record_path(kind, matches[0]), matches[0]


def read_record(root, relative, warnings):
    path = safe_path(root, relative)
    # A modify/delete conflict can contain valid JSON, so check pending operations
    # before parsing. Normal reads do not invoke Git at all.
    from .gitrepo import git, is_repository
    pending = any((root / ".git" / marker).exists() for marker in ["MERGE_HEAD", "REVERT_HEAD"])
    if pending and git(root, "ls-files", "-u", "--", relative.as_posix()).stdout:
        return committed_record(root, relative, warnings)
    try:
        return read_file(path, relative == Path("general.json"))
    except (BrainError, FileNotFoundError) as exc:
        # Also handle unmerged files created by direct Git operations.
        if is_repository(root) and git(root, "ls-files", "-u", "--", relative.as_posix()).stdout:
            return committed_record(root, relative, warnings)
        if isinstance(exc, FileNotFoundError):
            raise BrainError(f"Missing {relative.as_posix()}; initialize or restore your context.") from exc
        raise


def committed_record(root, relative, warnings):
    from .gitrepo import git
    previous = git(root, "show", f"HEAD:{relative.as_posix()}", check=False)
    if previous.returncode:
        raise BrainError(f"Conflict in {relative.as_posix()}; no committed local version. Resolve it first.")
    warnings.append(f"Conflict in {relative.as_posix()}; showing your committed local record.")
    return parse(previous.stdout, relative == Path("general.json"))


def validate_all(root):
    read_file(safe_path(root, Path("general.json")), True)
    inventory = discover(root)
    for kind, names in [("tool", inventory["tools"]), ("project", inventory["projects"])]:
        seen = set()
        for name in names:
            if name.lower() in seen:
                raise BrainError(f"Case-colliding {kind} names are not portable: {name}")
            seen.add(name.lower())
            read_file(safe_path(root, record_path(kind, name)))


def write_record(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n",
                                         dir=path.parent, delete=False) as output:
            temporary = Path(output.name)
            json.dump(value, output, indent=2, ensure_ascii=False)
            output.write("\n")
        os.replace(temporary, path)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()
