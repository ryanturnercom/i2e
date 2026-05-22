# i2e — agent skills pack

This is an [agentskills.io](https://agentskills.io)-format collection of the
Intent-to-Evidence (Simplified) SDLC skills. It is consumable by any
skills-compatible agent: Claude (Claude Code, Claude.ai), Cursor, Goose,
OpenCode, OpenHands, Codex, and others. See
[agentskills.io/clients](https://agentskills.io/clients) for the full list.

## Skills

- `i2e` — see `i2e/SKILL.md`
- `i2e-adapt` — see `i2e-adapt/SKILL.md`
- `i2e-develop` — see `i2e-develop/SKILL.md`
- `i2e-evidence` — see `i2e-evidence/SKILL.md`
- `i2e-intent` — see `i2e-intent/SKILL.md`
- `i2e-provider-datadog` — see `i2e-provider-datadog/SKILL.md`
- `i2e-provider-ga` — see `i2e-provider-ga/SKILL.md`
- `i2e-provider-human` — see `i2e-provider-human/SKILL.md`
- `i2e-provider-pytest` — see `i2e-provider-pytest/SKILL.md`
- `i2e-provider-sentry` — see `i2e-provider-sentry/SKILL.md`
- `i2e-provider-survey` — see `i2e-provider-survey/SKILL.md`
- `i2e-regression` — see `i2e-regression/SKILL.md`
- `i2e-report` — see `i2e-report/SKILL.md`
- `i2e-serve` — see `i2e-serve/SKILL.md`
- `i2e-spec` — see `i2e-spec/SKILL.md`
- `i2e-watch` — see `i2e-watch/SKILL.md`

## Install

The way you install agent skills varies by client. A few examples:

- **Claude Code** — copy the skill folder into your project's `.claude/skills/`
  or your user-level `~/.claude/skills/`. Or use the
  [Claude Code plugin bundle](https://github.com/ryanturnercom/i2e)
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
pip install "i2e-core @ git+https://github.com/ryanturnercom/i2e@main"
```

The non-provider skills (the IDEA loop) call into `i2e_core` via the agent;
they too require the package on `PYTHONPATH`.

## License

Apache-2.0 — see [LICENSE](./LICENSE).
