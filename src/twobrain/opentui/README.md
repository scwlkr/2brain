# 2brain OpenTUI

The terminal browser uses `@opentui/core` 0.6.2 with Bun 1.4.3. The Python CLI
remains the owner of record validation, discovery, selective reads, and conflict
behavior. The OpenTUI app calls that CLI's JSON interface through an argv array;
it never reads credentials, writes records, or runs a shell command.

OpenTUI owns the render tree, flexible layout, select/input/scroll widgets,
mouse/keyboard input, resizing, terminal modes, and cleanup. `main.ts` waits for
the renderer's `closed` promise on exit. Colors come from the existing brand kit,
passed by the Python launcher.

## Install and run on your computer

```sh
uv tool install --force "git+https://github.com/scwlkr/2brain@codex/2brain-terminal-brand"
2brain tui --setup --json
2brain tui
```

`--setup` downloads the private, pinned Bun binary from npm and verifies its
committed SHA-512 integrity before using it. It installs OpenTUI with
`bun install --production --frozen-lockfile`, then constructs and closes the real
native test renderer. It also probes cached installations when requested.
Nothing is installed into global Node/Bun directories or the context repository.
Ordinary CLI reads never trigger this setup. Existing context stays intact.

The application cache is separate from data: macOS `~/Library/Caches/2brain/opentui`,
Linux `$XDG_CACHE_HOME/2brain/opentui` or `~/.cache/2brain/opentui`, Windows
`%LOCALAPPDATA%/Cache/2brain/opentui`. Override with `TWOBRAIN_TUI_CACHE` when needed.
The source/lock digest gives each revision its own application directory; Bun and
downloaded packages are reused. Registry access is needed for the first setup.

## Develop and verify

```sh
python3 project tui-setup
python3 project tui-check
python3 project check
```

The project runner prepares a development copy in the cache with frozen
dependencies, type-checks it, and runs Bun tests through OpenTUI's native test
renderer against the actual Python backend. These assert full rendered frames,
not fragments of optimized terminal output. Python PTY tests also launch the
real entry point, exit with q/Ctrl+C, and verify terminal restoration.

When dependencies change deliberately, update `package.json` and regenerate
`bun.lock` with the pinned Bun version in an owned development copy. Commit the
lockfile. `runtime.json` owns verified Bun distribution URLs/checksums for supported
x64/arm64 macOS, Windows, and Linux targets. Never bypass TLS or checksum failures.

Python wheels and standalone archives retain these source files and the lockfile;
their first TUI launch uses the same setup. `node_modules` is never bundled into
the Python artifact. Native Linux behavior is verified; macOS/Windows use official
platform distributions and still need native execution on those systems.
