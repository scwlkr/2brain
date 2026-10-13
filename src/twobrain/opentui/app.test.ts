import {afterEach, expect, test} from "bun:test";
import {mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync} from "node:fs";
import {tmpdir} from "node:os";
import {join} from "node:path";
import {createTestRenderer} from "@opentui/core/testing";
import {createBrowser} from "./app.ts";
import {Backend} from "./backend.ts";

const cleanup: (() => Promise<void>)[] = [];
afterEach(async () => { for (const close of cleanup.splice(0).reverse()) await close(); });

async function fixture(width=100, height=24, color=true, theme: "dark" | "light"="dark") {
  const root=mkdtempSync(join(tmpdir(), "2brain-opentui-test-"));
  cleanup.push(async () => rmSync(root, {recursive:true, force:true}));
  mkdirSync(join(root, "tools"));
  mkdirSync(join(root, "projects/owner"), {recursive:true});
  const record=(...guidance:string[]) => JSON.stringify({schema_version:1, guidance, pointers:[]});
  writeFileSync(join(root,"general.json"),record("General OpenTUI proof."));
  writeFileSync(join(root,"tools/git.json"),record("Use local checks.", ...Array(12).fill("A long entry for meaningful scrolling.")));
  writeFileSync(join(root,"projects/owner/repo.json"),record("Project-specific OpenTUI proof."));
  const command: string[]=JSON.parse(process.env.TWOBRAIN_TEST_BACKEND || "[]");
  if (!command.length) throw new Error("Tests require the actual 2brain Python backend command.");
  const backend=new Backend([...command,"--data",root]);
  const harness=await createTestRenderer({width,height,exitOnCtrlC:false});
  cleanup.push(() => harness.dispose());
  const palette=backend.read(["brand"]).palette;
  const ui=createBrowser(harness.renderer,backend,{theme,color,palette});
  const frame=async () => { await harness.flush(); return harness.captureCharFrame(); };
  return {root,record,backend,harness,ui,frame};
}

test("OpenTUI loads selective context, filters names, and reports empty results",async () => {
  const f=await fixture();
  expect(await f.frame()).toContain("General OpenTUI proof.");
  expect(await f.frame()).toContain("Browse ·");
  expect(await f.frame()).toContain("type filter");
  f.harness.mockInput.pressKey("/");
  f.harness.mockInput.typeText("git");
  f.harness.mockInput.pressEnter();
  expect(await f.frame()).toContain("Use local checks.");
  expect(await f.frame()).toContain("1/1 records");
  f.harness.mockInput.pressKey("/");
  f.harness.mockInput.typeText("nonexistent");
  f.harness.mockInput.pressEnter();
  expect(await f.frame()).toContain("No matching records.");
  expect(await f.frame()).toContain("0/0 records");
});

test("browse mode type-to-filter without slash, keeping e for edit", async () => {
  const f = await fixture();
  expect(await f.frame()).toContain("Browse ·");
  f.harness.mockInput.typeText("git");
  const filtered = await f.frame();
  expect(filtered).toContain("Use local checks.");
  expect(filtered).toContain("1/1 records");
  expect(filtered).toContain("Search ·");
  f.harness.mockInput.pressEnter();
  expect(await f.frame()).toContain("Browse ·");
  f.harness.mockInput.pressKey("e");
  const editing = await f.frame();
  expect(editing).toContain("EDIT GUIDANCE");
  expect(editing).toContain("Use local checks.");
});

test("read focus announces mode and edit enter keeps guidance visible",async () => {
  const f=await fixture();
  f.harness.mockInput.pressArrow("down");
  f.harness.mockInput.pressEnter();
  const reading=await f.frame();
  expect(reading).toContain("Read ·");
  expect(reading).toContain("Use local checks.");
  f.harness.mockInput.pressEscape();
  await Bun.sleep(80); // Native stdin parser distinguishes Esc from an escape sequence.
  f.harness.mockInput.pressKey("e");
  const editing=await f.frame();
  expect(editing).toContain("EDIT GUIDANCE");
  expect(editing).toContain("Use local checks.");
  expect(editing).toContain("Blank line starts a new entry.");
});

