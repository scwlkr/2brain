import {
  BoxRenderable, InputRenderable, InputRenderableEvents, RGBA, ScrollBoxRenderable,
  SelectRenderable, SelectRenderableEvents, TextRenderable, TextareaRenderable,
  type CliRenderer, type KeyEvent,
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
  type Screen = {name: "browse" | "search" | "read"} | {name: "edit"; entry: Entry; pointers: StoredRecord["pointers"]; person?: string};
  let screen: Screen = {name: "browse"};
  const root = new BoxRenderable(renderer, {id: "2brain", width: "100%", height: "100%", flexDirection: "column", backgroundColor: bg, padding: 1});
  renderer.root.add(root);
  const heading = new TextRenderable(renderer, {id: "heading", content: "2brain / your context, close at hand", fg: accent, height: 1, flexShrink: 0});
  const caption = new TextRenderable(renderer, {id: "caption", content: "LOCAL CONTEXT / EDITABLE", fg: muted, height: 1, marginBottom: 1, flexShrink: 0});
  const search = new InputRenderable(renderer, {id: "search", placeholder: "/ search records", placeholderColor: muted, cursorColor: fg, textColor: fg, backgroundColor: bg, focusedBackgroundColor: bg, focusedTextColor: accent, marginBottom: 1});
  const body = new BoxRenderable(renderer, {id: "body", flexDirection: "row", flexGrow: 1, minHeight: 0});
  const list = new SelectRenderable(renderer, {id: "records", width: 32, flexShrink: 0, height: "100%",
    backgroundColor: bg, focusedBackgroundColor: bg, textColor: muted, focusedTextColor: muted,
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
  const status = new TextRenderable(renderer, {id: "status", fg: muted, height: 1, marginTop: 1, flexShrink: 0});
  const help = new TextRenderable(renderer, {id: "help", fg: muted, height: 1, flexShrink: 0});
  for (const item of [heading, caption, search, body, editor, status, help]) root.add(item);

  function layout() {
    const narrow = renderer.width < 78;
    const editing = screen.name === "edit";
    const reading = screen.name === "read";
    const searching = screen.name === "search";
    heading.content = narrow ? "2brain / local context" : "2brain / your context, close at hand";
    caption.content = editing ? "EDIT GUIDANCE" : "LOCAL CONTEXT / EDITABLE";
    search.visible = !editing;
    body.visible = !editing;
    editor.visible = editing;
    editor.flexGrow = editing ? 1 : 0;
    editor.height = editing ? Math.max(4, renderer.height - 8) : 0;
    if (!editing) {
      list.visible = !narrow || !reading;
      detail.visible = !narrow || reading;
      list.width = narrow ? "100%" : 32;
      detail.border = narrow ? false : ["left"];
      detail.paddingLeft = narrow ? 0 : 2;
    }
    help.content = editing ? "Alt+Enter or Ctrl+S save · Esc cancel" : searching ? "Enter apply · Esc clear · Ctrl+C quit" : narrow
      ? reading ? "↑↓ scroll · Esc back · q quit" : "↑↓ move · Enter read · e edit · q quit"
      : `↑↓ ${reading ? "scroll" : "browse"} · Tab ${reading ? "browse" : "read"} · / search · e edit · PgUp/PgDn scroll · r refresh · q quit`;
  }

  function selection() {
    const entry = visible[list.getSelectedIndex()];
    text.content = entry ? document(backend.view(entry)) : "No matching records. Press / to change the search, or Esc to clear it.";
    detail.scrollTo(0);
    status.content = `${entry ? list.getSelectedIndex() + 1 : 0}/${visible.length} records`;
    layout();
  }

  function filter() {
    visible = entries.filter(entry => `${entry.kind} ${entry.name}`.toLowerCase().includes(search.value.toLowerCase()));
    list.options = visible.map(entry => ({name: entry.kind === "general" ? "General" : `${entry.name} / ${entry.kind}`, description: "", value: entry}));
    list.setSelectedIndex(0);
    selection();
  }

  function focus(next: "search" | "list" | "detail") {
    screen = next === "search" ? {name: "search"} : next === "detail" ? {name: "read"} : {name: "browse"};
    (next === "search" ? search : next === "detail" ? detail : list).focus();
    layout();
  }

  function showBrowse() {
    screen = {name: "browse"};
    layout();
    list.focus();
  }

  function beginEdit() {
    const entry = visible[list.getSelectedIndex()];
    if (!entry) { status.content = "No record selected."; return; }
    const view = backend.view(entry);
    const data = view.context ?? view.general;
    if (view.error || !data) { status.content = view.error || "No record to edit."; return; }
    screen = {name: "edit", entry, pointers: data.pointers ?? [], person: data.person};
    editor.setText(guidanceToProse(data.guidance));
    status.content = "Blank line starts a new entry.";
    layout();
    editor.focus();
  }

  function saveEdit() {
    if (screen.name !== "edit") return;
    const record: StoredRecord = {schema_version: 1, guidance: proseToGuidance(editor.plainText), pointers: screen.pointers};
    if (screen.person) record.person = screen.person;
    const entry = screen.entry;
    try { backend.write(entry, record); }
    catch (error) {
      status.content = error instanceof Error ? error.message : String(error);
      return;
    }
    entries = backend.entries();
    showBrowse();
    filter();
    const index = visible.findIndex(item => item.kind === entry.kind && item.name === entry.name);
    if (index >= 0) list.setSelectedIndex(index);
    status.content = "Saved guidance.";
  }

  function cancelEdit() {
    showBrowse();
    selection();
    status.content = "Edit cancelled.";
  }

  function key(key: KeyEvent) {
    if (key.ctrl && key.name === "c") { renderer.destroy(); return; }
    if (screen.name === "edit") {
      if (key.name === "escape") { cancelEdit(); key.preventDefault(); }
      else if (key.ctrl && key.name === "s") { saveEdit(); key.preventDefault(); }
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
    } else if (key.name === "r") { entries = backend.entries(); filter(); }
    else return;
    key.preventDefault();
  }

  search.on(InputRenderableEvents.INPUT, filter);
  list.on(SelectRenderableEvents.SELECTION_CHANGED, selection);
  list.on(SelectRenderableEvents.ITEM_SELECTED, () => focus("detail"));
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
    renderer.keyInput.off("keypress", key); renderer.off("resize", layout); root.destroyRecursively();
  }};
}
