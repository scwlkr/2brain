#!/usr/bin/env node
"use strict";

const { spawnSync } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");

const root = path.resolve(__dirname, "..");
const launcher = path.join(root, "2brain");
const args = process.argv.slice(2);

function candidates() {
  if (process.env.TWOBRAIN_PYTHON) {
    return [process.env.TWOBRAIN_PYTHON];
  }
  if (process.platform === "win32") {
    return ["py", "python", "python3"];
  }
  return ["python3", "python"];
}

function resolvePython() {
  for (const command of candidates()) {
    const probe = spawnSync(
      command,
      ["-c", "import sys; assert sys.version_info >= (3, 10); print(sys.executable)"],
      { encoding: "utf8" },
    );
    if (probe.status === 0) {
      const executable = probe.stdout.trim();
      if (executable) {
        return executable;
      }
    }
  }
  return null;
}

if (!fs.existsSync(launcher)) {
  process.stderr.write("2brain npm package is missing the Python launcher file.\n");
  process.exit(1);
}

const python = resolvePython();
if (!python) {
  process.stderr.write(
    "2brain requires Python 3.10+ on PATH. Install Python, or set TWOBRAIN_PYTHON to a 3.10+ interpreter.\n",
  );
  process.exit(1);
}

const result = spawnSync(python, [launcher, ...args], { stdio: "inherit" });
if (result.error) {
  process.stderr.write(`${result.error.message}\n`);
  process.exit(1);
}
process.exit(result.status === null ? 1 : result.status);
