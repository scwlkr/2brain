import {afterEach, expect, test} from "bun:test";
import {existsSync, mkdtempSync, readFileSync, rmSync} from "node:fs";
import {tmpdir} from "node:os";
import {join} from "node:path";
import {Backend, document, guidanceToProse, proseToGuidance, type StoredRecord} from "./backend.ts";

const cleanup: string[] = [];
afterEach(() => { for (const root of cleanup.splice(0)) rmSync(root, {recursive: true, force: true}); });

function command(): string[] {
  const value: string[] = JSON.parse(process.env.TWOBRAIN_TEST_BACKEND || "[]");
  if (!value.length) throw new Error("Tests require the actual 2brain Python backend command.");
  return value;
}

function gitEnv(root: string): Record<string, string> {
  const env: Record<string, string> = {};
  for (const [key, value] of Object.entries(process.env)) {
    if (value !== undefined) env[key] = value;
  }
  env.GIT_CONFIG_GLOBAL = join(root, "no-global");
  env.GIT_CONFIG_NOSYSTEM = "1";
  env.GIT_AUTHOR_NAME = "2brain tests";
  env.GIT_AUTHOR_EMAIL = "tests@example.invalid";
  env.GIT_COMMITTER_NAME = "2brain tests";
  env.GIT_COMMITTER_EMAIL = "tests@example.invalid";
  return env;
}

function spawnBrain(env: Record<string, string>, args: string[]) {
  const result = Bun.spawnSync([...command(), ...args], {env, stdout: "pipe", stderr: "pipe", timeout: 20000});
  const stdout = new TextDecoder().decode(result.stdout);
  const stderr = new TextDecoder().decode(result.stderr);
  if (result.exitCode !== 0) throw new Error(stdout + stderr);
  return stdout;
}

test("prose helpers split blank lines and keep single newlines", () => {
  expect(guidanceToProse(["Line one.\nLine two.", "Next"])).toBe("Line one.\nLine two.\n\nNext");
  expect(proseToGuidance("  alpha  \n\n\nbeta\ngamma  \n")).toEqual(["alpha", "beta\ngamma"]);
  expect(proseToGuidance("\n\n  \n")).toEqual([]);
  expect(guidanceToProse([])).toBe("");
  expect(proseToGuidance("one\r\n\r\ntwo")).toEqual(["one", "two"]);
  expect(proseToGuidance(guidanceToProse(["Line one.\nLine two.", "Next"]))).toEqual(["Line one.\nLine two.", "Next"]);
});

test("document asks for the next edit when a record has no guidance and no pointers", () => {
  expect(document({
    context: {guidance: [], pointers: []},
    tool: "blank",
  })).toBe([
    "blank",
    "",
    "No guidance yet.",
    "e writes guidance · p adds pointers · a creates a record.",
    "",
  ].join("\n"));
  expect(document({
    context: {guidance: [], pointers: [{label: "Notes", target: "notes.md"}]},
    project: "owner/repo",
  })).toBe([
    "owner/repo",
    "",
    "→ Notes: notes.md",
    "",
  ].join("\n"));
});

test("document keeps saved context and read warnings without a policy footer", () => {
  const plain = document({
    context: {
      guidance: ["Use local checks."],
      pointers: [{label: "Board", target: "https://example.invalid/board"}],
    },
    tool: "git",
    warnings: ["stale tip"],
  });
  expect(plain).toBe([
    "git",
    "",
    "· Use local checks.",
    "",
    "→ Board: https://example.invalid/board",
    "",
    "Warning: stale tip",
    "",
  ].join("\n"));
});

