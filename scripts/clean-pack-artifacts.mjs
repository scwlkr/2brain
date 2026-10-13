#!/usr/bin/env node
"use strict";

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

function clean(dir) {
  if (!fs.existsSync(dir)) {
    return;
  }
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      if (entry.name === "__pycache__" || entry.name === "node_modules") {
        fs.rmSync(full, { recursive: true, force: true });
        continue;
      }
      clean(full);
      continue;
    }
    if (entry.name.endsWith(".pyc") || entry.name.endsWith(".tgz")) {
      fs.rmSync(full, { force: true });
    }
  }
}

clean(path.join(root, "src"));
clean(path.join(root, "bin"));
for (const name of fs.readdirSync(root)) {
  if (name.endsWith(".tgz")) {
    fs.rmSync(path.join(root, name), { force: true });
  }
}