test("narrow OpenTUI layout reads a record and returns to discovery",async () => {
  const f=await fixture(42);
  expect(await f.frame()).toContain("Enter read");
  f.harness.mockInput.pressArrow("down"); f.harness.mockInput.pressEnter();
  expect(await f.frame()).toContain("Use local checks.");
  f.harness.mockInput.pressEscape();
  await Bun.sleep(80); // Native stdin parser distinguishes Esc from an escape sequence.
  expect(await f.frame()).toContain("Enter read");
  f.harness.resize(100,24);
  expect(await f.frame()).toContain("Use local checks.");
});

test("scrolling reaches the policy and a corrupt selected record is recoverable",async () => {
  const f=await fixture(100,14);
  f.harness.mockInput.pressArrow("down");
  await f.frame();
  for (let i=0;i<5;i++) f.harness.mockInput.pressKey("\x1b[6~");
  expect(await f.frame()).toContain("Current instructions win;");
  writeFileSync(join(f.root,"tools/git.json"), "{broken");
  f.harness.mockInput.pressKey("r");
  // Refresh resets discovery to the general record; select the invalid tool again.
  f.harness.mockInput.pressArrow("down");
  expect(await f.frame()).toContain("Invalid record JSON:");
  f.harness.mockInput.pressArrow("up");
  expect(await f.frame()).toContain("General OpenTUI proof.");
});

test("browsing through OpenTUI never changes source record bytes",async () => {
  const f=await fixture();
  const before=readFileSync(join(f.root,"general.json"));
  f.harness.mockInput.pressArrow("down");
  f.harness.mockInput.pressArrow("down");
  expect(await f.frame()).toContain("Project-specific OpenTUI proof.");
  expect(readFileSync(join(f.root,"general.json"))).toEqual(before);
  expect(readFileSync(join(f.root,"tools/git.json"),"utf8")).toContain("Use local checks.");
});

test("q destroys the real OpenTUI renderer and completes native cleanup",async () => {
  const f=await fixture(); await f.frame();
  f.harness.mockInput.pressKey("q");
  await f.harness.renderer.closed;
  expect(f.harness.renderer.isDestroyed).toBe(true);
});

test("the OpenTUI light theme uses the saved brand palette",async () => {
  const f=await fixture(100,24,true,"light"); await f.frame();
  const spans=f.harness.captureSpans().lines.flatMap(line=>line.spans);
  const heading=spans.find(span=>span.text.includes("2brain /"));
  expect(heading?.fg.toInts()).toEqual([66,99,79,255]);
  expect(heading?.bg.toInts()).toEqual([248,248,244,255]);
});

function gitEnv(parent: string): Record<string, string> {
  const env: Record<string, string> = {};
  for (const [key, value] of Object.entries(process.env)) {
    if (value !== undefined) env[key] = value;
  }
  env.GIT_CONFIG_GLOBAL = join(parent, "no-global");
  env.GIT_CONFIG_NOSYSTEM = "1";
  env.GIT_AUTHOR_NAME = "2brain tests";
  env.GIT_AUTHOR_EMAIL = "tests@example.invalid";
  env.GIT_COMMITTER_NAME = "2brain tests";
  env.GIT_COMMITTER_EMAIL = "tests@example.invalid";
  return env;
}

