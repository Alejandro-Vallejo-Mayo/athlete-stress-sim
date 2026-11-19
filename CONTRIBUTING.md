# Contributing

Thanks for your interest in Athlete Stress Sim. This is a personal, single-user
project, but focused issues and pull requests are welcome.

## Scope

The project is designed around one athlete, one Polar account and a local
deployment. Contributions that improve correctness, documentation, tests or the
reproducibility of the existing scope are the easiest to review. Multi-user
support, new device integrations and clinical claims are outside the current
scope.

## Development setup

Prerequisites: Python 3.12, [`uv`](https://docs.astral.sh/uv/) and, optionally,
Docker.

```bash
git clone git@github.com:Alejandro-Vallejo-Mayo/athlete-stress-sim.git
cd athlete-stress-sim
make install
cp .env.example .env
```

Fill in the Polar credentials in `.env` only if you need live ingestion. Tests
do not require network access, real Polar data or a populated database.

## Definition of done

Every change must pass the same gates as CI, in this order:

```bash
make lint
make typecheck
make test-cov
```

`make test-cov` enforces 80 % branch coverage over `src/athlete_stress_sim/core`.
Backend and frontend are exercised by tests but are outside that coverage gate.

## Code conventions

- Python 3.12, `src` layout, `from __future__ import annotations` in every module.
- PEP 257 docstrings with Google-style `Args`, `Returns` and `Raises` sections.
- `ruff` for linting and formatting; `mypy --strict` over `src`.
- Prefer small, testable functions and keep `core/metrics` and `core/models`
  independent of DuckDB and FastAPI.
- Add dependencies to `pyproject.toml`, then run `uv lock` and `uv sync`.
  Do not use `pip` or `requirements.txt`.

## Tests

- Use `pytest`.
- Generate FIT fixtures with `tests/helpers/fit_fixture.py`; never commit real
  biometric data.
- Use `tmp_path` for DuckDB databases and inject `httpx2.MockTransport` instead
  of patching network calls.
- Keep `tests/conftest.py` forcing `POLAR_SYNC_ON_STARTUP=false` for tests that
  import `backend.main`.

## Documentation

- Public documentation lives under `docs/` and is written in English.
- [`docs/mathematical-model.md`](docs/mathematical-model.md) is the canonical
  source for equations and references. The README and user guide summarize it.
- Update the relevant document when behavior, configuration or commands change.
- Do not commit `.env`, OAuth tokens, raw FIT files, the DuckDB database or
  unsanitized biometric screenshots.

## Commit and pull-request style

- Use Conventional Commits, for example `feat:`, `fix:`, `refactor:`, `docs:` or
  `test:`.
- Keep each pull request focused and explain the motivation and validation.
- Open an issue before a large change so the scope can be discussed first.
- Include tests and documentation updates with the code change.
