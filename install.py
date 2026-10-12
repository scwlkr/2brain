"""Install a standalone archive and native launcher; no pip/download required."""

import argparse
import os
import runpy
import shlex
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prefix", type=Path, required=True, help="e.g. ~/.local or %%LOCALAPPDATA%%/2brain-cli")
    args = parser.parse_args()
    prefix = args.prefix.expanduser().absolute()
    archive = prefix / "lib/2brain/2brain.pyz"
    runpy.run_path(str(Path(__file__).with_name("project")))["build"](archive)
    binaries = prefix / "bin"
    binaries.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        launcher = binaries / "2brain.cmd"
        if any(c in str(archive) + sys.executable for c in '%"\r\n'):
            parser.error("Installation paths containing percent, quotes or newlines are unsupported by cmd.exe.")
        launcher.write_bytes(f'@echo off\r\n"{sys.executable}" "{archive}" %*\r\n'.encode("utf-8"))
    else:
        launcher = binaries / "2brain"
        launcher.write_text(f"#!/bin/sh\nexec {shlex.quote(sys.executable)} {shlex.quote(str(archive))} \"$@\"\n", encoding="utf-8")
        launcher.chmod(0o755)
    print(f"Installed {launcher}. Add {binaries} to PATH if needed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
