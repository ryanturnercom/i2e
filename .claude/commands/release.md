---
description: Bump the project version, rebuild bundles, commit, tag, and push.
argument-hint: "[patch|minor|major]  (default: patch)"
---

Release the i2e project. Bump the version in `pyproject.toml` (single source
of truth), rebuild `dist/`, commit, tag, and push to `origin/main`.

## Bump type

Parse `$ARGUMENTS`:
- empty or `patch` → bump the patch component (Z)
- `minor` → bump Y, reset Z to 0
- `major` → bump X, reset Y and Z to 0
- anything else → stop and report the invalid argument

## Steps

1. Read the current version from `pyproject.toml` — the `version = "X.Y.Z"`
   line under `[project]`. Compute `NEW_VERSION` from the bump type.

2. Snapshot the working tree state (`git status --short`). Any uncommitted
   or untracked files will be folded into the release commit at step 6 —
   the release command commits everything. Briefly report what will be
   swept in so the user knows what's about to ship.

3. Edit `pyproject.toml`: replace the existing `version = "..."` under
   `[project]` with `version = "NEW_VERSION"`. Do NOT touch
   `packaging/build_bundles.py` — it reads the version from pyproject.toml
   at build time.

4. Rebuild bundles: run `./tasks.ps1 bundle`. Confirm output reports
   "built 13 skills" and lists `dist/claude-plugin`, `dist/agentskills`,
   and the two zips.

5. Spot-check the rebuild bumped the version. Read at minimum:
   - `dist/claude-plugin/plugins/i2e/.claude-plugin/plugin.json`
   - `dist/claude-plugin/.claude-plugin/marketplace.json`
   - `.claude-plugin/marketplace.json`

   All three should show `NEW_VERSION`. If any still shows the old version,
   stop and investigate.

6. Stage all changes (including any pre-existing modifications and untracked
   files from step 2): `git add -A`. Then commit:

   ```
   git commit -m "release: vNEW_VERSION"
   ```

   Use a heredoc-style message with the Co-Authored-By trailer per project
   convention. If a pre-commit hook fails, fix the underlying issue and
   create a NEW commit — never use `--amend` or `--no-verify`.

   Note: this is intentionally a single bundled commit. The release sweeps
   in whatever is dirty at the time it runs.

7. Tag the commit: `git tag vNEW_VERSION`.

8. Push the commit and the tag in one step:

   ```
   git push origin main --follow-tags
   ```

9. Report:
   - the old → new version
   - the commit SHA (`git rev-parse --short HEAD`)
   - the tag name
   - a link to the GitHub release page:
     `https://github.com/ryanturnercom/i2e/releases/new?tag=vNEW_VERSION`
     (the user can attach the zips from `dist/` manually if they want a
     GitHub Release with downloadable assets)

## Boundaries

- Only modify `pyproject.toml` for the version bump. The rest of `dist/`
  changes come from the build script.
- Do not push to anything other than `origin/main`.
- Do not skip hooks (`--no-verify` is forbidden).
- Do not force-push.
