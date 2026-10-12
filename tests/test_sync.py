import json

from support import Scenario, record


class Synchronization(Scenario):
    def test_two_copies_merge_separate_records_and_same_record_compatible_edits(self):
        left, right, _ = self.pair()
        self.put(left, "tool", "git", record("Local checks."))
        self.put(right, "project", "owner/repo", record("Project preference."))
        self.call(left, "sync")
        self.call(right, "sync")
        self.call(left, "sync")
        self.assertEqual(self.call(left, "--list"), self.call(right, "--list"))
        many = record(*(f"Guidance {i}." for i in range(12)))
        self.put(left, "tool", "merge", many)
        self.call(left, "sync")
        self.call(right, "sync")
        local = json.loads(json.dumps(many))
        competing = json.loads(json.dumps(many))
        local["guidance"][0] = "Confirmed local change."
        competing["guidance"][-1] = "Confirmed remote change."
        self.put(left, "tool", "merge", local)
        self.put(right, "tool", "merge", competing)
        self.call(left, "sync")
        self.call(right, "sync")
        self.call(left, "sync")
        merged = self.call(left, "--tool", "merge")["context"]["guidance"]
        self.assertEqual(merged[0], local["guidance"][0])
        self.assertEqual(merged[-1], competing["guidance"][-1])
        self.assertEqual(self.git(left, "rev-parse", "HEAD"), self.git(right, "rev-parse", "HEAD"))

    def conflict_pair(self):
        left, right, remote = self.pair()
        local = self.put(left, "general", None, record("Local confirmed choice."))["revision"]
        competing = self.put(right, "general", None, record("Remote confirmed choice."))["revision"]
        self.call(left, "sync")
        error = self.call(right, "sync", expect=3)
        self.assertIn("general.json", error["error"])
        return left, right, remote, local, competing

    def test_conflict_preserves_versions_and_local_reads_then_resolves(self):
        left, right, _, local, competing = self.conflict_pair()
        self.assertEqual(self.git(right, "rev-parse", "HEAD"), competing)
        self.assertIn("<<<<<<<", (right / "general.json").read_text())
        response = self.call(right)
        self.assertEqual(response["general"]["guidance"], ["Remote confirmed choice."])
        self.assertEqual(len(response["warnings"]), 1)
        self.assertIn("Remote confirmed choice.", self.git(right, "show", ":2:general.json"))
        self.assertIn("Local confirmed choice.", self.git(right, "show", ":3:general.json"))
        self.call(right, "save", "--reason", "Unresolved test", expect=1)
        (right / "general.json").write_text(json.dumps(record("User resolved the competing choices.")), encoding="utf-8")
        self.call(right, "save", "--reason", "User explicitly resolved the conflict")
        self.call(right, "sync")
        self.call(left, "sync")
        self.assertEqual(self.call(left)["general"], self.call(right)["general"])
        self.git(right, "merge-base", "--is-ancestor", local, "HEAD")
        self.git(right, "merge-base", "--is-ancestor", competing, "HEAD")

    def test_abort_backs_up_partial_resolution_and_keeps_commits(self):
        _, right, _, local, competing = self.conflict_pair()
        partial = json.dumps(record("Partial resolution to preserve."))
        (right / "general.json").write_text(partial, encoding="utf-8")
        result = self.call(right, "abort")
        from pathlib import Path
        self.assertEqual((Path(result["recovery"]) / "general.json").read_text(), partial)
        self.assertEqual(self.git(right, "rev-parse", "HEAD"), competing)
        self.assertEqual(self.git(right, "rev-parse", "origin/main"), local)
        self.assertEqual(self.call(right)["general"]["guidance"], ["Remote confirmed choice."])
        self.assertFalse(self.call(right, "status")["merge_pending"])

    def test_failed_fetch_checkpoints_manual_edits_and_reads_remain_available(self):
        left, _, _ = self.pair()
        self.call(left, "remote", str(self.root / "missing-remote.git"))
        before = self.git(left, "rev-parse", "HEAD")
        (left / "general.json").write_text(json.dumps(record("Deliberate offline edit.")), encoding="utf-8")
        error = self.call(left, "sync", expect=1)
        self.assertIn("preserved", error["error"])
        self.assertNotEqual(self.git(left, "rev-parse", "HEAD"), before)
        self.assertFalse(self.call(left, "status")["dirty"])
        self.assertEqual(self.call(left)["general"]["guidance"], ["Deliberate offline edit."])

    def test_rejected_push_preserves_local_revision_and_retry_succeeds(self):
        left, right, remote = self.pair()
        self.git(remote, "config", "receive.denyNonFastForwards", "true")
        self.git(remote, "config", "receive.denyCurrentBranch", "refuse")
        # Turn the bare repository into a checked-out-branch rejector without adding executable hooks.
        self.git(remote, "config", "core.bare", "false")
        self.git(remote, "config", "core.worktree", str(self.root / "remote-work"))
        (self.root / "remote-work").mkdir()
        saved = self.put(left, "tool", "git", record("Keep this update."))["revision"]
        self.call(left, "sync", expect=1)
        self.assertEqual(self.git(left, "rev-parse", "HEAD"), saved)
        self.assertEqual(self.call(left, "--tool", "git")["context"]["guidance"], ["Keep this update."])
        self.git(remote, "config", "core.bare", "true")
        self.git(remote, "config", "--unset", "core.worktree")
        self.call(left, "sync")
        self.call(right, "sync")
        self.assertEqual(self.call(right, "--tool", "git")["context"]["guidance"], ["Keep this update."])

    def test_concurrent_add_and_delete_modify_conflicts_keep_reads_usable(self):
        left, right, _ = self.pair()
        self.put(left, "tool", "git", record("First addition."))
        self.put(right, "tool", "git", record("Competing addition."))
        self.call(left, "sync")
        self.call(right, "sync", expect=3)
        self.assertEqual(self.call(right, "--tool", "git")["context"]["guidance"], ["Competing addition."])
        self.call(right, "abort")
        # Resolve deliberately, then create a modify/delete conflict on that shared record.
        (right / "tools/git.json").write_text(json.dumps(record("Shared decision.")), encoding="utf-8")
        self.call(right, "save", "--reason", "User selected shared decision")
        self.call(right, "sync", expect=3)
        (right / "tools/git.json").write_text(json.dumps(record("Shared decision.")), encoding="utf-8")
        self.call(right, "save", "--reason", "User resolved addition conflict")
        self.call(right, "sync")
        self.call(left, "sync")
        self.call(left, "remove", "--tool", "git", "--reason", "User asked to forget")
        self.put(right, "tool", "git", record("Keep modified decision."))
        self.call(left, "sync")
        self.call(right, "sync", expect=3)
        response = self.call(right, "--tool", "git")
        self.assertEqual(response["context"]["guidance"], ["Keep modified decision."])
        self.assertEqual(len(response["warnings"]), 1)

    def test_local_deletion_with_remote_modification_does_not_invent_local_context(self):
        left, right, _ = self.pair()
        self.put(left, "tool", "git", record("Shared preference."))
        self.call(left, "sync")
        self.call(right, "sync")
        self.put(left, "tool", "git", record("Remote modification."))
        self.call(right, "remove", "--tool", "git", "--reason", "User asked to forget locally")
        self.call(left, "sync")
        self.call(right, "sync", expect=3)
        error = self.call(right, "--tool", "git", expect=1)
        self.assertIn("no committed local version", error["error"])
        self.assertEqual(self.call(right)["general"]["guidance"], ["Be concise."])

    def test_unrelated_histories_are_not_forced_together(self):
        left, _, remote = self.pair()
        unrelated = self.root / "unrelated"
        self.call(unrelated, "init")
        self.call(unrelated, "remote", str(remote))
        before = self.git(unrelated, "rev-parse", "HEAD")
        self.call(unrelated, "sync", expect=1)
        self.assertEqual(self.git(unrelated, "rev-parse", "HEAD"), before)
        self.assertEqual(self.call(left)["general"]["guidance"], ["Be concise."])
