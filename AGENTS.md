# AGENTS.md

Personal endurance/hybrid training platform: Polar AccessLink ingest -> local DuckDB ->
TRIMP/ACWR/Banister/EKF metrics -> FastAPI + Dash. Single Python package (*src layout*),
Python 3.12 (pinned in `.python-version`; `requires-python` also allows 3.11).

## Commands (always go through `uv` + the Makefile)

- `make install` — `uv sync --all-groups` + install pre-commit hooks.
- `make format` / `make lint` / `make typecheck` / `make test` / `make test-cov`.
- Single test: `uv run pytest tests/test_trimp.py::test_name`.
- Run backend `make run-backend` (:8000, uvicorn `--reload`), frontend `make run-frontend` (:8050).
- `make db` opens a DuckDB shell (`data/athleta.duckdb`); `make clean` removes caches.
- Docker: `make docker-up` / `make docker-logs` / `make docker-down` (compose file is `docker/`).
- Definition of done = `make lint && make typecheck && make test` (exactly what CI runs, in that order).

## Toolchain quirks

- Never use `pip`/`requirements.txt`. Add deps to `pyproject.toml`, then `uv lock` + `uv sync`;
  CI and Docker build with `uv sync --frozen`, so commit `uv.lock`.
- HTTP client is **`httpx2`** (with `httpcore2`), not `httpx`. Keep the imports as-is; tests use
  `httpx2.MockTransport` injected into clients rather than patching.
- ruff: line-length 100, target py312; `tests/*` ignores `PLR2004` (magic numbers).
- mypy is `--strict` but `files = ["src"]` only (tests are not type-checked). Every module starts
  with `from __future__ import annotations`; add missing third-party stubs to
  `[[tool.mypy.overrides]]` instead of sprinkling `# type: ignore`.
- `make test-cov` enforces **80% branch coverage over `src/athlete_stress_sim/core` only**
  (backend/frontend excluded). CI runs `make test`, so a coverage regression only fails locally.
- pytest uses `pythonpath = ["src"]` plus `--strict-markers --strict-config`; no test service or
  network is required.

## Conventions

- Load the `python-conventions` skill before writing/reviewing Python. All code artifacts
  (identifiers, comments, docstrings, commit/branch names, build/config comments) are **English**;
  `athlete-stress-sim-PRD.md` and `ROADMAP.md` are Spanish and exempt.
- PEP 257 docstrings (Google-style `Args`/`Returns`/`Raises`). Reference PRD requirement IDs
  (`RF-xx`/`RNF-xx`) and sprint tags (`S1`–`S16`) where relevant.
- Conventional commits (`feat:`, `refactor:`, ...). CI triggers on `main`/`develop`/`feature/**`
  and on PRs to `main`/`develop`.

## Architecture

- `backend/` — FastAPI app in `main.py` (module-level `app`; console script `athlete-stress-sim`).
  Routers: `api/oauth.py` (`/auth/*`), `api/ingest.py` (`/sync`, `/sync/status`),
  `api/exercises.py` (`/exercises*`), `api/metrics.py` (`/metrics/{trimp,acwr,banister,decoupling}`
  plus `/simulate` and `/simulate/taper`); request/response models live in `schemas/`.
  `/health` and `/config/physiology` (non-secret constants) are defined in `main.py`.
- `core/etl/` — Polar OAuth2 client, catch-up sync, FIT parser, normalization.
- `core/storage/` — DuckDB stores: `session_store` (tables `athlete`, `exercises`, `samples`,
  `session_rpe`), `ingest_store` (`ingest_log`), `token_store` (`oauth_tokens`).
- `core/metrics/` — `trimp`, `rpe`, `acwr`, `load`, `decoupling`; `core/models/` — `banister`
  (ODE), `ekf`.
- `frontend/` — Dash + Mantine dashboard (dark theme); `api.py` fetches the backend over HTTP
  server-side (`API_URL`, default `http://localhost:8000`; Docker compose sets `backend:8000`),
  panels live in `components/`.
- Not strictly layered: `core/etl/` imports `backend.config` for Polar settings, and `frontend/`
  imports `backend.schemas` for shared models. Check that before moving modules.
- Config uses pydantic-settings with env prefixes `ATHLETE_` / `POLAR_`; `.env` is loaded from the
  current working directory and is git-ignored (copy `.env.example`).

## Gotchas

- DuckDB is one local file `data/athleta.duckdb`; `data/*` is git-ignored. Stores open a new
  connection per call and create the schema on init; tests must pass `tmp_path` DB paths.
- Backend startup runs a catch-up sync in a background thread when `POLAR_SYNC_ON_STARTUP=true`.
  `tests/conftest.py` forces it to `false`; keep that for any test that imports `backend.main`.
- FIT fixtures are synthesized in memory by `tests/helpers/fit_fixture.py`; never commit real
  biometric data (`RNF-01`). `data/raw/` may hold local real FIT files — do not add or commit them.
- `README.md` is a stub; real product intent lives in `athlete-stress-sim-PRD.md` and
  `ROADMAP.md`. Status: S1–S13 (Phases 0–2) complete; S14–S16 (real-data validation, Docker/CI
  polish, public README) pending.