async function writableFixture(color = true) {
  const parent = mkdtempSync(join(tmpdir(), "2brain-opentui-write-"));
  cleanup.push(async () => rmSync(parent, {recursive: true, force: true}));
  const root = join(parent, "local");
  const env = gitEnv(parent);
  const command: string[] = JSON.parse(process.env.TWOBRAIN_TEST_BACKEND || "[]");
  if (!command.length) throw new Error("Tests require the actual 2brain Python backend command.");
  const run = (args: string[], stdin?: string) => {
    const result = Bun.spawnSync([...command, "--data", root, "--json", ...args], {
      env, stdout: "pipe", stderr: "pipe", timeout: 20000,
      ...(stdin !== undefined ? {stdin: new TextEncoder().encode(stdin)} : {}),
    });
    const stdout = new TextDecoder().decode(result.stdout);
    const stderr = new TextDecoder().decode(result.stderr);
    if (result.exitCode !== 0) throw new Error(stdout + stderr);
    return JSON.parse(stdout);
  };
  run(["init"]);
  run(["put", "--general", "--file", "-", "--reason", "User explicitly requested this test preference"], JSON.stringify({
    schema_version: 1, person: "Fixture User", guidance: ["Keep local checks."],
    pointers: [{label: "Notes", target: "notes.md"}],
  }));
  run(["put", "--project", "owner/repo", "--file", "-", "--reason", "User explicitly requested this test preference"], JSON.stringify({
    schema_version: 1, guidance: ["Project line."],
    pointers: [{label: "Board", target: "https://example.invalid/board"}],
  }));
  const backend = new Backend([...command, "--data", root], env);
  const harness = await createTestRenderer({width: 100, height: 24, exitOnCtrlC: false});
  cleanup.push(() => harness.dispose());
  const palette = backend.read(["brand"]).palette;
  const ui = createBrowser(harness.renderer, backend, {theme: "dark", color, palette});
  const frame = async () => { await harness.flush(); return harness.captureCharFrame(); };
  return {root, backend, harness, frame, env, ui};
}

test("editing guidance saves multiline text through put and escape cancels", async () => {
  const f = await writableFixture();
  expect(await f.frame()).toContain("Keep local checks.");
  f.harness.mockInput.pressKey("/");
  f.harness.mockInput.typeText("repo");
  f.harness.mockInput.pressEnter();
  expect(await f.frame()).toContain("Project line.");
  f.harness.mockInput.pressKey("e");
  expect(await f.frame()).toContain("EDIT GUIDANCE");
  expect(await f.frame()).toContain("Project line.");
  f.harness.mockInput.pressKey("END");
  f.harness.mockInput.pressEnter();
  f.harness.mockInput.typeText("Same entry continued.");
  f.harness.mockInput.pressEnter();
  f.harness.mockInput.pressEnter();
  f.harness.mockInput.typeText("Second entry.");
  f.harness.mockInput.pressKey("s", {ctrl: true});
  const saved = await f.frame();
  expect(saved).toContain("Saved guidance.");
  expect(saved).toContain("Same entry continued.");
  expect(saved).toContain("Second entry.");
  const disk = JSON.parse(readFileSync(join(f.root, "projects/owner/repo.json"), "utf8"));
  const cli = f.backend.read(["--project", "owner/repo"]).context;
  expect(disk).toEqual(cli);
  expect(disk.guidance).toEqual(["Project line.\nSame entry continued.", "Second entry."]);
  expect(disk.pointers).toEqual([{label: "Board", target: "https://example.invalid/board"}]);
  f.harness.mockInput.pressEscape();
  await Bun.sleep(80); // Native stdin parser distinguishes Esc from an escape sequence.
  expect(await f.frame()).toContain("Keep local checks.");
  f.harness.mockInput.pressKey("e");
  expect(await f.frame()).toContain("EDIT GUIDANCE");
  f.harness.mockInput.pressKey("END");
  f.harness.mockInput.pressEnter();
  f.harness.mockInput.pressEnter();
  f.harness.mockInput.typeText("General extra.");
  f.harness.mockInput.pressEnter({meta: true});
  const general = JSON.parse(readFileSync(join(f.root, "general.json"), "utf8"));
  expect(general).toEqual(f.backend.read([]).general);
  expect(general.guidance).toEqual(["Keep local checks.", "General extra."]);
  expect(general.person).toBe("Fixture User");
  expect(general.pointers).toEqual([{label: "Notes", target: "notes.md"}]);
  expect(readFileSync(join(f.root, "projects/owner/repo.json"), "utf8")).toContain("Same entry continued.");
  const log = Bun.spawnSync(["git", "-C", f.root, "log", "-1", "--format=%s"], {env: f.env, stdout: "pipe", stderr: "pipe"});
  expect(new TextDecoder().decode(log.stdout)).toBe("2brain: update general.json: edited via tui\n");

  const before = readFileSync(join(f.root, "general.json"));
  f.harness.mockInput.pressKey("e");
  f.harness.mockInput.typeText("DO NOT SAVE");
  f.harness.mockInput.pressEscape();
  await Bun.sleep(80); // Native stdin parser distinguishes Esc from an escape sequence.
  expect(await f.frame()).toContain("Edit cancelled.");
  expect(readFileSync(join(f.root, "general.json"))).toEqual(before);
});

