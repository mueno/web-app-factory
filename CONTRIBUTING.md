# Contributing to web-app-factory

## Development Setup

```bash
git clone <repo-url>
cd web-app-factory
pip install -e ".[dev]"
```

## Running Tests

```bash
pytest                    # all tests
pytest tests/test_foo.py  # single file
pytest -x -q              # stop on first failure, quiet output
```

## Code Style

This project uses [ruff](https://docs.astral.sh/ruff/) for linting and formatting:

```bash
ruff check .       # lint
ruff format .      # format
```

## Commit Messages

Follow conventional commits:
- `fix:` bug fixes
- `feat:` new features
- `docs:` documentation changes
- `test:` test additions/changes
- `refactor:` code restructuring

## Pull Requests

1. Fork the repo and create a feature branch
2. Write tests for new functionality
3. Ensure all tests pass (`pytest`)
4. Ensure linting passes (`ruff check .`)
5. Submit a PR with a clear description

## Architecture

See README.md for pipeline architecture overview. Key directories:

| Directory | Purpose |
|-----------|---------|
| `agents/` | Agent system prompts and definitions |
| `config/` | Runtime settings |
| `contracts/` | Pipeline contract YAML (phases, gates, quality criteria) |
| `pipeline_runtime/` | Orchestration, governance, error routing |
| `tools/gates/` | Quality gate implementations |
| `tools/phase_executors/` | Phase execution logic |
| `tests/` | Test suite |
