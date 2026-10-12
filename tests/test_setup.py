import json
from unittest.mock import patch

from support import Scenario


class Setup(Scenario):
    def test_setup_clones_context_and_backs_up_global_instructions_and_override(self):
        _, _, remote = self.pair()
        data = self.root / "new-context"
        home = self.root / "codex with spaces"
        home.mkdir()
        (home / "AGENTS.md").write_bytes(b"Previous global preferences.\n")
        (home / "AGENTS.override.md").write_bytes(b"An old override.\n")
        result = self.call(data, "setup", str(remote), "--codex", env={"CODEX_HOME": str(home)})
        self.assertEqual(self.call(data)["general"]["person"], "Shane Walker")
        self.assertTrue(result["instructions_changed"])
        self.assertFalse((home / "AGENTS.override.md").exists())
        text = (home / "AGENTS.md").read_text()
        self.assertIn("run `2brain`", text)
        self.assertNotIn("Previous", text)
        from pathlib import Path
        backup = Path(result["instructions_backup"])
        self.assertEqual((backup / "AGENTS.md").read_bytes(), b"Previous global preferences.\n")
        self.assertEqual((backup / "AGENTS.override.md").read_bytes(), b"An old override.\n")
        revision = self.git(data, "rev-parse", "HEAD")
        count = len(list((home / "2brain-backups").iterdir()))
        repeated = self.call(data, "setup", "--codex", env={"CODEX_HOME": str(home), "PATH": self.env["PATH"]})
        self.assertFalse(repeated["instructions_changed"])
        self.assertEqual(len(list((home / "2brain-backups").iterdir())), count)
        self.assertEqual(self.git(data, "rev-parse", "HEAD"), revision)

    def test_failed_clone_or_remote_mismatch_does_not_touch_global_instructions(self):
        home = self.root / "codex"
        home.mkdir()
        original = b"Owner instructions.\n"
        (home / "AGENTS.md").write_bytes(original)
        self.call(self.root / "absent", "setup", str(self.root / "missing.git"), "--codex",
                  env={"CODEX_HOME": str(home)}, expect=1)
        self.assertEqual((home / "AGENTS.md").read_bytes(), original)
        left, _, _ = self.pair()
        self.call(left, "setup", "other-owner/other-context", "--codex", env={"CODEX_HOME": str(home)}, expect=1)
        self.assertEqual((home / "AGENTS.md").read_bytes(), original)

    def test_setup_without_codex_keeps_agent_instructions_and_manual_edits(self):
        data = self.initialize()
        home = self.root / "codex"
        (data / "general.json").write_text(json.dumps({"schema_version": 1, "guidance": ["Deliberate pending edit."], "pointers": []}), encoding="utf-8")
        before = self.git(data, "rev-parse", "HEAD")
        self.call(data, "setup", env={"CODEX_HOME": str(home)})
        self.assertFalse(home.exists())
        self.assertEqual(self.git(data, "rev-parse", "HEAD"), before)
        self.assertEqual(self.call(data)["general"]["guidance"], ["Deliberate pending edit."])

    def test_github_shorthand_and_explicit_url(self):
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
        from twobrain.setup import expand_remote
        self.assertEqual(expand_remote("scwlkr/2brain-context"), "https://github.com/scwlkr/2brain-context.git")
        self.assertEqual(expand_remote("git@github.com:owner/repo.git"), "git@github.com:owner/repo.git")

    def test_concurrent_editor_change_is_preserved(self):
        import os
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
        from twobrain.setup import configure_codex
        from twobrain.errors import BrainError
        home = self.root / "codex"
        home.mkdir()
        instructions = home / "AGENTS.md"
        instructions.write_bytes(b"Original.\n")
        read_bytes = Path.read_bytes
        calls = 0
        def competing_read(path):
            nonlocal calls
            if path == instructions:
                calls += 1
                if calls == 2:
                    instructions.write_bytes(b"Competing editor change.\n")
            return read_bytes(path)
        with patch.dict(os.environ, {"CODEX_HOME": str(home)}), patch.object(Path, "read_bytes", competing_read):
            with self.assertRaises(BrainError):
                configure_codex()
        self.assertEqual(instructions.read_bytes(), b"Competing editor change.\n")
