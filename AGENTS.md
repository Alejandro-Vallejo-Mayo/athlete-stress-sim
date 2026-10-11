# AGENTS.md

Personal endurance/hybrid training platform: Polar AccessLink ingest -> local DuckDB ->
TRIMP/ACWR/Banister/EKF metrics -> FastAPI + Dash. Single Python package (*src layout*),
Python 3.12.

## Commands (always go through `uv` + the Makefile)

- `make install` — `uv sync --all-groups` + install pre-commit hooks.
- `make format` / `make lint` / `make typecheck` / `make test` / `make test-cov`.
- Single test: `uv run pytest tests/test_trimp.py::test_name`.
- Run backend `make run-backend` (:8000, uvicorn `--reload`), frontend `make run-frontend` (:8050).
- Docker: `make docker-up` / `make docker-logs` / `make docker-down`.
- Definition of done = `make lint && make typecheck && make test` (exactly what CI runs, in that order).

## Toolchain quirks

- Never use `pip`/`requirements.txt`. Add deps to `pyproject.toml`, then `uv lock` + `uv sync`;
  Docker builds with `uv sync --frozen`, so commit `uv.lock`.
- HTTP client is **`httpx2`** (with `httpcore2`), not `httpx`. Keep the imports as-is.
- ruff: line-length 100, target py312, `tests/*` ignores `PLR2004`/`S101`.
- mypy is `--strict` but `files = ["src"]` only (tests are not type-checked). Every module starts
  with `from __future__ import annotations`; annotate all public args and returns.
- `make test-cov` enforces **80% branch coverage over `src/athlete_stress_sim/core` only**
  (backend/frontend excluded); dropping below fails.

## Conventions

- Load the `python-conventions` skill before writing/reviewing Python. All code artifacts
  (identifiers, comments, docstrings, commit/branch names, build/config comments) are **English**;
  `athlete-stress-sim-PRD.md` and `ROADMAP.md` are Spanish and exempt.
- PEP 257 docstrings (Google-style `Args`/`Returns`/`Raises`). Reference PRD requirement IDs
  (`RF-xx`/`RNF-xx`) and sprint tags (`S1`–`S16`) where relevant.

## Architecture

- `backend/` — FastAPI app in `main.py` (module-level `app`; console script `athlete-stress-sim`).
  Routers: `api/oauth.py`, `api/ingest.py`, `api/exercises.py`, `api/metrics.py` (`/metrics/*`
  + `/simulate`); request/response models live in `schemas/`. Config in `config.py`.
- `core/etl/` — Polar OAuth2 client, catch-up sync, FIT parser, normalization.
- `core/storage/` — DuckDB stores: `session_store` (tables `athlete`, `exercises`, `samples`,
  `session_rpe`), `ingest_store` (ingest log/queue), `token_store`.
- `core/metrics/` — `trimp`, `rpe`, `acwr`, `load`, `decoupling`; `core/models/` — `banister`
  (ODE), `ekf`.
- `frontend/` — Dash + Mantine dashboard (dark theme); `api.py` fetches the backend over HTTP
  (`API_URL`, default `http://localhost:8000`), panels live in `components/`.
- Config uses pydantic-settings with env prefixes `ATHLETE_` / `POLAR_`; `.env` is git-ignored
  (copy `.env.example`). `/config/physiology` exposes the active non-secret constants.

## Gotchas

- DuckDB is one local file `data/athleta.duckdb`; `data/*` is git-ignored. Stores open a new
  connection per call and create the schema on init; tests should use temp DB paths.
- `tests/conftest.py` forces `POLAR_SYNC_ON_STARTUP=false` so importing `backend.main` never hits
  the network. Keep that when adding tests that import the app.
- FIT fixtures are synthesized in memory by `tests/helpers/fit_fixture.py`; never commit real
  biometric data (`RNF-01`).
- Trace work to `ROADMAP.md` sprints/DoD. Status: S1–S13 (Phases 0–2) complete; S14–S16
  (real-data validation, Docker/CI polish, public README) pending.
- Conventional commits (`feat:`, `refactor:`, ...). CI triggers on `main`/`develop`/`feature/**`
  and on PRs to `main`/`develop`.
