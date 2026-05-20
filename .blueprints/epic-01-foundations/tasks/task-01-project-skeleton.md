# Task: Project skeleton + pyproject + repo layout

**Status:** [✓] Completed
**Started:** 2026-05-19
**Completed:** 2026-05-19

**Dependencies:** None

## Context

Bootstrap the repo. After this task, the project root has the directory layout from spec §3, a `pyproject.toml` for the `i2e_core` package, a `.gitignore`, and a top-level README.

- Language: Python 3.11+
- Framework: stdlib + pyyaml, pydantic v2, jinja2, watchdog (deps added incrementally per epic)
- Testing: pytest
- Database: filesystem (YAML + Markdown under `.i2e/`)

## Needed from User

None.

## Instructions

1. Create the directory tree at the project root (`D:\_Brain\1 - Projects\sdlc\intent-based_simplified\`):
   ```
   src/i2e_core/__init__.py
   tests/__init__.py
   .i2e/context/.gitkeep
   .i2e/intents/.gitkeep
   .i2e/evidence/.gitkeep
   .i2e/pending/.gitkeep
   .i2e/logs/.gitkeep
   ```
2. Write `pyproject.toml` declaring:
   - `[project]` name `i2e_core`, version `0.1.0`, requires-python `>=3.11`
   - dependencies: `pydantic>=2`, `PyYAML>=6`, `python-frontmatter>=1.1`, `jinja2>=3`, `watchdog>=4`
   - `[project.optional-dependencies] dev = ["pytest>=8", "pytest-cov"]`
   - `[tool.setuptools.packages.find] where = ["src"]`
   - `[tool.pytest.ini_options] testpaths = ["tests"]`
3. Write `.gitignore` covering: `__pycache__/`, `*.pyc`, `.venv/`, `.pytest_cache/`, `.i2e/.serve.url`, `dist/`, `*.egg-info/`
4. Write `README.md` with a one-paragraph summary linking to `.documentation/I2E_simplified.md` as the source spec and listing the 6 loop skills + 2 reference providers
5. Write `src/i2e_core/__init__.py` exposing `__version__ = "0.1.0"`

## Acceptance Criteria

- [✓] All directories exist with `.gitkeep` placeholders where empty
- [✓] `pyproject.toml` is valid TOML (`python -c "import tomllib; tomllib.load(open('pyproject.toml','rb'))"` succeeds)
- [✓] `pip install -e .[dev]` from project root succeeds in a fresh venv
- [✓] `python -c "import i2e_core; print(i2e_core.__version__)"` prints `0.1.0`
- [✓] `pytest` runs (collects zero tests at this stage, exit 5 is OK)

## Implementation Notes

- Created the directory tree under `src/i2e_core/`, `tests/`, and `.i2e/{context,intents,evidence,pending,logs}` with `.gitkeep` placeholders.
- `pyproject.toml` uses setuptools backend with `packages.find` rooted at `src/`. Added optional `dev` extras (pytest, pytest-cov) and a `tool.coverage.run` block.
- `.gitignore` covers Python build/runtime junk plus `.i2e/.serve.url`.
- Added a top-level `tasks.ps1` runner (Windows-first) with `install`, `test`, `cov` targets and documented it in the README.
