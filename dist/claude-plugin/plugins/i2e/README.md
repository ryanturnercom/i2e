# i2e plugin

A Claude Code plugin that ships the Intent-to-Evidence (Simplified) SDLC as
16 model-invoked skills.

## What it does

The `i2e` skill is the orchestrator. On each tick it runs preflight,
walks a 5-branch decision tree, and dispatches to one of the loop skills
(`i2e-intent`, `i2e-develop`, `i2e-evidence`, `i2e-adapt`) or escalates a
non-passing item to a human via a `pending/` file. Provider skills
(`i2e-provider-*`) collect evidence — pytest for cases, GA4/Datadog/Sentry
for targets, human/survey for subjective verdicts.

## Prerequisites

The provider skills `import i2e_core`. Install the Python package first:

```bash
pip install "i2e-core @ git+https://github.com/ryanturnercom/i2e@main"
```

For GA4 support, add the optional `ga` extra (`i2e-core[ga]`).

## Usage

After installation, invoke the orchestrator from any project that has a
`.i2e/` directory:

```
/i2e:i2e
```

To author a new capability intent:

```
/i2e:i2e-intent
```

See the [project README](https://github.com/ryanturnercom/i2e) for the
full IDEA-loop spec.

## License

Apache-2.0