test("Backend.write saves multiline guidance through put", () => {
  const parent = mkdtempSync(join(tmpdir(), "2brain-write-"));
  cleanup.push(parent);
  const root = join(parent, "local");
  const env = gitEnv(parent);
  spawnBrain(env, ["--data", root, "--json", "init"]);
  const backend = new Backend([...command(), "--data", root], env);
  const record: StoredRecord = {
    schema_version: 1,
    guidance: ["First line.\nSecond line.", "Next paragraph."],
    pointers: [{label: "Docs", target: "https://example.invalid/docs"}],
  };
  const saved = backend.write({kind: "tool", name: "git"}, record);
  expect(saved.message).toBe("Saved tools/git.json locally.");
  const disk = JSON.parse(readFileSync(join(root, "tools/git.json"), "utf8"));
  const cli = backend.read(["--tool", "git"]).context;
  expect(disk).toEqual(cli);
  expect(disk.guidance).toEqual(["First line.\nSecond line.", "Next paragraph."]);
  const log = Bun.spawnSync(["git", "-C", root, "log", "-1", "--format=%s"], {env, stdout: "pipe", stderr: "pipe"});
  expect(new TextDecoder().decode(log.stdout)).toBe("2brain: update tools/git.json: edited via tui\n");

  expect(() => backend.write({kind: "tool", name: "git"}, {...record, guidance: ["bad\there"]})).toThrow("control");
  expect(JSON.parse(readFileSync(join(root, "tools/git.json"), "utf8")).guidance).toEqual(["First line.\nSecond line.", "Next paragraph."]);

  const general = backend.write({kind: "general", name: "General"}, {
    schema_version: 1, guidance: ["Hi\nthere"], pointers: [], person: "Ada",
  });
  expect(general.message).toBe("Saved general.json locally.");
  expect(backend.read([]).general).toEqual(JSON.parse(readFileSync(join(root, "general.json"), "utf8")));

  const project = backend.write({kind: "project", name: "acme/widget"}, {
    schema_version: 1, guidance: ["Ship\nit"], pointers: [],
  });
  expect(project.message).toBe("Saved projects/acme/widget.json locally.");
  const listed = backend.read(["--list"]);
  expect(listed.tools).toEqual(["git"]);
  expect(listed.projects).toEqual(["acme/widget"]);
  expect(backend.read(["--project", "acme/widget"]).context.guidance).toEqual(["Ship\nit"]);
});

test("Backend.remove deletes a tool and a project and refuses general", () => {
  const parent = mkdtempSync(join(tmpdir(), "2brain-remove-"));
  cleanup.push(parent);
  const root = join(parent, "local");
  const env = gitEnv(parent);
  spawnBrain(env, ["--data", root, "--json", "init"]);
  const backend = new Backend([...command(), "--data", root], env);
  backend.write({kind: "tool", name: "git"}, {schema_version: 1, guidance: ["Use local checks."], pointers: []});
  backend.write({kind: "project", name: "acme/widget"}, {schema_version: 1, guidance: ["Ship it."], pointers: []});
  const generalBefore = readFileSync(join(root, "general.json"));
  const removedTool = backend.remove({kind: "tool", name: "git"});
  expect(removedTool.message).toBe("Removed tools/git.json locally.");
  expect(existsSync(join(root, "tools/git.json"))).toBe(false);
  expect(backend.read(["--list"]).tools).toEqual([]);
  const removedProject = backend.remove({kind: "project", name: "acme/widget"});
  expect(removedProject.message).toBe("Removed projects/acme/widget.json locally.");
  expect(existsSync(join(root, "projects/acme/widget.json"))).toBe(false);
  expect(backend.read(["--list"]).projects).toEqual([]);
  expect(() => backend.remove({kind: "general", name: "General"})).toThrow("Replace general guidance with an empty record to clear it; keep general.json.");
  expect(readFileSync(join(root, "general.json"))).toEqual(generalBefore);
  const log = Bun.spawnSync(["git", "-C", root, "log", "--format=%s"], {env, stdout: "pipe", stderr: "pipe"});
  const subjects = new TextDecoder().decode(log.stdout);
  expect(subjects).toContain("2brain: remove tools/git.json: edited via tui");
  expect(subjects).toContain("2brain: remove projects/acme/widget.json: edited via tui");
});