test("a rejected guidance save stays in the editor and leaves the file unchanged", async () => {
  const f = await writableFixture();
  const before = readFileSync(join(f.root, "general.json"));
  f.harness.mockInput.pressKey("e");
  expect(await f.frame()).toContain("EDIT GUIDANCE");
  f.harness.mockInput.pressKey("END");
  f.harness.mockInput.typeText("x".repeat(301));
  f.harness.mockInput.pressKey("s", {ctrl: true});
  const frame = await f.frame();
  expect(frame).toContain("EDIT GUIDANCE");
  expect(frame).toContain("1–300");
  expect(readFileSync(join(f.root, "general.json"))).toEqual(before);
});

test("the add menu creates a tool and a project and refuses a duplicate", async () => {
  const f = await writableFixture();
  f.harness.mockInput.pressKey("a");
  const menu = await f.frame();
  expect(menu).toContain("New tool");
  expect(menu).toContain("New project");
  f.harness.mockInput.pressEnter();
  expect(await f.frame()).toContain("Enter a tool name.");
  f.harness.mockInput.typeText("ripgrep");
  f.harness.mockInput.pressEnter();
  const createdTool = await f.frame();
  expect(createdTool).toContain("EDIT GUIDANCE");
  expect(createdTool).toContain("Blank line starts a new entry.");
  const tool = JSON.parse(readFileSync(join(f.root, "tools/ripgrep.json"), "utf8"));
  expect(tool).toEqual({schema_version: 1, guidance: [], pointers: []});
  expect(f.backend.read(["--list"]).tools).toEqual(["ripgrep"]);
  const log = Bun.spawnSync(["git", "-C", f.root, "log", "-1", "--format=%s"], {env: f.env, stdout: "pipe", stderr: "pipe"});
  expect(new TextDecoder().decode(log.stdout)).toBe("2brain: update tools/ripgrep.json: edited via tui\n");

  f.harness.mockInput.typeText("Prefer ripgrep for search.");
  f.harness.mockInput.pressKey("s", {ctrl: true});
  const savedTool = await f.frame();
  expect(savedTool).toContain("Saved guidance.");
  expect(savedTool).toContain("ripgrep / tool");
  expect(JSON.parse(readFileSync(join(f.root, "tools/ripgrep.json"), "utf8")).guidance).toEqual(["Prefer ripgrep for search."]);

  f.harness.mockInput.pressKey("a");
  f.harness.mockInput.pressArrow("down");
  f.harness.mockInput.pressEnter();
  expect(await f.frame()).toContain("Enter owner/repo.");
  f.harness.mockInput.typeText("acme/widget");
  f.harness.mockInput.pressEnter();
  const createdProject = await f.frame();
  expect(createdProject).toContain("EDIT GUIDANCE");
  const project = JSON.parse(readFileSync(join(f.root, "projects/acme/widget.json"), "utf8"));
  expect(project).toEqual({schema_version: 1, guidance: [], pointers: []});
  f.harness.mockInput.pressEscape();
  await Bun.sleep(80); // Native stdin parser distinguishes Esc from an escape sequence.
  const afterCancel = await f.frame();
  expect(afterCancel).toContain("Edit cancelled.");
  expect(afterCancel).toContain("acme/widget / project");
  expect(JSON.parse(readFileSync(join(f.root, "projects/acme/widget.json"), "utf8"))).toEqual({
    schema_version: 1, guidance: [], pointers: [],
  });
  const listed = f.backend.read(["--list"]);
  expect(listed.tools).toEqual(["ripgrep"]);
  expect(listed.projects).toEqual(["acme/widget", "owner/repo"]);

  const before = readFileSync(join(f.root, "tools/ripgrep.json"));
  f.harness.mockInput.pressKey("a");
  f.harness.mockInput.pressEnter();
  f.harness.mockInput.typeText("Ripgrep");
  f.harness.mockInput.pressEnter();
  expect(await f.frame()).toContain("already exists");
  expect(readFileSync(join(f.root, "tools/ripgrep.json"))).toEqual(before);

  f.harness.mockInput.pressEscape();
  await Bun.sleep(80); // Native stdin parser distinguishes Esc from an escape sequence.
  f.harness.mockInput.pressKey("a");
  f.harness.mockInput.pressEnter();
  f.harness.mockInput.typeText("../nope");
  f.harness.mockInput.pressEnter();
  expect(await f.frame()).toContain("Invalid name");
  expect(f.backend.read(["--list"]).tools).toEqual(["ripgrep"]);
});

