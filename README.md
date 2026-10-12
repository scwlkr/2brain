# 2brain

Small, portable personalization for terminal agents. `2brain` reads a short introduction; tool and repository details load only when requested. Your current instructions always take precedence.

Python 3.10+ and Git 2.28+; no runtime packages, model, database, or server. Python's standard library keeps the same implementation usable on macOS, Windows and Linux. Separate UTF-8 JSON records are readable, validate before saving, and merge through Git. Git is only required for writes/history/sync; ordinary reads use local files directly.

## Setup

The CLI and personalization live in **separate repositories**:

- Source: `scwlkr/2brain` (private).
- Shane's context: `scwlkr/2brain-context` (private).

Use your existing Git/GitHub authentication. No credentials belong in records or remote URLs.

With [uv](https://docs.astral.sh/uv/guides/tools/) installed, setup is two commands on macOS, Windows or Linux:

```sh
uv tool install "git+https://github.com/scwlkr/2brain@v0.1.1"
2brain setup scwlkr/2brain-context --codex
```

The package manager installs the CLI in its own environment and creates the platform launcher. It can acquire a compatible Python interpreter when needed. Git and access to the two private repositories are still required; your existing Git credential helper handles authentication. No token belongs in either command.

If uv reports its executable directory is missing from PATH, run `uv tool update-shell` once and reopen the terminal. On Windows, install uv through your normal package manager (for example `winget install --id astral-sh.uv --exact`) if it is not already available. Restart Codex after setup so it sees the launcher and new instructions.

`setup owner/repo` accepts an actual GitHub repository name or a full Git URL. It clones context when absent and otherwise preserves the existing local copy, including manual edits. It refuses a different remote rather than silently switching datasets. To reuse your current context, run `2brain setup --codex`.

`--codex` explicitly replaces global Codex personalization with only the short 2brain loader. It saves exact previous `AGENTS.md` and `AGENTS.override.md` bytes under the Codex home's inactive `2brain-backups/` directory, then removes the active override so the loader is used. It honors `CODEX_HOME`. Repeating setup makes no extra backup when the loader is already installed. Without `--codex`, agent instructions are untouched. Failed context initialization leaves agent instructions untouched.

Installation is a normal package install; it never clones personalization or edits agent instructions as an install hook. Personalization stays in its separate private repository and local data copy. The versioned Git URL selects the release deliberately; use the full commit SHA in place of `v0.1.1` when you require an immutable source pin. Git credential-helper behavior is documented by [uv](https://docs.astral.sh/uv/concepts/authentication/git/).

To uninstall the CLI: `uv tool uninstall twobrain-cli`. Your context/history and Codex instruction backups remain available. For a release upgrade, install that release's versioned Git URL. Context changes use `2brain sync` separately.

Advanced source installation remains available: run `python3 install.py --prefix ~/.local` from a clone on macOS/Linux, or `py -3 install.py --prefix "$env:LOCALAPPDATA\2brain-cli"` on Windows and add the resulting `bin` directory to PATH. You can also run `python3 2brain` directly, build a standalone archive with `python3 project build`, or install with `python3 -m pip install .`.

Default local data: `~/Library/Application Support/2brain` on macOS, `%LOCALAPPDATA%\2brain` on Windows, `$XDG_DATA_HOME/2brain` (or `~/.local/share/2brain`) on Linux. Override with `TWOBRAIN_HOME` or `--data <directory>` anywhere in the command. These locate the dataset, not project checkouts.

For an offline start, `2brain init` creates empty context; `2brain init --seed <record-directory>` copies supplied records without networking. Existing directories are never replaced. Git needs your existing `user.name`/`user.email` configuration for commits. Failed initialization retains partial work at the path reported in its error.

To use your own private remote, create an **empty private repository**, then `2brain remote <URL>` and `2brain sync`. `remote` changes local Git configuration only. On additional computers, clone it with `init --remote`. The CLI supports normal Git transports; privacy is set on GitHub when you create the repository, not enforced by local reads.

## Read only what you need

```sh
2brain
2brain --tool git
2brain --project scwlkr/wstack
2brain --project wstack       # works if the repository name is unique
2brain --list
2brain --project scwlkr/wstack --json
```

Discovery lists names without opening other records. Default guidance allows at most six entries and 1,000 characters, plus four pointers. Tool reads return just that tool. Project reads include general guidance followed by the repository record; JSON explicitly gives precedence as current instructions → project → general. Free-text guidance remains instructions for the receiving agent, rather than executable policy. An ambiguous unqualified repository name requires `owner/repo`; no aliases or per-computer checkout mappings exist.

## Deliberate updates

Use the user's actual request or explicit lasting preference as the reason. Do not save inferred preferences, suggestions, experiments, or assistant-generated examples.

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

`put` creates or replaces exactly one record and commits locally. `--file -` reads JSON from stdin. A general record may also contain `"person": "Shane Walker"`; leave unknown preferences unfilled. Inspect existing record JSON through `--json` (the record is under `general` or `context`). Records contain only `schema_version`, `guidance`, `pointers`, and optional general `person`.

You may instead edit the JSON files directly in the data directory, then run `2brain save --reason "User's decision"`. `status` shows that directory, revision, dirty state, and pending conflicts. Save existing manual edits before using `put`, `remove`, or `undo`. Invalid records are left intact with an actionable error. Updates never contact a network. `undo` adds a revert commit for an ordinary update; initial/merge commits require deliberately restoring chosen record contents with `put`.

Records live at `general.json`, `tools/<name>.json`, and `projects/<owner>/<repo>.json`. Names retain repository identity and must be portable filenames; case duplicates and Windows device names are rejected. Referenced tools, skills, and repositories stay where they already are. Pointers may name a CLI command, GitHub repository/file, skill, or authentication mechanism; the CLI never follows or downloads them.

## Sync and conflicts

```sh
2brain sync
2brain status --json
```

Sync validates and commits deliberate local file edits **before** networking, fetches origin, merges the corresponding branch, validates the result, then pushes normally. Compatible changes merge; no force push, reset, stash, or preference inference. A rejected push (including a concurrent remote update) preserves local commits; retry sync to merge the newer remote. Network calls time out after 30 seconds; existing Git credential configuration is used without interactive prompts.

If a merge conflicts, exit code 3 names the affected files. Both committed versions remain in Git. Reads of a conflicted record show your pre-merge committed version and a warning (in JSON, `warnings`); other records remain usable. A record absent from your pre-merge copy reports that limitation. Once you save your resolution, reads show the resolved record.

Resolve the JSON markers in the named files, run `2brain save --reason "User's resolution"`, then `2brain sync`. Or run `2brain abort`: it backs up current JSON resolution work under `.git/2brain-recovery/`, then restores your committed local version; the fetched competing version remains in Git. Undo conflicts use Git's ordinary `revert --continue`/`revert --abort` flow as reported in the error.

Do not put unrelated files in the context repository. Sync/save refuse them. Local Git locks prevent competing 2brain writes; if a process is interrupted, the error gives the exact lock path. Verify that process is idle before removing a stale lock. Direct editor/Git operations must be coordinated separately. Reads never acquire a write lock or fetch.

## Agent startup and verification

Copy the short instruction in [AGENT-STARTUP.md](AGENT-STARTUP.md) into your terminal agent's instructions. Ordinary ChatGPT integration is outside this tool.

```sh
python3 project check
```

Local tests exercise selective concise reads, no-Git offline reads, JSON, explicit updates/reverts, two-copy merges, conflicts, aborted-resolution recovery, failed fetch/push preservation, a standalone archive, and safe repeatable Codex setup. No hosted CI is required. Native Windows/Linux execution must be verified on those systems; macOS checks do not claim it.
