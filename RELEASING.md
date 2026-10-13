# Releasing 2brain

Version tags select a particular release. Git branch `stable` and npm dist-tag `stable` point at the latest published release. Ordinary changes on `main` do not move either stable channel. They do feed npm dist-tag `dev`. Never move an existing version tag. Never force-push `main` or `stable`.

## Channels

| Channel | Install | Source | npm dist-tag |
|---------|---------|--------|--------------|
| stable | `npm install -g @scwlkr/2brain@stable` or `uv tool install "git+https://github.com/scwlkr/2brain.git@stable"` | published release commit | `stable` |
| dev | `npm install -g @scwlkr/2brain@dev` | `main` | `dev` |

`@scwlkr/2brain` embeds the Python package `twobrain-cli` and exposes bin `2brain`. The npm tarball includes only the CLI payload listed in `package.json` `files`. It must not include personalization records or test fixtures.

## Release steps

1. Update the version in `pyproject.toml`, `src/twobrain/__init__.py`, `package.json`, the installer version assertion in `tests/test_reads_updates.py`, and the pinned example in `README.md`. Commit and review through the normal PR flow.
2. Run `python3 project check` on the clean candidate before pushing. After merging, fetch and fast-forward `main`, confirm the merged changes, and run the same check on the clean landed commit. Keep the output as local release evidence. The check runs `scripts/verify-npm-pack.mjs` when Node is on PATH.
3. Build the wheel and standalone archive from that landed commit. Substitute the new version in all commands below:

   ```sh
   uv build --wheel --out-dir dist
   python3 project build --output dist/2brain-v0.1.3.pyz
   git tag -a v0.1.3 -m "2brain v0.1.3"
   git push origin refs/tags/v0.1.3
   ```

4. With existing GitHub authentication, create a draft release for the tag and attach the wheel and archive. Describe behavior changes, validation, and any native-platform qualification limits in its notes. Verify both assets and the tag's target before publishing.
5. Publish the release, then fast-forward `stable` to the same commit:

   ```sh
   gh release edit v0.1.3 --repo scwlkr/2brain --draft=false
   git push origin HEAD:refs/heads/stable
   ```

   The push creates `stable` for its first release. Later pushes must fast-forward; stop and inspect if rejected. Do not force-push it.

6. Smoke both install paths. For npm: `npm install -g @scwlkr/2brain@stable`, then `2brain --version` and `2brain edit --help`. For uv: install from `@stable`, check the same commands, and run `uv tool upgrade twobrain-cli`. Confirm the installed source matches the tag and `stable`. Installing or upgrading the CLI must leave personalization untouched.

Users who prefer a fixed git version can install its tag. Rollback uses `uv tool install --force "git+https://github.com/scwlkr/2brain@v0.1.1"` or `npm install -g @scwlkr/2brain@<older-version>`. Personalization remains in the user's local data directory and optional remote. Do not rewrite tags or shared history to roll back a user's installation.

## npm publish automation

Workflows under `.github/workflows/`:

- `npm-publish-dev.yml` runs on pushes to `main`. It sets version to `<pyproject>-dev.<shortsha>` and runs `npm publish --tag dev` when `NPM_TOKEN` is present.
- `npm-publish-stable.yml` runs on pushes to `stable`. It aligns `package.json` to the `pyproject.toml` version and runs `npm publish --tag stable` when `NPM_TOKEN` is present.

Required repository secret: `NPM_TOKEN` with publish rights for the `@scwlkr` npm user scope (package `@scwlkr/2brain`, `publishConfig.access=public`). Without that secret the workflows exit successfully without publishing. Publish under the `scwlkr` npm account. Do not create a `@2brain` org for this package.

Local dry run without publishing:

```sh
node scripts/verify-npm-pack.mjs
```
