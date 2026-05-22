"""Build redistributable bundles for the i2e skills.

Produces two artifacts under ``dist/``:

1. ``dist/claude-plugin/`` — a complete Claude Code plugin marketplace repo,
   ready to push to GitHub. Layout::

       dist/claude-plugin/
       ├── .claude-plugin/marketplace.json
       ├── README.md
       ├── LICENSE
       └── plugins/i2e/
           ├── .claude-plugin/plugin.json
           ├── README.md
           └── skills/<16 skill folders>

   Users install with::

       /plugin marketplace add <user>/<repo>
       /plugin install i2e@i2e-skills

2. ``dist/agentskills/`` — a flat agentskills.io-format pack. One folder per
   skill plus a README explaining how to install each one in any
   skills-compatible agent (Cursor, Goose, OpenCode, Claude.ai, etc.).

Both bundles also get zipped to ``dist/i2e-claude-plugin.zip`` and
``dist/i2e-agentskills.zip`` for download-based distribution.

Single source of truth for skill content is ``.claude/skills/`` at the repo
root. Re-run this script after editing any SKILL.md or provider.py.
"""

from __future__ import annotations

import json
import re
import shutil
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_SRC = REPO_ROOT / ".claude" / "skills"
DIST = REPO_ROOT / "dist"
LICENSE_SRC = REPO_ROOT / "LICENSE"
PYPROJECT = REPO_ROOT / "pyproject.toml"


def _read_version() -> str:
    """Single source of truth: the [project] version in pyproject.toml."""
    text = PYPROJECT.read_text(encoding="utf-8")
    m = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if not m:
        raise SystemExit(f"could not find version in {PYPROJECT}")
    return m.group(1)


PLUGIN_VERSION = _read_version()
MARKETPLACE_NAME = "i2e-skills"
PLUGIN_NAME = "i2e"
GITHUB_REPO_PLACEHOLDER = "ryanturnercom/i2e"  # users override on publish


def _clean() -> None:
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir(parents=True)


def _copy_skill(src_dir: Path, dst_dir: Path) -> None:
    """Copy a single skill folder, excluding __pycache__ and other noise."""
    dst_dir.mkdir(parents=True, exist_ok=True)
    for child in src_dir.iterdir():
        if child.name == "__pycache__":
            continue
        if child.is_file():
            shutil.copy2(child, dst_dir / child.name)
        elif child.is_dir():
            shutil.copytree(child, dst_dir / child.name, dirs_exist_ok=True)


def _discover_skills() -> list[Path]:
    return sorted(p for p in SKILLS_SRC.iterdir() if p.is_dir())


def _write_plugin_manifest(plugin_dir: Path) -> None:
    manifest = {
        "name": PLUGIN_NAME,
        "description": (
            "Intent-to-Evidence (Simplified): a skills-driven SDLC where "
            "humans declare intent and an AI agent runs the IDEA loop "
            "(Intent → Develop → Evidence → Adapt)."
        ),
        "version": PLUGIN_VERSION,
        "author": {"name": "Ryan Turner", "email": "ryan@ryanturner.com"},
        "homepage": f"https://github.com/{GITHUB_REPO_PLACEHOLDER}",
        "repository": f"https://github.com/{GITHUB_REPO_PLACEHOLDER}",
        "license": "Apache-2.0",
        "keywords": ["sdlc", "agent", "evidence", "intent", "tdd", "workflow"],
    }
    (plugin_dir / ".claude-plugin").mkdir(parents=True, exist_ok=True)
    _write_json(plugin_dir / ".claude-plugin" / "plugin.json", manifest)


def _marketplace_catalog(source_path: str) -> dict:
    return {
        "$schema": "https://json.schemastore.org/claude-code-marketplace.json",
        "name": MARKETPLACE_NAME,
        "owner": {"name": "Ryan Turner", "email": "ryan@ryanturner.com"},
        "description": (
            "Intent-to-Evidence (Simplified) — the IDEA-loop SDLC as a "
            "single Claude Code plugin."
        ),
        "plugins": [
            {
                "name": PLUGIN_NAME,
                "source": source_path,
                "description": (
                    "16 skills: orchestrator + intent/develop/evidence/adapt "
                    "loop steps + 6 reference evidence providers."
                ),
                "version": PLUGIN_VERSION,
                "author": {"name": "Ryan Turner"},
                "license": "Apache-2.0",
                "category": "workflow",
                "keywords": ["sdlc", "agent", "evidence", "tdd"],
            }
        ],
    }


