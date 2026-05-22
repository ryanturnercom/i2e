# i2e — Claude Code marketplace

This repository is a Claude Code **plugin marketplace** that distributes the
[Intent-to-Evidence (Simplified)](https://github.com/ryanturnercom/i2e)
SDLC as a single plugin.

## Install

```
/plugin marketplace add ryanturnercom/i2e
/plugin install i2e@i2e-skills
```

Skills are namespaced as `/i2e:<skill-name>` — e.g. `/i2e:i2e`,
`/i2e:i2e-intent`.

## Prerequisites

The skills are thin wrappers around the `i2e_core` Python package. Install it
first:

```bash
pip install "i2e-core @ git+https://github.com/ryanturnercom/i2e@main"
```

Or, from a local checkout of the source repo:

```bash
pip install -e ".[dev]"
```

## Contents

A single plugin (`i2e`) with 16 skills:

- **Loop skills** — `i2e`, `i2e-intent`, `i2e-spec`, `i2e-develop`,
  `i2e-evidence`, `i2e-adapt`, `i2e-report`, `i2e-serve`,
  `i2e-regression`, `i2e-watch`
- **Reference providers** — `i2e-provider-pytest`, `i2e-provider-human`,
  `i2e-provider-ga`, `i2e-provider-datadog`, `i2e-provider-sentry`,
  `i2e-provider-survey`

## License

Apache-2.0 — see [LICENSE](./LICENSE).
