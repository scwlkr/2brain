"""Quiet sage accents; machine-readable and redirected output stay plain."""

import os
from dataclasses import dataclass

from .branding import palette

RESET = "\x1b[0m"


def use_color(mode, stream):
    if mode != "auto":
        return mode == "always"
    return stream.isatty() and "NO_COLOR" not in os.environ and os.environ.get("TERM") != "dumb"


def rgb(hex_color, background=False):
    values = ";".join(str(int(hex_color[i:i + 2], 16)) for i in (1, 3, 5))
    return f"\x1b[{48 if background else 38};2;{values}m"


@dataclass
class Theme:
    name: str = "dark"
    colored: bool = True

    def __post_init__(self):
        colors = palette()
        light = self.name == "light"
        self.colors = {"text": colors["ink" if light else "paper"],
                       "background": colors["paper" if light else "ink"],
                       "accent": colors["forest" if light else "sage"],
                       "muted": colors["stone" if light else "muted"],
                       "line": colors["fog" if light else "line"],
                       "selection": colors["sage"], "selected": colors["ink"]}

    def paint(self, text, role="text", background=None, bold=False):
        if not self.colored:
            return text
        prefix = rgb(self.colors[role])
        if background:
            prefix += rgb(self.colors[background], background=True)
        if bold:
            prefix += "\x1b[1m"
        return prefix + text + RESET


def decorate(text, name="dark"):
    theme = Theme(name)
    lines = []
    for index, line in enumerate(text.splitlines()):
        if line.startswith("- "):
            line = theme.paint("  · ", "accent") + line[2:]
        elif line.startswith("→ "):
            line = theme.paint(line, "muted")
        elif line.startswith("Current instructions win;"):
            line = theme.paint(line, "muted")
        elif ": " in line:
            label, value = line.split(": ", 1)
            line = theme.paint(label + ":", "accent", bold=True) + " " + value
        else:
            line = theme.paint(("2brain / " if index == 0 and not line.startswith("2brain") else "") + line, "accent", bold=True)
        lines.append(line)
    return "\n".join(lines)
