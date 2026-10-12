import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def record(*guidance, person=None):
    value = {"schema_version": 1, "guidance": list(guidance), "pointers": []}
    if person:
        value["person"] = person
    return value


class Scenario(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="2brain-tests-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.env = dict(os.environ, GIT_CONFIG_GLOBAL=str(self.root / "no-global"),
                        GIT_CONFIG_NOSYSTEM="1", GIT_AUTHOR_NAME="2brain tests",
                        GIT_AUTHOR_EMAIL="tests@example.invalid", GIT_COMMITTER_NAME="2brain tests",
                        GIT_COMMITTER_EMAIL="tests@example.invalid", PYTHONDONTWRITEBYTECODE="1")

    def call(self, data, *args, expect=0, env=None, raw=False, stdin=None):
        command = [sys.executable, str(ROOT / "2brain"), "--data", str(data), *args]
        if not raw:
            command.append("--json")
        result = subprocess.run(command, capture_output=True, text=True,
                                env={**self.env, **(env or {})}, input=stdin, timeout=45)
        self.assertEqual(result.returncode, expect, result.stdout + result.stderr)
        return result if raw else json.loads(result.stdout)

    def git(self, data, *args):
        result = subprocess.run(["git", "-C", str(data), *args], capture_output=True,
                                text=True, env=self.env, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        return result.stdout.strip()

    def put(self, data, kind, name, value):
        source = self.root / "input.json"
        source.write_text(json.dumps(value), encoding="utf-8")
        selector = ["--general"] if kind == "general" else [f"--{kind}", name]
        return self.call(data, "put", *selector, "--file", str(source), "--reason", "User explicitly requested this test preference")

    def initialize(self):
        data = self.root / "local"
        self.call(data, "init")
        self.put(data, "general", None, record("Be concise.", person="Shane Walker"))
        return data

    def pair(self):
        local = self.initialize()
        remote = self.root / "remote.git"
        self.git(self.root, "init", "--bare", "-b", "main", str(remote))
        self.call(local, "remote", str(remote))
        self.call(local, "sync")
        second = self.root / "second"
        self.call(second, "init", "--remote", str(remote))
        return local, second, remote
