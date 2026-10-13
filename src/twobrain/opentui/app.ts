import {
  BoxRenderable, InputRenderable, InputRenderableEvents, RGBA, ScrollBoxRenderable,
  SelectRenderable, SelectRenderableEvents, TextRenderable, TextareaRenderable,
  createTimeline, type CliRenderer, type KeyEvent, type Timeline,
} from "@opentui/core";
import {Backend, document, guidanceToProse, proseToGuidance, type Entry, type StoredRecord} from "./backend.ts";

export type Settings = {theme: "dark" | "light"; color: boolean; palette: Record<string, string>; initial?: Entry};

export function createBrowser(renderer: CliRenderer, backend: Backend, settings: Settings) {
  const p = settings.palette;
  const light = settings.theme === "light";
  const fg = settings.color ? p[light ? "ink" : "paper"] : RGBA.defaultForeground();
  const bg = settings.color ? p[light ? "paper" : "ink"] : RGBA.defaultBackground();
  const accent = settings.color ? p[light ? "forest" : "sage"] : fg;
  const muted = settings.color ? p[light ? "stone" : "muted"] : fg;
  const line = settings.color ? p[light ? "fog" : "line"] : fg;
  let entries = backend.entries();
  let visible = entries;
  const viewCache = new Map<string, string>();
  let motion: Timeline | null = null;
  type Screen = {name: "browse" | "search" | "read"}
    | {name: "edit"; entry: Entry; pointers: StoredRecord["pointers"]; person?: string}
    | {name: "add"}
    | {name: "name"; kind: "tool" | "project"};
  let screen: Screen = {name: "browse"};
  const root = new BoxRenderable(renderer, {id: "2brain", width: "100%", height: "100%", flexDirection: "column", backgroundColor: bg, padding: 1});
  renderer.root.add(root);
  const heading = new TextRenderable(renderer, {id: "heading", content: "2brain / your context, close at hand", fg: accent, height: 1, flexShrink: 0});
  const caption = new TextRenderable(renderer, {id: "caption", content: "LOCAL CONTEXT / EDITABLE", fg: muted, height: 1, marginBottom: 1, flexShrink: 0});
  const search = new InputRenderable(renderer, {id: "search", placeholder: "/ search records", placeholderColor: muted, cursorColor: fg, textColor: fg, backgroundColor: bg, focusedBackgroundColor: bg, focusedTextColor: accent, marginBottom: 1});
  const body = new BoxRenderable(renderer, {id: "body", flexDirection: "row", flexGrow: 1, minHeight: 0});
  const list = new SelectRenderable(renderer, {id: "records", width: 32, flexShrink: 0, height: "100%",
    backgroundColor: bg, focusedBackgroundColor: bg, textColor: muted, focusedTextColor: fg,
    selectedBackgroundColor: settings.color ? p.sage : bg, selectedTextColor: settings.color ? p.ink : fg,
    selectedDescriptionColor: settings.color ? p.ink : fg, showDescription: false, showSelectionIndicator: true,
    options: []});
  const detail = new ScrollBoxRenderable(renderer, {id: "detail", flexGrow: 1, minWidth: 0, height: "100%",
    border: ["left"], borderColor: line, paddingLeft: 2, scrollX: false, scrollY: true,
    scrollbarOptions: {visible: false}, contentOptions: {flexDirection: "column"}});
  const text = new TextRenderable(renderer, {id: "record-text", width: "100%", wrapMode: "word", fg, content: ""});
  detail.add(text);
  body.add(list); body.add(detail);
  const editor = new TextareaRenderable(renderer, {
    id: "guidance-editor", width: "100%", flexGrow: 1, minHeight: 0, visible: false, wrapMode: "word",
    backgroundColor: bg, textColor: fg, focusedBackgroundColor: bg, focusedTextColor: fg, cursorColor: accent,
    placeholder: "Write guidance. A blank line starts another entry.", placeholderColor: muted,
    onSubmit: () => saveEdit(),
  });
  const addMenu = new SelectRenderable(renderer, {
    id: "add-menu", width: "100%", flexGrow: 0, height: 0, visible: false,
    backgroundColor: bg, focusedBackgroundColor: bg, textColor: fg, focusedTextColor: accent,
    selectedBackgroundColor: settings.color ? p.sage : bg, selectedTextColor: settings.color ? p.ink : fg,
    showDescription: false, showSelectionIndicator: true,
    options: [
      {name: "New tool", description: "", value: "tool"},
      {name: "New project", description: "", value: "project"},
    ],
  });
  const nameInput = new InputRenderable(renderer, {
    id: "name-input", visible: false, flexShrink: 0,
    placeholder: "name", placeholderColor: muted, cursorColor: fg, textColor: fg,
    backgroundColor: bg, focusedBackgroundColor: bg, focusedTextColor: accent,
  });
  const status = new TextRenderable(renderer, {id: "status", fg: muted, height: 1, marginTop: 1, flexShrink: 0});
  const help = new TextRenderable(renderer, {id: "help", fg: muted, height: 1, flexShrink: 0});
  for (const item of [heading, caption, search, body, editor, addMenu, nameInput, status, help]) root.add(item);

  function entryKey(entry: Entry) {
    return `${entry.kind}:${entry.name}`;
  }

  function invalidateViews(entry?: Entry) {
    if (entry) viewCache.delete(entryKey(entry));
    else viewCache.clear();
  }

  function cachedDocument(entry: Entry) {
    const key = entryKey(entry);
    const hit = viewCache.get(key);
    if (hit !== undefined) return hit;
    const rendered = document(backend.view(entry));
    viewCache.set(key, rendered);
    return rendered;
  }

  function stopMotion() {
    if (!motion) return;
    motion.pause();
    motion = null;
  }

  function playMotion(build: (timeline: Timeline) => void) {
    stopMotion();
    motion = createTimeline({duration: 160, autoplay: true}, renderer);
    build(motion);
  }

  function flashStatus(message: string, tone: "muted" | "accent" = "muted") {
    status.fg = tone === "accent" ? accent : muted;
    status.content = message;
    status.opacity = 0.35;
    playMotion(timeline => timeline.add(status, {opacity: 1, duration: 90, ease: "outQuad"}));
  }

  function modeLabel() {
    if (screen.name === "edit") return "Edit";
    if (screen.name === "add" || screen.name === "name") return "New";
    if (screen.name === "search") return "Search";
    if (screen.name === "read") return "Read";
    return "Browse";
  }

  function recordStatus(extra?: string) {
    const entry = visible[list.getSelectedIndex()];
    const count = `${entry ? list.getSelectedIndex() + 1 : 0}/${visible.length}`;
    flashStatus(extra ?? `${modeLabel()} · ${count} records`, screen.name === "edit" || screen.name === "read" ? "accent" : "muted");
  }

  function layout() {
    const narrow = renderer.width < 78;
    const editing = screen.name === "edit";
    const adding = screen.name === "add";
    const naming = screen.name === "name";
    const overlay = editing || adding || naming;
    const reading = screen.name === "read";
    const searching = screen.name === "search";
    heading.content = narrow ? "2brain / local context" : "2brain / your context, close at hand";
    caption.content = editing ? "EDIT GUIDANCE" : adding || naming ? "NEW RECORD" : "LOCAL CONTEXT / EDITABLE";
    caption.fg = editing || adding || naming || reading ? accent : muted;
    search.visible = !overlay;
    body.visible = !overlay;
    editor.visible = editing;
    editor.flexGrow = editing ? 1 : 0;
    editor.height = editing ? Math.max(4, renderer.height - 8) : 0;
    addMenu.visible = adding;
    addMenu.flexGrow = adding ? 1 : 0;
    addMenu.height = adding ? Math.max(4, renderer.height - 8) : 0;
    nameInput.visible = naming;
    nameInput.height = naming ? 1 : 0;
    if (!overlay) {
      list.visible = !narrow || !reading;
      detail.visible = !narrow || reading;
      list.width = narrow ? "100%" : 32;
      detail.border = narrow ? false : ["left"];
      detail.borderColor = reading ? accent : line;
      detail.paddingLeft = narrow ? 0 : 2;
    }
    help.content = editing ? "Alt+Enter or Ctrl+S save · Esc cancel"
      : adding ? "↑↓ choose · Enter select · Esc cancel"
      : naming ? "Enter create · Esc cancel"
      : searching ? "Enter apply · Esc clear · Ctrl+C quit" : narrow
      ? reading ? "↑↓ scroll · Esc back · q quit" : "↑↓ · Enter read · e edit · a add · q quit"
      : `↑↓ ${reading ? "scroll" : "browse"} · Tab ${reading ? "browse" : "read"} · / search · e edit · a add · PgUp/PgDn scroll · r refresh · q quit`;
  }

  function selection() {
    const entry = visible[list.getSelectedIndex()];
    text.content = entry ? cachedDocument(entry) : "No matching records. Press / to change the search, or Esc to clear it.";
    detail.scrollTo(0);
    const count = `${entry ? list.getSelectedIndex() + 1 : 0}/${visible.length}`;
    status.fg = muted;
    status.content = `${modeLabel()} · ${count} records`;
    status.opacity = 1;
  }

  function filter() {
    visible = entries.filter(entry => `${entry.kind} ${entry.name}`.toLowerCase().includes(search.value.toLowerCase()));
    list.options = visible.map(entry => ({name: entry.kind === "general" ? "General" : `${entry.name} / ${entry.kind}`, description: "", value: entry}));
    list.setSelectedIndex(0);
    selection();
    layout();
  }

  function focus(next: "search" | "list" | "detail") {
    screen = next === "search" ? {name: "search"} : next === "detail" ? {name: "read"} : {name: "browse"};
    (next === "search" ? search : next === "detail" ? detail : list).focus();
    layout();
    if (next === "detail") {
      detail.opacity = 0.72;
      status.fg = accent;
      status.content = `${modeLabel()} · ${visible[list.getSelectedIndex()] ? list.getSelectedIndex() + 1 : 0}/${visible.length} records`;
      status.opacity = 0.35;
      playMotion(timeline => {
        timeline.add(detail, {opacity: 1, duration: 110, ease: "outQuad"});
        timeline.add(status, {opacity: 1, duration: 90, ease: "outQuad"});
      });
      return;
    }
    detail.opacity = 1;
    recordStatus();
  }

  function showBrowse() {
    stopMotion();
    editor.opacity = 1;
    addMenu.opacity = 1;
    detail.opacity = 1;
    status.opacity = 1;
    screen = {name: "browse"};
    layout();
    list.focus();
  }

  function beginEdit() {
    const entry = visible[list.getSelectedIndex()];
    if (!entry) { flashStatus("No record selected."); return; }
    const view = backend.view(entry);
    const data = view.context ?? view.general;
    if (view.error || !data) { flashStatus(view.error || "No record to edit."); return; }
    screen = {name: "edit", entry, pointers: data.pointers ?? [], person: data.person};
    editor.setText(guidanceToProse(data.guidance));
    layout();
    editor.opacity = 1;
    editor.paddingLeft = 3;
    editor.focus();
    status.fg = accent;
    status.content = "Blank line starts a new entry.";
    status.opacity = 0.35;
    playMotion(timeline => {
      timeline.add(editor, {paddingLeft: 0, duration: 120, ease: "outQuad"});
      timeline.add(status, {opacity: 1, duration: 90, ease: "outQuad"});
    });
  }

  function saveEdit() {
    if (screen.name !== "edit") return;
    const record: StoredRecord = {schema_version: 1, guidance: proseToGuidance(editor.plainText), pointers: screen.pointers};
    if (screen.person) record.person = screen.person;
    const entry = screen.entry;
    try { backend.write(entry, record); }
    catch (error) {
      flashStatus(error instanceof Error ? error.message : String(error));
      return;
    }
    invalidateViews(entry);
    entries = backend.entries();
    showBrowse();
    filter();
    const index = visible.findIndex(item => item.kind === entry.kind && item.name === entry.name);
    if (index >= 0) list.setSelectedIndex(index);
    selection();
    flashStatus("Saved guidance.", "accent");
  }

  function leaveToBrowse(message: string) {
    showBrowse();
    selection();
    flashStatus(message);
  }

  function beginAdd() {
    screen = {name: "add"};
    addMenu.setSelectedIndex(0);
    layout();
    addMenu.opacity = 1;
    addMenu.paddingLeft = 3;
    addMenu.focus();
    status.fg = accent;
    status.content = "Create a tool or project record.";
    status.opacity = 0.35;
    playMotion(timeline => {
      timeline.add(addMenu, {paddingLeft: 0, duration: 120, ease: "outQuad"});
      timeline.add(status, {opacity: 1, duration: 90, ease: "outQuad"});
    });
  }

  function beginName(kind: "tool" | "project") {
    screen = {name: "name", kind};
    nameInput.value = "";
    nameInput.placeholder = kind === "tool" ? "tool name" : "owner/repo";
    layout();
    nameInput.focus();
    flashStatus(kind === "tool" ? "Enter a tool name." : "Enter owner/repo.", "accent");
  }

  function createNamed() {
    if (screen.name !== "name") return;
    const kind = screen.kind;
    const name = nameInput.value.trim();
    if (!name) { flashStatus("Enter a name."); return; }
    if (entries.some(item => item.kind === kind && item.name.toLowerCase() === name.toLowerCase())) {
      flashStatus(`A ${kind} record named ${name} already exists.`);
      return;
    }
    const entry: Entry = {kind, name};
    try { backend.write(entry, {schema_version: 1, guidance: [], pointers: []}); }
    catch (error) {
      flashStatus(error instanceof Error ? error.message : String(error));
      return;
    }
    invalidateViews();
    entries = backend.entries();
    search.value = "";
    showBrowse();
    filter();
    const index = visible.findIndex(item => item.kind === kind && item.name === name);
    if (index >= 0) list.setSelectedIndex(index);
    selection();
    flashStatus(`Created ${name}. Press e to edit.`, "accent");
  }

  function key(key: KeyEvent) {
    if (key.ctrl && key.name === "c") { renderer.destroy(); return; }
    if (screen.name === "edit") {
      if (key.name === "escape") { leaveToBrowse("Edit cancelled."); key.preventDefault(); }
      else if (key.ctrl && key.name === "s") { saveEdit(); key.preventDefault(); }
      return;
    }
    if (screen.name === "add") {
      if (key.name === "escape") { leaveToBrowse("Create cancelled."); key.preventDefault(); }
      return;
    }
    if (screen.name === "name") {
      if (key.name === "escape") { leaveToBrowse("Create cancelled."); key.preventDefault(); }
      else if (key.name === "return" || key.name === "linefeed") { createNamed(); key.preventDefault(); }
      return;
    }
    if (screen.name === "search") {
      if (key.name === "escape") { search.value = ""; filter(); focus("list"); key.preventDefault(); }
      else if (key.name === "return" || key.name === "linefeed") { focus("list"); key.preventDefault(); }
      return;
    }
    const reading = screen.name === "read";
    if (key.name === "q") renderer.destroy();
    else if (key.name === "e" && !key.ctrl && !key.meta && !key.shift) beginEdit();
    else if (key.name === "a" && !key.ctrl && !key.meta && !key.shift) beginAdd();
    else if (key.name === "/") focus("search");
    else if (key.name === "tab") focus(reading ? "list" : "detail");
    else if (key.name === "return" || key.name === "right") focus("detail");
    else if (key.name === "escape" || key.name === "left") {
      if (reading) focus("list");
      else if (search.value) { search.value = ""; filter(); }
      else renderer.destroy();
    } else if (key.name === "pagedown" || key.name === "pageup") {
      detail.scrollBy((renderer.height - 8) * (key.name === "pagedown" ? 1 : -1));
    } else if (reading && ["j", "k", "up", "down"].includes(key.name)) {
      detail.scrollBy(["j", "down"].includes(key.name) ? 1 : -1);
    } else if (key.name === "r") { invalidateViews(); entries = backend.entries(); filter(); }
    else return;
    key.preventDefault();
  }

  search.on(InputRenderableEvents.INPUT, filter);
  list.on(SelectRenderableEvents.SELECTION_CHANGED, selection);
  list.on(SelectRenderableEvents.ITEM_SELECTED, () => focus("detail"));
  addMenu.on(SelectRenderableEvents.ITEM_SELECTED, (_index, option) => {
    if (screen.name !== "add") return;
    beginName(option.value === "project" ? "project" : "tool");
  });
  renderer.keyInput.on("keypress", key);
  renderer.on("resize", layout);
  filter();
  if (settings.initial) {
    const initial = settings.initial;
    const index = entries.findIndex(entry => entry.kind === initial.kind && entry.name === initial.name);
    if (index >= 0) list.setSelectedIndex(index);
  }
  focus("list");
  return {root, list, search, detail, text, dispose: () => {
    stopMotion();
    renderer.keyInput.off("keypress", key); renderer.off("resize", layout); root.destroyRecursively();
  }};
}
