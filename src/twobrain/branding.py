"""The packaged brand kit is also the source of terminal color tokens."""

import json
import re
from importlib.resources import files

from .errors import BrainError


def kit():
    return files("twobrain").joinpath("brand")


def style():
    return json.loads(kit().joinpath("style.json").read_text(encoding="utf-8"))


def palette():
    return dict(re.fullmatch(r"([a-z]+) (#[0-9A-Fa-f]{6})", item).groups()
                for item in style()["colors"])


def export(destination):
    destination = destination.expanduser().absolute()
    if destination.exists():
        raise BrainError(f"Brand export already exists: {destination}. Choose a new directory; existing files are preserved.")
    destination.mkdir(parents=True, exist_ok=False)

    def copy(source, target):
        for child in source.iterdir():
            path = target / child.name
            if child.is_dir():
                path.mkdir()
                copy(child, path)
            else:
                path.write_bytes(child.read_bytes())

    try:
        copy(kit(), destination)
    except OSError as exc:
        raise BrainError(f"Brand export could not finish: {exc}. Partial files are retained at {destination}.") from exc
    return {"brand": "2brain", "guide": str(destination / "index.html"),
            "board": str(destination / "references/brand-board.svg"), "directory": str(destination)}


def describe():
    return {"brand": "2brain", "palette": palette(), "style": style(),
            "export": "2brain brand --export <new-directory>",
            "reference": "Editable reconstruction of the supplied brand board; the original attachment is not included."}
