"""Command-line interface and compact agent-facing output."""

import argparse
import json
import sys
from pathlib import Path

from . import __version__, operations
from .appearance import Theme, decorate, use_color
from .branding import describe as describe_brand, export as export_brand
from .edit import edit
from .errors import BrainError
from .gitrepo import lock, remote, require_repository, status, sync
from .records import default_home, discover, read_record, select
from .setup import setup

POLICY = "Current instructions win; Wstack owns coding workflow and wins over 2brain. 2brain supplies background context. Save only requested or explicitly lasting context."


class ArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        raise BrainError(f"{message}. Use 2brain --help.", 2)


def selectors(parser, required=False):
    group = parser.add_mutually_exclusive_group(required=required)
    group.add_argument("--general", action="store_true", help="select general guidance")
    group.add_argument("--tool", metavar="NAME", help="select a tool record")
    group.add_argument("--project", metavar="OWNER/REPO", help="select an actual repository")


def parser():
    result = ArgumentParser(prog="2brain", description="Concise local personalization. Reads never contact a network.")
    result.add_argument("--version", action="version", version=f"2brain {__version__}")
    result.add_argument("--data", type=Path, default=default_home(), help="local context directory (or TWOBRAIN_HOME)")
    result.add_argument("--json", action="store_true", help="machine-readable output, including errors")
    result.add_argument("--color", choices=["auto", "always", "never"], default="auto", help="terminal color (default: auto; respects NO_COLOR)")
    result.add_argument("--theme", choices=["dark", "light"], default="dark", help="brand theme for terminal output (default: dark)")
    views = result.add_mutually_exclusive_group()
    views.add_argument("--tool", metavar="NAME")
    views.add_argument("--project", metavar="OWNER/REPO")
    views.add_argument("--list", action="store_true", help="list names without loading records")
    actions = result.add_subparsers(dest="action")
    browser = actions.add_parser("tui", help="browse and edit local context in the OpenTUI interface")
    browser.add_argument("--theme", choices=["dark", "light"], default=argparse.SUPPRESS, help="brand theme (default: dark)")
    browser.add_argument("--setup", action="store_true", help="install and verify the pinned OpenTUI runtime without opening the UI")
    brand = actions.add_parser("brand", help="inspect or export the reusable brand board and guide")
    brand.add_argument("--export", type=Path, metavar="DIRECTORY", help="save the brand kit to a new directory")
    init = actions.add_parser("init", help="initialize empty/seeded context, or clone a private remote")
    mode = init.add_mutually_exclusive_group()
    mode.add_argument("--remote")
    mode.add_argument("--seed", type=Path)
    onboarding = actions.add_parser("setup", help="prepare private context and optionally install the Codex loader")
    onboarding.add_argument("repository", nargs="?", help="GitHub owner/repo or Git URL; omit to keep existing local context")
    onboarding.add_argument("--codex", action="store_true", help="replace global Codex personalization with the loader, backing up previous instructions")
    actions.add_parser("sync", help="checkpoint local edits, fetch, merge, push")
    put = actions.add_parser("put", help="create or replace one record deliberately")
    selectors(put, True)
    put.add_argument("--file", required=True, help="UTF-8 JSON file, or - for stdin")
    put.add_argument("--reason", required=True, help="the user's request or lasting preference")
    editor = actions.add_parser("edit", help="edit one record in VS Code, validate and save locally")
    selectors(editor, True)
    editor.add_argument("--reason", help="history reason; defaults to edited <scope> guidance")
    remove = actions.add_parser("remove", help="remove one record with history")
    selectors(remove, True)
    remove.add_argument("--reason", required=True)
    save = actions.add_parser("save", help="validate and commit manual edits or resolved conflicts")
    save.add_argument("--reason", required=True)
    log = actions.add_parser("history", help="inspect revision history")
    selectors(log)
    log.add_argument("--limit", type=int, default=10)
    undo = actions.add_parser("undo", help="revert an ordinary update without rewriting history")
    undo.add_argument("revision")
    undo.add_argument("--reason", required=True)
    origin = actions.add_parser("remote", help="show/change origin without contacting the network")
    origin.add_argument("url", nargs="?")
    actions.add_parser("status", help="inspect local revision, pending edits and conflicts")
    actions.add_parser("abort", help="back up conflict edits and abort the pending sync merge")
    return result


def selected(args):
    if args.tool:
        return "tool", args.tool
    if args.project:
        return "project", args.project
    return "general", None


def query(root, args):
    if args.list:
        return {"general": "2brain", **discover(root)}
    kind, name = selected(args)
    relative, key = select(root, kind, name)
    warnings = []
    record = read_record(root, relative, warnings)
    output = {"policy": POLICY, "warnings": warnings}
    if kind == "general":
        output["general"] = record
    elif kind == "tool":
        output.update(tool=key, context=record)
    else:
        output.update(project=key, general=read_record(root, Path("general.json"), warnings), context=record)
        output["precedence"] = ["current_instructions", "wstack", "project", "general"]
    return output


