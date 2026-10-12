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

test("NO_COLOR presentation retains default foreground and background for content",async () => {
  const f=await fixture(100,24,false); await f.frame();
  const spans=f.harness.captureSpans().lines.flatMap(line=>line.spans);
  for (const phrase of ["2brain /","General OpenTUI proof.","LOCAL CONTEXT"]) {
    const span=spans.find(item=>item.text.includes(phrase));
    expect(span?.fg.intent).toBe("default");
    expect(span?.bg.intent).toBe("default");
  }
});