def _write_marketplace(market_root: Path) -> None:
    (market_root / ".claude-plugin").mkdir(parents=True, exist_ok=True)
    _write_json(
        market_root / ".claude-plugin" / "marketplace.json",
        _marketplace_catalog(f"./plugins/{PLUGIN_NAME}"),
    )


def _write_top_level_marketplace() -> None:
    """Also emit a marketplace.json at the project root so users can run
    `/plugin marketplace add ryanturnercom/i2e` against the source repo
    directly. The source path points into dist/ where the built plugin lives.
    """
    (REPO_ROOT / ".claude-plugin").mkdir(parents=True, exist_ok=True)
    _write_json(
        REPO_ROOT / ".claude-plugin" / "marketplace.json",
        _marketplace_catalog(f"./dist/claude-plugin/plugins/{PLUGIN_NAME}"),
    )


def _write_json(path: Path, data: dict) -> None:
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _write_text(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def _build_claude_plugin(skills: list[Path]) -> Path:
    market_root = DIST / "claude-plugin"
    plugin_dir = market_root / "plugins" / PLUGIN_NAME
    skills_dir = plugin_dir / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)

    for skill in skills:
        _copy_skill(skill, skills_dir / skill.name)

    _write_plugin_manifest(plugin_dir)
    _write_marketplace(market_root)

    shutil.copy2(LICENSE_SRC, market_root / "LICENSE")
    shutil.copy2(LICENSE_SRC, plugin_dir / "LICENSE")

    _write_text(market_root / "README.md", _marketplace_readme())
    _write_text(plugin_dir / "README.md", _plugin_readme())

    return market_root


def _build_agentskills(skills: list[Path]) -> Path:
    pack_root = DIST / "agentskills"
    pack_root.mkdir(parents=True, exist_ok=True)

    for skill in skills:
        _copy_skill(skill, pack_root / skill.name)

    shutil.copy2(LICENSE_SRC, pack_root / "LICENSE")
    _write_text(pack_root / "README.md", _agentskills_readme(skills))

    return pack_root


def _zip_dir(src: Path, archive: Path) -> None:
    if archive.exists():
        archive.unlink()
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in src.rglob("*"):
            if f.is_file():
                zf.write(f, arcname=str(f.relative_to(src.parent)))


def _marketplace_readme() -> str:
    return f"""# i2e — Claude Code marketplace

This repository is a Claude Code **plugin marketplace** that distributes the
[Intent-to-Evidence (Simplified)](https://github.com/{GITHUB_REPO_PLACEHOLDER})
SDLC as a single plugin.

## Install

```
/plugin marketplace add {GITHUB_REPO_PLACEHOLDER}
/plugin install {PLUGIN_NAME}@{MARKETPLACE_NAME}
```

Skills are namespaced as `/{PLUGIN_NAME}:<skill-name>` — e.g. `/{PLUGIN_NAME}:i2e`,
`/{PLUGIN_NAME}:i2e-intent`.

## Prerequisites

The skills are thin wrappers around the `i2e_core` Python package. Install it
first:

```bash
pip install "i2e-core @ git+https://github.com/{GITHUB_REPO_PLACEHOLDER}@main"
```

Or, from a local checkout of the source repo:

```bash
pip install -e ".[dev]"
```

## Contents

A single plugin (`{PLUGIN_NAME}`) with 16 skills:

- **Loop skills** — `i2e`, `i2e-intent`, `i2e-spec`, `i2e-develop`,
  `i2e-evidence`, `i2e-adapt`, `i2e-report`, `i2e-serve`,
  `i2e-regression`, `i2e-watch`
- **Reference providers** — `i2e-provider-pytest`, `i2e-provider-human`,
  `i2e-provider-ga`, `i2e-provider-datadog`, `i2e-provider-sentry`,
  `i2e-provider-survey`

## License

Apache-2.0 — see [LICENSE](./LICENSE).
"""


