# 2brain

Small, portable personalization for terminal agents. `2brain` reads a short introduction; tool and repository details load only when requested. Your current instructions always take precedence.

Python 3.10+ and Git 2.28+; no Python runtime packages, model, database, or server. Python's standard library keeps ordinary CLI reads portable and offline. The optional OpenTUI browser manages its own Bun runtime and locked dependencies. Separate UTF-8 JSON records validate before saving and merge through Git. Git is only required for writes/history/sync.

## Setup

The CLI package and your personalization data stay separate. Install the CLI from npm or from this repository. Keep context in a local data directory you own, optionally synced through any Git remote you control. No credentials belong in records or remote URLs.

npm package `@scwlkr/2brain` ships the `2brain` command. It embeds the Python CLI and runs it with Python 3.10+ from your PATH (override with `TWOBRAIN_PYTHON`). Personalization data is never part of the package.

Stable channel (release builds, npm dist-tag `stable`):

```sh
npm install -g @scwlkr/2brain@stable
2brain init
```

Dev channel (builds from `main`, npm dist-tag `dev`):

```sh
npm install -g @scwlkr/2brain@dev
2brain --version
```

`npx @scwlkr/2brain@stable --version` works the same without a global install. Channel policy lives in [RELEASING.md](RELEASING.md).

