#!/usr/bin/env node
"use strict";

import { spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const requireJson = createRequire(import.meta.url);
const pkg = requireJson("../package.json");

function run(command, args, options = {}) {
  const result = spawnSync(command, args, {
    cwd: root,
    encoding: "utf8",
    ...options,
  });
  if (result.status !== 0) {
    const detail = (result.stderr || result.stdout || "").trim();
    throw new Error(`${command} ${args.join(" ")} failed (${result.status}): ${detail}`);
  }
  return result;
}

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

assert(pkg.name === "@scwlkr/2brain", `expected package name @scwlkr/2brain, got ${pkg.name}`);
assert(pkg.bin && pkg.bin["2brain"] === "bin/2brain.js", "expected bin.2brain -> bin/2brain.js");

run("node", [path.join(root, "scripts/clean-pack-artifacts.mjs")]);
const pack = run("npm", ["pack", "--json"]);
const packed = JSON.parse(pack.stdout);
assert(Array.isArray(packed) && packed.length === 1, "npm pack --json should return one entry");
const tarball = path.join(root, packed[0].filename);
assert(fs.existsSync(tarball), `missing tarball ${tarball}`);

const listing = run("tar", ["-tzf", tarball]).stdout.split("\n").filter(Boolean);
const relative = listing.map((entry) => entry.replace(/^package\//, ""));

const required = ["package.json", "bin/2brain.js", "2brain", "src/twobrain/cli.py", "README.md"];
for (const item of required) {
  assert(relative.includes(item), `packed tarball missing ${item}`);
}

const forbidden = [
  /^tests\//,
  /^\.git\//,
  /^\.github\//,
  /node_modules\//,
  /__pycache__\//,
  /\.pyc$/,
  /(^|\/)\.env/,
  /credential/i,
  /2brain-context/,
  /general\.json$/,
  /tools\/.+\.json$/,
  /projects\/.+\.json$/,
];
for (const entry of relative) {
  for (const pattern of forbidden) {
    assert(!pattern.test(entry), `packed tarball must not include ${entry}`);
  }
}

const staging = fs.mkdtempSync(path.join(os.tmpdir(), "2brain-npm-pack-"));
try {
  run("tar", ["-xzf", tarball, "-C", staging]);
  const extracted = path.join(staging, "package");
  const binPath = path.join(extracted, "bin", "2brain.js");
  fs.chmodSync(binPath, 0o755);
  const version = run(process.execPath, [binPath, "--version"], {
    cwd: extracted,
    env: process.env,
  });
  const printed = version.stdout.trim();
  assert(printed.includes(pkg.version.split("-")[0]), `bin --version ${printed} should include ${pkg.version}`);
  console.log(`verify-npm-pack ok: ${packed[0].filename} (${relative.length} files), bin --version => ${printed}`);
} finally {
  fs.rmSync(staging, { recursive: true, force: true });
  fs.rmSync(tarball, { force: true });
}