def _plugin_readme() -> str:
    return f"""# i2e plugin

A Claude Code plugin that ships the Intent-to-Evidence (Simplified) SDLC as
16 model-invoked skills.

## What it does

The `{PLUGIN_NAME}` skill is the orchestrator. On each tick it runs preflight,
walks a 5-branch decision tree, and dispatches to one of the loop skills
(`i2e-intent`, `i2e-develop`, `i2e-evidence`, `i2e-adapt`) or escalates a
non-passing item to a human via a `pending/` file. Provider skills
(`i2e-provider-*`) collect evidence — pytest for cases, GA4/Datadog/Sentry
for targets, human/survey for subjective verdicts.

## Prerequisites

The provider skills `import i2e_core`. Install the Python package first:

```bash
pip install "i2e-core @ git+https://github.com/{GITHUB_REPO_PLACEHOLDER}@main"
```

For GA4 support, add the optional `ga` extra (`i2e-core[ga]`).

## Usage

After installation, invoke the orchestrator from any project that has a
`.i2e/` directory:

```
/{PLUGIN_NAME}:{PLUGIN_NAME}
```

To author a new capability intent:

```
/{PLUGIN_NAME}:i2e-intent
```

See the [project README](https://github.com/{GITHUB_REPO_PLACEHOLDER}) for the
full IDEA-loop spec.

## License

Apache-2.0
"""


def _agentskills_readme(skills: list[Path]) -> str:
    skill_list = "\n".join(f"- `{p.name}` — see `{p.name}/SKILL.md`" for p in skills)
    return f"""# i2e — agent skills pack

This is an [agentskills.io](https://agentskills.io)-format collection of the
Intent-to-Evidence (Simplified) SDLC skills. It is consumable by any
skills-compatible agent: Claude (Claude Code, Claude.ai), Cursor, Goose,
OpenCode, OpenHands, Codex, and others. See
[agentskills.io/clients](https://agentskills.io/clients) for the full list.

## Skills

{skill_list}

## Install

The way you install agent skills varies by client. A few examples:

- **Claude Code** — copy the skill folder into your project's `.claude/skills/`
  or your user-level `~/.claude/skills/`. Or use the
  [Claude Code plugin bundle](https://github.com/{GITHUB_REPO_PLACEHOLDER})
  instead for namespaced installation.
- **Claude.ai** — upload via Settings → Skills.
- **Cursor / Goose / OpenCode** — see each client's docs at
  [agentskills.io/clients](https://agentskills.io/clients).

Each skill folder is self-contained and conforms to the agentskills.io spec
(`SKILL.md` with YAML frontmatter + Markdown body).

## Prerequisites

The provider skills (`i2e-provider-*`) execute Python (`provider.py`) that
imports `i2e_core`. Install the Python package first:

```bash
pip install "i2e-core @ git+https://github.com/{GITHUB_REPO_PLACEHOLDER}@main"
```

The non-provider skills (the IDEA loop) call into `i2e_core` via the agent;
they too require the package on `PYTHONPATH`.

## License

Apache-2.0 — see [LICENSE](./LICENSE).
"""


def _root_readme() -> str:
    return """# dist/ — generated bundles

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
"""


def main() -> None:
    _clean()
    skills = _discover_skills()
    if not skills:
        raise SystemExit(f"no skills found under {SKILLS_SRC}")

    plugin_root = _build_claude_plugin(skills)
    pack_root = _build_agentskills(skills)
    _write_top_level_marketplace()
    _write_text(DIST / "README.md", _root_readme())

    _zip_dir(plugin_root, DIST / "i2e-claude-plugin.zip")
    _zip_dir(pack_root, DIST / "i2e-agentskills.zip")

    print(f"built {len(skills)} skills")
    print(f"  -> {plugin_root.relative_to(REPO_ROOT)}")
    print(f"  -> {pack_root.relative_to(REPO_ROOT)}")
    print(f"  -> dist/i2e-claude-plugin.zip")
    print(f"  -> dist/i2e-agentskills.zip")


if __name__ == "__main__":
    main()