test("NO_COLOR presentation retains default foreground and background for content",async () => {
  const f=await fixture(100,24,false); await f.frame();
  const spans=f.harness.captureSpans().lines.flatMap(line=>line.spans);
  for (const phrase of ["2brain /","General OpenTUI proof.","LOCAL CONTEXT"]) {
    const span=spans.find(item=>item.text.includes(phrase));
    expect(span?.fg.intent).toBe("default");
    expect(span?.bg.intent).toBe("default");
  }
});

test("detail pane paints title, guidance bullet, pointer label, and policy with brand roles", async () => {
  const f = await writableFixture();
  const frame = await f.frame();
  expect(frame).toContain("Fixture User");
  expect(frame).toContain("· Keep local checks.");
  expect(frame).toContain("→ Notes: notes.md");
  expect(frame).toContain("Current instructions win;");
  const spans = f.harness.captureSpans().lines.flatMap(line => line.spans);
  expect(spans.find(span => span.text.includes("Fixture User"))?.fg.toInts()).toEqual([148, 180, 156, 255]);
  expect(spans.find(span => span.text === "· ")?.fg.toInts()).toEqual([148, 180, 156, 255]);
  expect(spans.find(span => span.text.includes("Keep local checks."))?.fg.toInts()).toEqual([248, 248, 244, 255]);
  expect(spans.find(span => span.text === "→ ")?.fg.toInts()).toEqual([173, 182, 173, 255]);
  expect(spans.find(span => span.text === "Notes:")?.fg.toInts()).toEqual([148, 180, 156, 255]);
  expect(spans.find(span => span.text.includes("notes.md"))?.fg.toInts()).toEqual([248, 248, 244, 255]);
  expect(spans.find(span => span.text.includes("Current instructions win;"))?.fg.toInts()).toEqual([173, 182, 173, 255]);
});

test("NO_COLOR detail hierarchy stays readable with default span colors", async () => {
  const f = await writableFixture(false);
  const shown = await f.frame();
  expect(shown).toContain("· Keep local checks.");
  expect(shown).toContain("→ Notes: notes.md");
  const spans = f.harness.captureSpans().lines.flatMap(line => line.spans);
  for (const phrase of ["Fixture User", "· ", "Keep local checks.", "→ ", "Notes:", "notes.md", "Current instructions win;"]) {
    const span = spans.find(item => item.text.includes(phrase) || item.text === phrase);
    expect(span?.fg.intent).toBe("default");
  }
});