def run(root, args):
    if not args.action:
        return query(root, args)
    if args.list:
        raise BrainError("Use --list by itself.")
    if args.action == "tui":
        if args.setup:
            from .tui_runtime import setup as setup_tui
            return setup_tui()
        if args.json:
            raise BrainError("The terminal browser does not emit JSON. Use 2brain --list --json or a record selector.", 2)
        from .tui import browse
        kind, name = selected(args)
        browse(root, args.theme, args.color, kind, name)
        return None
    if args.action == "brand":
        if args.tool or args.project:
            raise BrainError("Tool/project selectors do not apply to brand assets.", 2)
        return export_brand(args.export) if args.export else describe_brand()
    if args.action not in {"put", "edit", "remove", "history"} and (args.tool or args.project):
        raise BrainError("Tool/project selectors do not apply to this action.")
    if args.action == "init":
        return operations.initialize(root, args.remote, args.seed.expanduser().absolute() if args.seed else None)
    if args.action == "setup":
        return setup(root, args.repository, args.codex)
    require_repository(root)
    kind, name = selected(args)
    if args.action == "history":
        if not 1 <= args.limit <= 100:
            raise BrainError("History limit must be between 1 and 100.")
        scoped = args.general or args.tool or args.project
        return operations.history(root, args.limit, kind if scoped else None, name)
    if args.action == "status":
        return status(root)
    if args.action == "edit":
        return edit(root, kind, name, args.reason)
    with lock(root):
        if args.action == "sync":
            return sync(root)
        if args.action == "remote":
            return {"remote": remote(root, args.url)}
        if args.action == "put":
            if args.file == "-":
                raw = sys.stdin.read(32769)
            else:
                with Path(args.file).open(encoding="utf-8") as source:
                    raw = source.read(32769)
            if len(raw.encode("utf-8")) > 32768:
                raise BrainError("Input exceeds 32 KiB.")
            return operations.put(root, kind, name, raw, args.reason)
        if args.action == "remove":
            return operations.remove(root, kind, name, args.reason)
        if args.action == "save":
            return operations.save(root, args.reason)
        if args.action == "undo":
            return operations.undo(root, args.revision, args.reason)
        return operations.abort(root)


def render_record(title, record):
    lines = [title]
    lines.extend(f"- {item}" for item in record["guidance"])
    lines.extend(f"→ {pointer['label']}: {pointer['target']}" for pointer in record["pointers"])
    if not record["guidance"] and not record["pointers"]:
        lines.append("No guidance saved yet.")
    return lines


def render(value):
    if "brand" in value and "palette" in value:
        return "\n".join(["2brain brand", *[f"{name}: {color}" for name, color in value["palette"].items()],
                          value["export"], value["reference"]])
    if "policy" in value:
        lines = []
        if "general" in value:
            lines += render_record(value["general"].get("person", "General"), value["general"])
        if "context" in value:
            lines += render_record(value.get("tool", value.get("project")), value["context"])
        lines.append(value["policy"])
        return "\n".join(lines)
    if "tools" in value:
        return f"General: 2brain\nTools: {', '.join(value['tools']) or '(none)'}\nRepositories: {', '.join(value['projects']) or '(none)'}"
    if "history" in value:
        return "\n".join(f"{row['revision'][:12]} {row['date'][:10]} {row['message']}" for row in value["history"]) or "No matching history."
    return "\n".join(f"{key}: {item}" for key, item in value.items())


def main(argv=None):
    # Global format/data flags may appear before or after a subcommand.
    raw = list(sys.argv[1:] if argv is None else argv)
    globals_parser = ArgumentParser(add_help=False)
    globals_parser.add_argument("--json", action="store_true")
    globals_parser.add_argument("--data", type=Path)
    globals_parser.add_argument("--color", choices=["auto", "always", "never"], default="auto")
    globals_parser.add_argument("--theme", choices=["dark", "light"], default="dark")
    json_output = "--json" in raw
    error_color, error_theme = "auto", "dark"
    try:
        global_args, rest = globals_parser.parse_known_args(raw)
        error_color, error_theme = global_args.color, global_args.theme
        arguments = ["--color", global_args.color, "--theme", global_args.theme] + (["--json"] if global_args.json else [])
        if global_args.data:
            arguments += ["--data", str(global_args.data)]
        arguments += rest
        args = parser().parse_args(arguments)
        root = args.data.expanduser().absolute()
        result = run(root, args)
        if result is None:
            return 0
        if args.json:
            print(json.dumps(result, ensure_ascii=False))
        else:
            output = render(result)
            print(decorate(output, args.theme) if use_color(args.color, sys.stdout) else output)
            for warning in result.get("warnings", []):
                print(f"2brain: {warning}", file=sys.stderr)
        return 0
    except (BrainError, OSError, UnicodeError) as exc:
        code = exc.code if isinstance(exc, BrainError) else 1
        if json_output:
            print(json.dumps({"error": str(exc), "code": code}, ensure_ascii=False))
        else:
            message = f"2brain: {exc}"
            if use_color(error_color, sys.stderr):
                message = Theme(error_theme).paint(message, "accent")
            print(message, file=sys.stderr)
        return code


if __name__ == "__main__":
    raise SystemExit(main())
