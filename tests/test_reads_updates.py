import json
import subprocess
import sys

from support import ROOT, Scenario, record


class ReadsAndUpdates(Scenario):
    def test_selective_offline_reads_without_git_and_compact_discovery(self):
        data = self.initialize()
        self.put(data, "tool", "git", record("Use local checks."))
        self.put(data, "project", "owner/repo", record("Repository-specific convention."))
        (data / "tools/broken.json").write_text("invalid", encoding="utf-8")
        empty_path = self.root / "no-programs"
        empty_path.mkdir()
        general = self.call(data, env={"PATH": str(empty_path)})
        self.assertEqual(general["general"]["person"], "Fixture User")
        self.assertNotIn("context", general)
        tool = self.call(data, "--tool", "GIT", env={"PATH": str(empty_path)})
        self.assertNotIn("general", tool)
        self.assertEqual(tool["context"]["guidance"], ["Use local checks."])
        project = self.call(data, "--project", "repo", env={"PATH": str(empty_path)})
        self.assertEqual(project["project"], "owner/repo")
        self.assertEqual(project["precedence"], ["current_instructions", "wstack", "project", "general"])
        self.assertIn("Wstack owns coding workflow and wins over 2brain", project["policy"])
        inventory = self.call(data, "--list", env={"PATH": str(empty_path)})
        self.assertEqual(inventory["tools"], ["broken", "git"])
        text = self.call(data, raw=True, env={"PATH": str(empty_path)}).stdout
        self.assertLess(len(text.split()), 80)

    def test_create_replace_remove_and_undo_preserve_history(self):
        data = self.initialize()
        first = self.put(data, "tool", "git", record("First decision."))["revision"]
        second = self.put(data, "tool", "git", record("Second decision."))["revision"]
        self.call(data, "undo", second, "--reason", "User asked to restore first decision")
        self.assertEqual(self.call(data, "--tool", "git")["context"]["guidance"], ["First decision."])
        self.call(data, "remove", "--tool", "git", "--reason", "User asked to forget")
        self.assertFalse((data / "tools/git.json").exists())
        rows = self.call(data, "history", "--tool", "git")["history"]
        self.assertEqual(len(rows), 4)
        self.assertEqual(rows[-1]["revision"], first)
        self.call(data, "--tool", "git", expect=1)

    def test_multiline_guidance_round_trips_through_put_and_rejects_other_controls(self):
        data = self.initialize()
        guidance = ["First line.\nSecond line.", "Next paragraph."]
        payload = record(*guidance)
        payload["pointers"] = [{"label": "Docs", "target": "https://example.invalid/docs"}]
        self.call(data, "put", "--tool", "git", "--file", "-", "--reason", "User explicitly requested multiline guidance",
                  stdin=json.dumps(payload))
        disk = json.loads((data / "tools/git.json").read_text(encoding="utf-8"))
        cli = self.call(data, "--tool", "git")["context"]
        self.assertEqual(disk["guidance"], ["First line.\nSecond line.", "Next paragraph."])
        self.assertEqual(cli["guidance"], disk["guidance"])
        self.assertEqual(cli["pointers"], disk["pointers"])
        self.assertEqual(self.git(data, "log", "-1", "--format=%s"),
                         "2brain: update tools/git.json: User explicitly requested multiline guidance")

        before = (data / "tools/git.json").read_bytes()
        revision = self.git(data, "rev-parse", "HEAD")
        for bad in ["has\ttab", "has\rreturn", "has\x7fdel", "has\x00null"]:
            error = self.call(data, "put", "--tool", "git", "--file", "-", "--reason", "User request",
                              stdin=json.dumps(record(bad)), expect=1)
            self.assertIn("control", error["error"])
        error = self.call(data, "put", "--general", "--file", "-", "--reason", "line\nbreak",
                          stdin=json.dumps(record("Fine.")), expect=1)
        self.assertIn("one line", error["error"])
        error = self.call(data, "put", "--general", "--file", "-", "--reason", "User request",
                          stdin=json.dumps(record("Fine.", person="Line\nbreak")), expect=1)
        self.assertIn("one line", error["error"])
        broken_pointer = record("Fine.")
        broken_pointer["pointers"] = [{"label": "Bad\nlabel", "target": "https://example.invalid"}]
        error = self.call(data, "put", "--tool", "git", "--file", "-", "--reason", "User request",
                          stdin=json.dumps(broken_pointer), expect=1)
        self.assertIn("one line", error["error"])
        error = self.call(data, "put", "--tool", "git", "--file", "-", "--reason", "User request",
                          stdin=json.dumps(record(" \n ")), expect=1)
        self.assertIn("must contain", error["error"])
        self.assertEqual((data / "tools/git.json").read_bytes(), before)
        self.assertEqual(self.git(data, "rev-parse", "HEAD"), revision)

        fitted = "a" * 149 + "\n" + "b" * 150
        self.call(data, "put", "--tool", "git", "--file", "-", "--reason", "User request",
                  stdin=json.dumps(record(fitted)))
        self.assertEqual(self.call(data, "--tool", "git")["context"]["guidance"], [fitted])
        error = self.call(data, "put", "--tool", "git", "--file", "-", "--reason", "User request",
                          stdin=json.dumps(record(fitted + "c")), expect=1)
        self.assertIn("1–300", error["error"])
        general = record("Hello\nthere.", "Second.", person="Fixture User")
        self.call(data, "put", "--general", "--file", "-", "--reason", "User request", stdin=json.dumps(general))
        self.assertEqual(self.call(data)["general"]["guidance"], ["Hello\nthere.", "Second."])
        self.assertEqual(self.call(data)["general"]["person"], "Fixture User")
        oversized = record(*(["n" * 200] * 5), "m\n" * 100)
        error = self.call(data, "put", "--general", "--file", "-", "--reason", "User request",
                          stdin=json.dumps(oversized), expect=1)
        self.assertIn("1,000", error["error"])

    def test_stdin_put_and_validation_leave_previous_record_intact(self):
        data = self.initialize()
        before = (data / "general.json").read_bytes()
        revision = self.git(data, "rev-parse", "HEAD")
        self.call(data, "put", "--general", "--file", "-", "--reason", "User request",
                  stdin=json.dumps(record("x" * 301)), expect=1)
        self.assertEqual((data / "general.json").read_bytes(), before)
        self.assertEqual(self.git(data, "rev-parse", "HEAD"), revision)
        self.call(data, "put", "--tool", "git", "--file", "-", "--reason", "User request",
                  stdin=json.dumps(record("Confirmed preference.")))
        self.assertTrue((data / "tools/git.json").exists())
        self.call(data, "put", "--tool", "../escape", "--file", "-", "--reason", "User request",
                  stdin=json.dumps(record("Confirmed.")), expect=1)

    def test_project_ambiguity_case_and_windows_names(self):
        data = self.initialize()
        self.put(data, "project", "alice/repo", record("Alice repository."))
        self.put(data, "project", "bob/repo", record("Bob repository."))
        error = self.call(data, "--project", "repo", expect=1)
        self.assertIn("Ambiguous", error["error"])
        self.put(data, "project", "ALICE/REPO", record("Updated Alice repository."))
        self.assertEqual(self.call(data, "--list")["projects"], ["alice/repo", "bob/repo"])
        source = self.root / "input.json"
        self.call(data, "put", "--tool", "CON", "--file", str(source), "--reason", "User request", expect=1)
        self.call(data, "put", "--project", "repo", "--file", str(source), "--reason", "User request", expect=1)

    def test_manual_edits_save_and_unrelated_files_are_preserved(self):
        data = self.initialize()
        (data / "general.json").write_text(json.dumps(record("Manual confirmed preference.")), encoding="utf-8")
        self.call(data, "put", "--tool", "git", "--file", "-", "--reason", "User request",
                  stdin=json.dumps(record("Another preference.")), expect=1)
        self.call(data, "save", "--reason", "User confirmed manual edit")
        (data / "secret.txt").write_text("owner data", encoding="utf-8")
        error = self.call(data, "save", "--reason", "User request", expect=1)
        self.assertIn("non-record", error["error"])
        self.assertEqual((data / "secret.txt").read_text(), "owner data")
        self.assertEqual(self.call(data)["general"]["guidance"], ["Manual confirmed preference."])

    def test_lock_and_reinitialization_do_not_change_data(self):
        data = self.initialize()
        before = (data / "general.json").read_bytes()
        self.call(data, "init", expect=1)
        (data / ".git/2brain.lock").mkdir()
        self.call(data, "remove", "--general", "--reason", "User request", expect=1)
        self.assertEqual((data / "general.json").read_bytes(), before)
        self.call(data)  # Reads do not take the write lock.

    def test_seed_and_archive_work_independently_of_checkout(self):
        data = self.initialize()
        clone = self.root / "offline-seed"
        self.call(clone, "init", "--seed", str(data))
        self.assertEqual(self.call(data)["general"], self.call(clone)["general"])
        archive = self.root / "2brain.pyz"
        result = subprocess.run([sys.executable, str(ROOT / "project"), "build", "--output", str(archive)],
                                env=self.env, capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        result = subprocess.run([sys.executable, str(archive), "--data", str(clone), "--json"],
                                cwd=self.root, env=self.env, capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["general"]["person"], "Fixture User")

    def test_authenticated_url_is_rejected_without_storing_credentials(self):
        data = self.initialize()
        self.call(data, "remote", "https://token@example.invalid/repo.git", expect=1)
        self.assertNotIn("token", (data / ".git/config").read_text())

    def test_argument_errors_are_json_and_missing_reason_cannot_write(self):
        data = self.initialize()
        before = self.git(data, "rev-parse", "HEAD")
        error = self.call(data, "put", "--general", "--file", "-", expect=2)
        self.assertEqual(error["code"], 2)
        self.assertIn("reason", error["error"])
        self.call(data, "--unknown", expect=2)
        self.assertEqual(self.git(data, "rev-parse", "HEAD"), before)

    def test_native_installer_handles_spaces_in_paths(self):
        prefix = self.root / "installation with spaces"
        result = subprocess.run([sys.executable, str(ROOT / "install.py"), "--prefix", str(prefix)],
                                env=self.env, capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        launcher = prefix / "bin" / ("2brain.cmd" if sys.platform == "win32" else "2brain")
        result = subprocess.run([str(launcher), "--version"], env=self.env,
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("2brain 0.1.3", result.stdout)

    def test_untrusted_symlink_cannot_mutate_external_record(self):
        if sys.platform == "win32":
            self.skipTest("Windows symlink permission requires native qualification")
        data = self.initialize()
        outside = self.root / "outside.json"
        outside.write_text(json.dumps(record("Owner data.")), encoding="utf-8")
        (data / "tools").mkdir()
        (data / "tools/git.json").symlink_to(outside)
        self.call(data, "--tool", "git", expect=1)
        self.assertEqual(json.loads(outside.read_text())["guidance"], ["Owner data."])
