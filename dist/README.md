# dist/ — generated bundles

This directory is built by `python packaging/build_bundles.py`. It is
gitignored in the source repo. Do not edit by hand — edit `.claude/skills/`
and re-run the build.

## Outputs

- `claude-plugin/` — a Claude Code marketplace repo. Push its contents to a
  dedicated GitHub repo (e.g. `i2e-skills`) so users can run
  `/plugin marketplace add <user>/i2e-skills`. See
  [claude-plugin/README.md](./claude-plugin/README.md).
- `agentskills/` — a flat agentskills.io-format pack for any
  skills-compatible agent (Cursor, Goose, OpenCode, etc.). See
  [agentskills/README.md](./agentskills/README.md).
- `i2e-claude-plugin.zip`, `i2e-agentskills.zip` — zipped equivalents.
  Attach these to a GitHub release for download-based distribution.

## Publishing flow

```powershell
# rebuild
python packaging/build_bundles.py

# push the marketplace
cd dist/claude-plugin
git init; git add -A; git commit -m "release v0.1.0"
git remote add origin git@github.com:<you>/i2e-skills.git
git push -u origin main

# attach zips to a release
gh release create v0.1.0 ../i2e-claude-plugin.zip ../i2e-agentskills.zip
```
