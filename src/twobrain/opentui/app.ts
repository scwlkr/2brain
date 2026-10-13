import {
  BoxRenderable, InputRenderable, InputRenderableEvents, RGBA, ScrollBoxRenderable,
  SelectRenderable, SelectRenderableEvents, TextRenderable, type CliRenderer, type KeyEvent,
} from "@opentui/core";
import {Backend, document, type Entry} from "./backend.ts";

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
  let searching = false;
  let reading = false;
  const root = new BoxRenderable(renderer, {id: "2brain", width: "100%", height: "100%", flexDirection: "column", backgroundColor: bg, padding: 1});
  renderer.root.add(root);
  const heading = new TextRenderable(renderer, {id: "heading", content: "2brain / your context, close at hand", fg: accent, height: 1, flexShrink: 0});
  const caption = new TextRenderable(renderer, {id: "caption", content: "LOCAL CONTEXT / READ ONLY", fg: muted, height: 1, marginBottom: 1, flexShrink: 0});
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
  const status = new TextRenderable(renderer, {id: "status", fg: muted, height: 1, marginTop: 1, flexShrink: 0});
  const help = new TextRenderable(renderer, {id: "help", fg: muted, height: 1, flexShrink: 0});
  for (const item of [heading, caption, search, body, status, help]) root.add(item);

  function layout() {
    const narrow = renderer.width < 78;
    heading.content = narrow ? "2brain / local context" : "2brain / your context, close at hand";
    list.visible = !narrow || !reading;
    detail.visible = !narrow || reading;
    list.width = narrow ? "100%" : 32;
    detail.border = narrow ? false : ["left"];
    detail.paddingLeft = narrow ? 0 : 2;
    help.content = searching ? "Enter apply · Esc clear · Ctrl+C quit" : narrow
      ? reading ? "↑↓ scroll · Esc back · q quit" : "↑↓ move · Enter read · / find · q quit"
      : `↑↓ ${reading ? "scroll" : "browse"} · Tab ${reading ? "browse" : "read"} · / search · PgUp/PgDn scroll · r refresh · q quit`;
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
    searching = next === "search";
    reading = next === "detail";
    (searching ? search : reading ? detail : list).focus();
    layout();
  }

  function key(key: KeyEvent) {
    if (key.ctrl && key.name === "c") { renderer.destroy(); return; }
    if (searching) {
      if (key.name === "escape") { search.value = ""; filter(); focus("list"); key.preventDefault(); }
      else if (key.name === "return" || key.name === "linefeed") { focus("list"); key.preventDefault(); }
      return;
    }
    if (key.name === "q") renderer.destroy();
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