With [uv](https://docs.astral.sh/uv/guides/tools/) instead of npm:

```sh
uv tool install "git+https://github.com/scwlkr/2brain.git@stable"
2brain init
```

uv installs the Python package `twobrain-cli` in its own environment and creates the platform launcher. It can acquire a compatible Python interpreter when needed. Your existing Git credential helper handles authentication for git installs and sync. No token belongs in either command.

If uv reports its executable directory is missing from PATH, run `uv tool update-shell` once and reopen the terminal. On Windows, install uv through your normal package manager (for example `winget install --id astral-sh.uv --exact`) if it is not already available.

`2brain init` creates empty context offline. `2brain init --seed <record-directory>` copies supplied records without networking. Existing directories are never replaced. Git needs your existing `user.name`/`user.email` configuration for commits. Failed initialization retains partial work at the path reported in its error.

Primary onboarding for multi-machine sync is local init, then any Git remote you own, then sync. A second GitHub repository is optional, not required.

```sh
2brain init
2brain remote <URL>
2brain sync
```

On additional computers, clone with `2brain init --remote <URL>`. Use a normal Git URL or a local path to a bare repository. HTTPS, SSH, and filesystem remotes all work. Privacy comes from how you create the remote, not from local reads.

`2brain setup owner/repo` remains optional shorthand when the remote already lives on GitHub. It also accepts a full Git URL for any host. It clones when absent and otherwise preserves the existing local copy, including manual edits. It refuses a different remote rather than silently switching datasets.

Optional Codex wiring uses `--codex`. `2brain setup --codex` (with or without a remote) replaces global Codex personalization with only the short 2brain loader. It saves exact previous `AGENTS.md` and `AGENTS.override.md` bytes under the Codex home's inactive `2brain-backups/` directory, then removes the active override so the loader is used. It honors `CODEX_HOME`. Repeating setup makes no extra backup when the loader is already installed. Without `--codex`, agent instructions are untouched. Failed context initialization leaves agent instructions untouched. Restart Codex after setup so it sees the launcher and new instructions.

Installation is a normal package install; it never clones personalization or edits agent instructions as an install hook. Personalization stays in your local data directory and optional remote. The git `stable` branch and the npm `stable` dist-tag advance only to published releases. Ordinary `main` commits feed the npm `dev` dist-tag. Git credential-helper behavior for uv git installs is documented by [uv](https://docs.astral.sh/uv/concepts/authentication/git/).

To update npm installs:

```sh
npm install -g @scwlkr/2brain@stable
npm install -g @scwlkr/2brain@dev
```

To update an existing uv installation from a tag or commit pin, switch to `stable` once:

```sh
uv tool install --force --refresh "git+https://github.com/scwlkr/2brain.git@stable"
2brain --version
```

For subsequent uv releases:

```sh
uv tool upgrade twobrain-cli
2brain --version
```

These commands update the CLI. Run `2brain sync` to exchange personalization changes with your other computers. Updating the CLI preserves local context, pending edits, history, and agent instructions. `@scwlkr/2brain` is the npm package name; `twobrain-cli` is the Python package name; `2brain` is the executable in both cases.

To select a specific git release with uv, use `uv tool install --force "git+https://github.com/scwlkr/2brain.git@v0.1.3"`. A tag or full commit SHA stays pinned when running `uv tool upgrade`; re-install with a different tag or `stable` to change it. To uninstall: `npm uninstall -g @scwlkr/2brain` or `uv tool uninstall twobrain-cli`. Your context/history and Codex instruction backups remain available. Maintainers follow [RELEASING.md](RELEASING.md) to publish versions and advance `stable`.

Advanced source installation remains available: run `python3 install.py --prefix ~/.local` from a clone on macOS/Linux, or `py -3 install.py --prefix "$env:LOCALAPPDATA\2brain-cli"` on Windows and add the resulting `bin` directory to PATH. You can also run `python3 2brain` directly, build a standalone archive with `python3 project build`, or install with `python3 -m pip install .`.

Default local data: `~/Library/Application Support/2brain` on macOS, `%LOCALAPPDATA%\2brain` on Windows, `$XDG_DATA_HOME/2brain` (or `~/.local/share/2brain`) on Linux. Override with `TWOBRAIN_HOME` or `--data <directory>` anywhere in the command. These locate the dataset, not project checkouts.

`remote` changes local Git configuration only. Create an empty repository on any Git host, or a bare repo on a machine you control, then attach it with `2brain remote <URL>`.

## Read only what you need

Terminal output uses quiet sage accents from the supplied 2brain brand board.
Colors appear automatically in interactive terminals; redirected text and `--json`
remain plain. Use `--color always` or `--color never` anywhere in a command to
override detection. `NO_COLOR` and `TERM=dumb` suppress automatic color.
Use `--theme light` for forest accents on a light terminal background; the default
theme uses sage accents for a dark background.

Browse local records with the read-only **OpenTUI** interface:

```sh
2brain tui
2brain tui --theme light
2brain --tool wstack tui
```

First launch installs pinned Bun and OpenTUI into a private cache; no separate
Node, npm, or Bun installation is needed. Downloads use TLS, a pinned SHA-512
checksum for Bun, and a frozen dependency lockfile. Later launches use the retained
runtime and work offline. Prepare and diagnose it separately with
`2brain tui --setup --json`. `TWOBRAIN_TUI_CACHE` can select another writable cache.

Update an existing installation on your computer from `stable`, then open the browser:

```sh
uv tool install --force --refresh "git+https://github.com/scwlkr/2brain.git@stable"
2brain tui --setup
2brain tui
```

Installing in a cloud checkout does not update the CLI on another computer.
See the [OpenTUI development instructions](src/twobrain/opentui/README.md).

Use arrows or `j`/`k` to browse, `/` to filter record names, Enter to read on narrow
terminals, Tab to change focus, Page Up/Down to scroll, `r` to refresh, and `q` to
quit. Mouse selection and scrolling are also supported. Escape clears a search
or returns from a record. OpenTUI owns layout, rendering, input, and terminal
cleanup. The browser never writes or syncs context. Linux PTY behavior is tested;
native macOS and Windows execution still require qualification on those systems.

The reusable [brand guide](src/twobrain/brand/index.html), SVG artwork, and compact
style source are included in both the package and standalone archive:

```sh
2brain brand
2brain brand --export ./2brain-brand
```

Export uses a new directory and preserves existing files. Open its `index.html`
in a browser for color roles, artwork previews/downloads, terminal examples, and
reusable style JSON. The saved vector board is an editable reconstruction of the
supplied preview; the original attachment was not accessible as a file. Its logo
geometry, lettering, and color values are interpreted rather than exact originals.

```sh
2brain
2brain --tool git
2brain --project owner/example-repo
2brain --project example-repo       # works if the repository name is unique
2brain --list
2brain --project owner/example-repo --json
```

Discovery lists names without opening other records. Default guidance allows at most six entries and 1,000 characters, plus four pointers. Tool reads return just that tool. Project reads include general guidance followed by the repository record; JSON explicitly gives precedence as current instructions → project → general. Free-text guidance remains instructions for the receiving agent, rather than executable policy. An ambiguous unqualified repository name requires `owner/repo`; no aliases or per-computer checkout mappings exist.

## Deliberate updates

Use the user's actual request or explicit lasting preference as the reason. Do not save inferred preferences, suggestions, experiments, or assistant-generated examples.

To edit an existing record in VS Code:

```sh
2brain edit --general
2brain edit --tool git
2brain edit --project owner/repo
2brain edit --general --reason "Prefer shorter responses"
```

VS Code's `code` command must be on PATH. The command opens a temporary JSON draft; save it and **close its tab** to finish. It validates the draft and commits locally with a default reason such as `edited general guidance`; `--reason` supplies your own history message. Unchanged records, including formatting-only edits, create no commit. Use `sync` separately to exchange changes with your remote.

Editing refuses to start when there are unsaved context changes. It checks again after VS Code closes and also refuses a stale draft if another commit appeared while editing. Existing work remains untouched. Invalid drafts, editor failures and interrupted edits are retained under the context repository's `.git/2brain-drafts/` directory; the error reports the exact draft path. Correct a retained draft and deliberately save it with `2brain put --general --file <draft-path> --reason "Your reason"` (or the matching tool/project selector), once other pending work is saved. A fresh `edit` always starts from the current record.

Create a UTF-8 file such as `git.json`:

```json
{
  "schema_version": 1,
  "guidance": ["A preference the user explicitly confirmed."],
  "pointers": [{"label": "Existing instructions", "target": "https://github.com/owner/repo"}]
}
```

```sh
2brain put --tool git --file git.json --reason "User asked to remember their Git preference"
2brain put --project owner/repo --file repo.json --reason "User confirmed this repository convention"
2brain put --general --file general.json --reason "User requested updated general guidance"
2brain remove --tool git --reason "User asked to forget this preference"
2brain history --tool git
2brain undo <commit-SHA> --reason "User asked to undo that update"
```

`put` creates or replaces exactly one record and commits locally. `--file -` reads JSON from stdin. A general record may also contain `"person": "Fixture User"`; leave unknown preferences unfilled. Inspect existing record JSON through `--json` (the record is under `general` or `context`). Records contain only `schema_version`, `guidance`, `pointers`, and optional general `person`.

You may instead edit the JSON files directly in the data directory, then run `2brain save --reason "User's decision"`. `status` shows that directory, revision, dirty state, and pending conflicts. Save existing manual edits before using `put`, `remove`, or `undo`. Invalid records are left intact with an actionable error. Updates never contact a network. `undo` adds a revert commit for an ordinary update; initial/merge commits require deliberately restoring chosen record contents with `put`.

Records live at `general.json`, `tools/<name>.json`, and `projects/<owner>/<repo>.json`. Names retain repository identity and must be portable filenames; case duplicates and Windows device names are rejected. Referenced tools, skills, and repositories stay where they already are. Pointers may name a CLI command, GitHub repository/file, skill, or authentication mechanism; the CLI never follows or downloads them.

## Sync and conflicts

```sh
2brain sync
2brain status --json
```

Sync validates and commits deliberate local file edits **before** networking, fetches the configured `origin`, merges the corresponding branch, validates the result, then pushes normally. It uses ordinary Git transport against that remote. Compatible changes merge; no force push, reset, stash, or preference inference. A rejected push (including a concurrent remote update) preserves local commits; retry sync to merge the newer remote. Network calls time out after 30 seconds; existing Git credential configuration is used without interactive prompts.

If a merge conflicts, exit code 3 names the affected files. Both committed versions remain in Git. Reads of a conflicted record show your pre-merge committed version and a warning (in JSON, `warnings`); other records remain usable. A record absent from your pre-merge copy reports that limitation. Once you save your resolution, reads show the resolved record.

Resolve the JSON markers in the named files, run `2brain save --reason "User's resolution"`, then `2brain sync`. Or run `2brain abort`: it backs up current JSON resolution work under `.git/2brain-recovery/`, then restores your committed local version; the fetched competing version remains in Git. Undo conflicts use Git's ordinary `revert --continue`/`revert --abort` flow as reported in the error.

Do not put unrelated files in the context repository. Sync/save refuse them. Local Git locks prevent competing 2brain writes; if a process is interrupted, the error gives the exact lock path. Verify that process is idle before removing a stale lock. Direct editor/Git operations must be coordinated separately. Reads never acquire a write lock or fetch.

## Agent startup and verification

Copy the short instruction in [AGENT-STARTUP.md](AGENT-STARTUP.md) into your terminal agent's instructions. Ordinary ChatGPT integration is outside this tool.

```sh
python3 project check
```

Local tests exercise selective concise reads, no-Git offline reads, JSON, explicit updates/reverts, editor subprocesses, draft validation/recovery, concurrent-edit protection, two-copy merges over a user-owned bare remote (no GitHub), conflicts, aborted-resolution recovery, failed fetch/push preservation, a standalone archive, and safe repeatable Codex setup. The bare-remote sync smoke is `test_sync_over_user_owned_bare_remote_without_github` in `tests/test_sync.py`. The runner also checks TypeScript and native OpenTUI behavior. Editor tests use a controlled child process; real VS Code interaction requires a native smoke check. No hosted CI is required. The current OpenTUI implementation is verified on Linux; native macOS and Windows execution remains unqualified.
