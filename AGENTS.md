# AGENTS.md

Personal endurance/hybrid training platform: Polar AccessLink ingest -> local DuckDB ->
TRIMP/ACWR/Banister (NLS-ridge calibration) / race-prediction metrics -> FastAPI + Dash.
Single Python package (*src layout*), Python 3.12 (pinned in `.python-version`;
`requires-python` also allows 3.11).

## Commands (always go through `uv` + the Makefile)

- `make install` — `uv sync --all-groups` + install pre-commit hooks.
- `make format` / `make lint` / `make typecheck` / `make test` / `make test-cov`.
- Single test: `uv run pytest tests/test_trimp.py::test_name`.
- Run backend `make run-backend` (:8000, uvicorn `--reload`), frontend `make run-frontend` (:8050).
- `make db` opens a DuckDB shell (`data/athleta.duckdb`, connection named `con`); `make clean`
  removes caches.
- Docker: `make docker-up` / `make docker-logs` / `make docker-down` (compose file is `docker/`).
- Definition of done = `make lint && make typecheck && make test-cov` (exactly what CI runs, in
  that order). `test-cov` includes the test suite and enforces the coverage gate.

## Toolchain quirks

- Never use `pip`/`requirements.txt`. Add deps to `pyproject.toml`, then `uv lock` + `uv sync`;
  CI and Docker build with `uv sync --frozen`, so commit `uv.lock`.
- HTTP client is **`httpx2`** (with `httpcore2`), not `httpx`. Keep the imports as-is; tests use
  `httpx2.MockTransport` injected into clients rather than patching.
- ruff: line-length 100, target py312; `tests/*` ignores `PLR2004` (magic numbers) and `S101`.
- mypy is `--strict` but `files = ["src"]` only (tests are not type-checked). Every module starts
  with `from __future__ import annotations`; add missing third-party stubs to
  `[[tool.mypy.overrides]]` (currently `fitparse.*`, `dash_mantine_components.*`, `plotly.*`,
  `scipy.*`) instead of sprinkling `# type: ignore`.
- `make test-cov` enforces **80% branch coverage over `src/athlete_stress_sim/core` only**
  (backend/frontend excluded); CI runs it as the test step.
- pytest uses `pythonpath = ["src"]` plus `--strict-markers --strict-config`; no test service or
  network is required.

## Conventions

- Load the `python-conventions` skill before writing/reviewing Python. All code artifacts
  (identifiers, comments, docstrings, commit/branch names, build/config comments) are **English**;
  `athlete-stress-sim-PRD.md`, `ROADMAP.md` and `docs/guia-funcionalidades.md` are Spanish and exempt.
- PEP 257 docstrings (Google-style `Args`/`Returns`/`Raises`). Reference PRD requirement IDs
  (`RF-xx`/`RNF-xx`) and sprint tags (`S1`–`S16`) where relevant.
- Conventional commits (`feat:`, `refactor:`, ...). CI triggers on `main`/`develop`/`feature/**`
  and on PRs to `main`/`develop`.

## Architecture

- `backend/` — FastAPI app in `main.py` (module-level `app`; console script `athlete-stress-sim`).
  Routers: `api/oauth.py` (`/auth/*`), `api/ingest.py` (`/sync`, `/sync/status`),
  `api/exercises.py` (`/exercises*`), `api/metrics.py` (`/metrics/{trimp,acwr,banister,calibration,
  running-baseline,decoupling}`, `/metrics/ekf` as a **deprecated alias**, plus `/simulate`,
  `/simulate/taper`, `/simulate/taper/plan`), `api/prediction.py` (`/metrics/best-efforts`,
  `/metrics/race-prediction`); request/response models live in `schemas/`. `/health` and
  `/config/physiology` (non-secret constants) are defined in `main.py`.
- `core/etl/` — Polar OAuth2 client, catch-up sync, FIT parser, normalization and
  `sports.py` (activity classification: running, strength, elliptical, other).
- `core/storage/` — DuckDB stores: `session_store` (tables `athlete`, `exercises`, `samples`,
  `session_rpe`), `ingest_store` (`ingest_log`), `token_store` (`oauth_tokens`).
- `core/metrics/` — `trimp` (running/elliptical), `rpe` (strength), `acwr`, `load`, `decoupling`,
  `performance`, `taper`,
  `race_prediction`; `core/models/` — `banister` (ODE) and `calibration` (bounded ridge
  least-squares with fixed `tau` + cross-validation gate; production path, **not** EKF).
- `frontend/` — Dash + Mantine dashboard (dark theme); `app.py` builds on-demand callbacks,
  `readiness.py` scores freshness, `api.py` fetches the backend over HTTP server-side (`API_URL`,
  default `http://localhost:8000`; Docker compose sets `backend:8000`), panels live in `components/`.
- Not strictly layered: `core/etl/` imports `backend.config` for Polar settings, `frontend/`
  imports `backend.schemas` and `core` types, and `api/prediction.py` reuses the private helpers
  `_assemble_daily_loads`/`_calibration` from `api/metrics.py`. Check that before moving modules.
- Config uses pydantic-settings with env prefixes `ATHLETE_` / `POLAR_`; `.env` is loaded from the
  current working directory and is git-ignored (use `.env.example`; never read or echo the local
  `.env`, it holds real credentials).

## Gotchas

- DuckDB is one local file `data/athleta.duckdb`; `data/*` is git-ignored. Stores open a new
  connection per call and create the schema on init; tests must pass `tmp_path` DB paths. Metrics
  load a cached `_SessionData` snapshot via batch queries keyed by the DB revision; reuse
  `_load_session_data` (in `backend/api/metrics.py`) instead of per-exercise queries. Storage reads
  return lightweight `SampleRow` tuples from `core/etl/types.py`, not Pydantic `Sample` models.
- Backend startup runs a catch-up sync via `lifespan` + `asyncio.to_thread` when
  `POLAR_SYNC_ON_STARTUP=true`. `tests/conftest.py` forces it to `false`; keep that for any test
  that imports `backend.main`.
- Calibration silently falls back to the physiological priors unless there are >= 8 observations,
  `R² >= 0.1` and >= 5% leave-one-out improvement. Tests for "calibrated" behavior must supply
  enough synthetic performance points.
- FIT fixtures are synthesized in memory by `tests/helpers/fit_fixture.py`; never commit real
  biometric data (`RNF-01`). `data/raw/` may hold local real FIT files — do not add or commit them.
- `README.md` is a stub; product intent lives in `athlete-stress-sim-PRD.md`, `ROADMAP.md` and the
  user-facing `docs/guia-funcionalidades.md`. Status: S1–S14 done (real-data validation; NLS
  replaced the old EKF), S15 done (DuckDB batch reads/cache, runtime Docker images, CI coverage
  gate); S16 (public README) pending. Confirm the GitHub Actions run after pushing.
