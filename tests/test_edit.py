import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

from support import ROOT, Scenario, record


class Editing(Scenario):
    def setUp(self):
        super().setUp()
        # A real child process stands in for VS Code, including its Windows layout.
        installation = self.root / "VS Code installation"
        binaries = installation / "bin"
        binaries.mkdir(parents=True)
        script = installation / "resources/app/out/cli.js"
        script.parent.mkdir(parents=True)
        script.write_text('''import json, os, subprocess, sys
from pathlib import Path
assert sys.argv[1] == "--wait", sys.argv
draft = Path(sys.argv[2])
Path(os.environ["EDITOR_LOG"]).write_text(str(draft), encoding="utf-8")
action = os.environ.get("EDITOR_ACTION", "change")
if action == "fail":
    sys.exit(9)
if action == "unchanged":
    sys.exit(0)
if action == "invalid":
    draft.write_text("{broken", encoding="utf-8")
elif action == "invalid-schema":
    draft.write_text(json.dumps({"schema_version": 99}), encoding="utf-8")
else:
    value = json.loads(draft.read_text(encoding="utf-8"))
    if action != "reformat":
        value["guidance"] = ["Edited and confirmed preference."]
    draft.write_text(json.dumps(value), encoding="utf-8")
if action in {"concurrent", "committed"}:
    data = Path(os.environ["EDITOR_DATA"])
    (data / "README.md").write_text("Concurrent owner work", encoding="utf-8")
    if action == "committed":
        subprocess.run(["git", "-C", str(data), "add", "README.md"], check=True)
        subprocess.run(["git", "-C", str(data), "commit", "-m", "Concurrent update"],
                       check=True, stdout=subprocess.DEVNULL)
''', encoding="utf-8")
        if sys.platform == "win32":
            (binaries / "code.cmd").write_text('@echo off\n"%~dp0..\\Code.exe" "%~dp0..\\resources\\app\\out\\cli.js" %*\nexit /b 99\n', encoding="utf-8")
            shutil.copyfile(sys.executable, installation / "Code.exe")
            for library in Path(sys.base_prefix).glob("python*.dll"):
                shutil.copyfile(library, installation / library.name)
            self.env["PYTHONHOME"] = sys.base_prefix
        else:
            launcher = binaries / "code"
            launcher.write_text(f'#!/bin/sh\nexec {shlex.quote(sys.executable)} {shlex.quote(str(script))} "$@"\n',
                                encoding="utf-8")
            launcher.chmod(0o755)
        self.log = self.root / "editor.log"
        self.env.update(PATH=str(binaries) + os.pathsep + self.env["PATH"], EDITOR_LOG=str(self.log))

    def edit(self, data, *selector, action="change", expect=0, reason=None):
        arguments = ["edit", *selector]
        if reason is not None:
            arguments += ["--reason", reason]
        return self.call(data, *arguments, expect=expect,
                         env={"EDITOR_ACTION": action, "EDITOR_DATA": str(data)})

    def draft(self):
        return Path(self.log.read_text(encoding="utf-8"))

    def test_general_default_reason_preserves_metadata_and_saves_locally(self):
        data = self.initialize()
        original = self.call(data)["general"]
        original["pointers"] = [{"label": "Tool", "target": "2brain --tool git"}]
        self.put(data, "general", None, original)
        before = self.git(data, "rev-parse", "HEAD")
        result = self.edit(data, "--general")
        current = self.call(data)["general"]
        self.assertEqual(current["guidance"], ["Edited and confirmed preference."])
        self.assertEqual(current["person"], original["person"])
        self.assertEqual(current["pointers"], original["pointers"])
        self.assertNotEqual(result["revision"], before)
        self.assertIn("edited general guidance", self.git(data, "log", "-1", "--format=%s"))
        self.assertEqual(self.git(data, "show", "--format=", "--name-only", "HEAD"), "general.json")
        self.assertFalse(self.call(data, "status")["dirty"])
        self.assertFalse(self.draft().exists())

    def test_tool_project_selectors_and_reason_override(self):
        data = self.initialize()
        self.put(data, "tool", "git", record("Original tool preference."))
        self.put(data, "project", "owner/repo", record("Original project preference."))
        general = (data / "general.json").read_bytes()
        for selector, relative in [("--tool", "tools/git.json"), ("--project", "projects/owner/repo.json")]:
            name = "GIT" if selector == "--tool" else "REPO"
            self.edit(data, selector, name, reason="My explicit reason")
            self.assertTrue(self.git(data, "log", "-1", "--format=%s").endswith(": My explicit reason"))
            self.assertEqual(self.git(data, "show", "--format=", "--name-only", "HEAD"), relative)
            self.assertEqual(json.loads((data / relative).read_text())["guidance"],
                             ["Edited and confirmed preference."])
        self.assertEqual((data / "general.json").read_bytes(), general)

    def test_unchanged_and_reformatted_drafts_do_not_commit(self):
        data = self.initialize()
        before = (data / "general.json").read_bytes()
        revision = self.git(data, "rev-parse", "HEAD")
        for action in ("unchanged", "reformat"):
            self.edit(data, "--general", action=action)
            self.assertEqual((data / "general.json").read_bytes(), before)
            self.assertEqual(self.git(data, "rev-parse", "HEAD"), revision)
            self.assertFalse(self.draft().exists())

    def test_existing_unsaved_edits_are_preserved_before_launch(self):
        for mode in ("unstaged", "staged", "untracked"):
            with self.subTest(mode=mode):
                data = self.root / mode
                self.call(data, "init")
                relative = "general.json" if mode != "untracked" else "owner.txt"
                pending = json.dumps(record("Unfinished owner preference."))
                (data / relative).write_text(pending, encoding="utf-8")
                if mode == "staged":
                    self.git(data, "add", relative)
                before = self.git(data, "status", "--porcelain")
                revision = self.git(data, "rev-parse", "HEAD")
                error = self.edit(data, "--general", expect=1)
                self.assertIn("Unsaved local edits", error["error"])
                self.assertEqual((data / relative).read_text(), pending)
                self.assertEqual(self.git(data, "status", "--porcelain"), before)
                self.assertEqual(self.git(data, "rev-parse", "HEAD"), revision)
                self.assertFalse(self.log.exists())

    def test_edits_made_while_editor_is_open_are_not_overwritten_or_committed(self):
        data = self.initialize()
        original = (data / "general.json").read_bytes()
        revision = self.git(data, "rev-parse", "HEAD")
        error = self.edit(data, "--general", action="concurrent", expect=1)
        self.assertIn("Unsaved local edits", error["error"])
        self.assertEqual((data / "README.md").read_text(), "Concurrent owner work")
        self.assertEqual((data / "general.json").read_bytes(), original)
        self.assertEqual(self.git(data, "rev-parse", "HEAD"), revision)
        self.assertIn(str(self.draft()), error["error"])
        self.assertEqual(json.loads(self.draft().read_text())["guidance"], ["Edited and confirmed preference."])

    def test_committed_changes_while_editor_is_open_require_a_fresh_draft(self):
        data = self.initialize()
        original = (data / "general.json").read_bytes()
        revision = self.git(data, "rev-parse", "HEAD")
        error = self.edit(data, "--general", action="committed", expect=1)
        self.assertIn("changed while VS Code was open", error["error"])
        self.assertNotEqual(self.git(data, "rev-parse", "HEAD"), revision)
        self.assertEqual((data / "general.json").read_bytes(), original)
        self.assertTrue(self.draft().exists())
        self.assertFalse(self.call(data, "status")["dirty"])

    def test_invalid_drafts_and_editor_failure_leave_original_and_recovery(self):
        data = self.initialize()
        original = (data / "general.json").read_bytes()
        revision = self.git(data, "rev-parse", "HEAD")
        for action in ("invalid", "invalid-schema", "fail"):
            with self.subTest(action=action):
                error = self.edit(data, "--general", action=action, expect=1)
                self.assertEqual((data / "general.json").read_bytes(), original)
                self.assertEqual(self.git(data, "rev-parse", "HEAD"), revision)
                self.assertTrue(self.draft().exists())
                self.assertIn(str(self.draft()), error["error"])
                self.assertFalse(self.call(data, "status")["dirty"])

    def test_missing_editor_selector_and_invalid_reason_cannot_write(self):
        data = self.initialize()
        revision = self.git(data, "rev-parse", "HEAD")
        self.call(data, "edit", expect=2)
        self.edit(data, "--general", reason="", expect=1)
        self.edit(data, "--tool", "missing", expect=1)
        self.assertFalse(self.log.exists())
        # Keep Git available while hiding both the fake and real VS Code launchers.
        git_path = Path(shutil.which("git"))
        error = self.call(data, "edit", "--general", expect=1,
                          env={"PATH": str(git_path.parent)})
        self.assertIn("VS Code", error["error"])
        self.assertEqual(self.git(data, "rev-parse", "HEAD"), revision)
        self.assertFalse(self.log.exists())

    def test_single_record_commit_preserves_unrelated_staged_and_unstaged_work(self):
        data = self.initialize()
        (data / "general.json").write_text(json.dumps(record("Confirmed edit.")), encoding="utf-8")
        (data / "README.md").write_text("Staged owner work", encoding="utf-8")
        self.git(data, "add", "README.md")
        (data / "README.md").write_text("Unstaged owner work", encoding="utf-8")
        # Exercise the final Git boundary, where an external editor can race
        # with the earlier clean-state checks.
        script = ('from pathlib import Path; import sys; from twobrain.gitrepo import commit; '
                  'commit(Path(sys.argv[1]), "confirmed edit", Path("general.json"))')
        result = subprocess.run([sys.executable, "-c", script, str(data)], capture_output=True, text=True,
                                env={**self.env, "PYTHONPATH": str(ROOT / "src")}, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.git(data, "show", "--format=", "--name-only", "HEAD"), "general.json")
        self.assertEqual(self.git(data, "show", ":README.md"), "Staged owner work")
        self.assertEqual((data / "README.md").read_text(), "Unstaged owner work")

    def test_failed_commit_retains_the_draft_and_reports_the_failure(self):
        data = self.initialize()
        revision = self.git(data, "rev-parse", "HEAD")
        hook = data / ".git/hooks/pre-commit"
        hook.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        hook.chmod(0o755)
        error = self.edit(data, "--general", expect=1)
        self.assertEqual(self.git(data, "rev-parse", "HEAD"), revision)
        self.assertTrue(self.draft().exists())
        self.assertIn(str(self.draft()), error["error"])
        self.assertEqual(json.loads((data / "general.json").read_text())["guidance"],
                         ["Edited and confirmed preference."])

    def test_interrupted_editor_retains_draft_and_releases_the_lock(self):
        data = self.initialize()
        original = (data / "general.json").read_bytes()
        revision = self.git(data, "rev-parse", "HEAD")
        script = '''import json, sys
from pathlib import Path
import twobrain.edit as editing
from twobrain.errors import BrainError
run = editing.subprocess.run
def interrupt(command, *args, **kwargs):
    if "--wait" in command:
        raise KeyboardInterrupt
    return run(command, *args, **kwargs)
editing.subprocess.run = interrupt
try:
    editing.edit(Path(sys.argv[1]), "general", None)
except BrainError as exc:
    print(json.dumps({"code": exc.code, "error": str(exc)}))
'''
        result = subprocess.run([sys.executable, "-c", script, str(data)], capture_output=True, text=True,
                                env={**self.env, "PYTHONPATH": str(ROOT / "src")}, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        error = json.loads(result.stdout)
        self.assertEqual(error["code"], 130)
        drafts = list((data / ".git/2brain-drafts").glob("*/general.json"))
        self.assertEqual(len(drafts), 1)
        self.assertIn(str(drafts[0]), error["error"])
        self.assertEqual(drafts[0].read_bytes(), original)
        self.assertEqual((data / "general.json").read_bytes(), original)
        self.assertEqual(self.git(data, "rev-parse", "HEAD"), revision)
        self.assertFalse((data / ".git/2brain.lock").exists())
