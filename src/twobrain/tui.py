"""Read-only local context browsing; no background networking or writes."""

from dataclasses import dataclass
from types import SimpleNamespace

from .appearance import Theme, use_color
from .errors import BrainError
from .records import discover, select
from .terminal import session
from .tui_view import frame


@dataclass(frozen=True)
class Entry:
    kind: str
    name: str

    @property
    def label(self):
        return "General" if self.kind == "general" else self.name


class Browser:
    def __init__(self, root, kind="general", name=None):
        self.root = root
        self.search = ""
        self.searching = False
        self.selected = 0
        self.offset = 0
        self.detail = False
        self.refresh()
        if name:
            _, canonical = select(root, kind, name)
            self.selected = next(i for i, item in enumerate(self.visible) if item.kind == kind and item.name == canonical)

    def refresh(self):
        inventory = discover(self.root)
        self.entries = [Entry("general", "general")]
        self.entries += [Entry("tool", name) for name in inventory["tools"]]
        self.entries += [Entry("project", name) for name in inventory["projects"]]
        self.selected = min(self.selected, max(0, len(self.visible) - 1))
        self.offset = 0

    @property
    def visible(self):
        return [entry for entry in self.entries if self.search.casefold() in f"{entry.kind} {entry.label}".casefold()]

    def content(self):
        from .cli import query
        entries = self.visible
        if not entries:
            return {"empty": "No matching records. Press / to change the search, or Esc to clear it."}
        entry = entries[self.selected]
        args = SimpleNamespace(tool=entry.name if entry.kind == "tool" else None,
                               project=entry.name if entry.kind == "project" else None, list=False)
        try:
            return query(self.root, args)
        except (BrainError, OSError, UnicodeError) as exc:
            return {"error": str(exc)}

    def key(self, key, page):
        if self.searching:
            if key in ("enter", "escape"):
                self.searching = False
                if key == "escape":
                    self.search = ""
            elif key == "backspace":
                self.search = self.search[:-1]
            elif len(key) == 1 and key.isprintable():
                self.search += key
            elif key == "quit":
                return False
            self.selected = self.offset = 0
            return True
        if key in ("q", "quit"):
            return False
        if key == "escape":
            if self.detail:
                self.detail = False
            elif self.search:
                self.search = ""
                self.selected = self.offset = 0
            else:
                return False
        elif key == "/":
            self.searching = True
            self.detail = False
        elif key == "r":
            self.refresh()
        elif key in ("enter", "right", "tab"):
            self.detail = not self.detail if key == "tab" else True
        elif key == "left":
            self.detail = False
        elif key in ("pagedown", "pageup"):
            self.offset = max(0, self.offset + (page if key == "pagedown" else -page))
        elif key in ("j", "down", "k", "up"):
            amount = 1 if key in ("j", "down") else -1
            if self.detail:
                self.offset = max(0, self.offset + amount)
            else:
                self.selected = max(0, min(len(self.visible) - 1, self.selected + amount))
                self.offset = 0
        elif key in ("home", "g", "end", "G"):
            self.selected = 0 if key in ("home", "g") else max(0, len(self.visible) - 1)
            self.offset = 0
        return True


def browse(root, theme="dark", color="auto", kind="general", name=None):
    import sys
    model = Browser(root, kind, name)
    appearance = Theme(theme, use_color(color, sys.stdout))
    try:
        with session() as terminal:
            dimensions = terminal.size()
            terminal.draw(frame(model, *dimensions, appearance))
            while True:
                key = terminal.key()
                resized = terminal.size()
                if key is not None and not model.key(key, max(1, resized[1] - 8)):
                    break
                if key is not None or resized != dimensions:
                    dimensions = resized
                    terminal.draw(frame(model, *dimensions, appearance))
    except KeyboardInterrupt:
        pass
