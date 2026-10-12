# Releasing 2brain

Version tags select a particular release. `stable` points to the latest published release, so users can install it once and use `uv tool upgrade twobrain-cli` thereafter. Advance `stable` only after publishing a release; ordinary changes to `main` do not update it. Never move an existing version tag.

1. Update the version in `pyproject.toml`, `src/twobrain/__init__.py`, the installer version assertion in `tests/test_reads_updates.py`, and the pinned example in `README.md`. Commit and review the changes through the normal PR flow.
2. Run `python3 project check` on the clean candidate before pushing. After merging, fetch and fast-forward `main`, confirm the merged changes, and run the same check on the clean landed commit. Keep the output as local release evidence; hosted CI is not required.
3. Build the wheel and standalone archive from that landed commit. Substitute the new version in all commands below:

   ```sh
   uv build --wheel --out-dir dist
   python3 project build --output dist/2brain-v0.1.2.pyz
   git tag -a v0.1.2 -m "2brain v0.1.2"
   git push origin refs/tags/v0.1.2
   ```

4. With existing GitHub authentication, create a draft release for the tag and attach the wheel and archive. Describe behavior changes, validation, and any native-platform qualification limits in its notes. Verify both assets and the tag's target before publishing.
5. Publish the release, then fast-forward `stable` to the same commit:

   ```sh
   gh release edit v0.1.2 --repo scwlkr/2brain --draft=false
   git push origin HEAD:refs/heads/stable
   ```

   The push creates `stable` for its first release. Later pushes must fast-forward; stop and inspect if rejected. Do not force-push it.

6. In an isolated uv tool environment, install from `@stable`, check `2brain --version` and `2brain edit --help`, and run `uv tool upgrade twobrain-cli`. Confirm the installed source commit matches the tag and `stable`. Also verify installing the explicit version tag. Installing/upgrading the CLI must leave personalization untouched.

Users who prefer a fixed version can install its tag. Rollback uses `uv tool install --force "git+https://github.com/scwlkr/2brain@v0.1.1"`; personalization remains in the separate context repository. Do not rewrite tags or shared history to roll back a user's installation.
