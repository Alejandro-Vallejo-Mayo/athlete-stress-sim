# Master Roadmap — Athlete Stress Sim

> **Historical delivery record.** This document is frozen after the `v1.0.0`
> release. Every implementation task traces back to one of the weeks and
> acceptance criteria defined here.
>
> - **Project:** Athlete Stress Sim
> - **Horizon:** 4 months (16 weeks) · 1 semester
> - **User zero:** personal preparation for a first half marathon (3 running days + 3 gym days)
> - **Device:** Polar Ignite (Polar AccessLink API)
> - **Requirement source:** [`product-requirements.md`](product-requirements.md) (v1.2.0)
> - **Status:** S1–S16 delivered · `v1.0.0` released
> - **Last updated:** 2026-11-19

---

## Table of contents

1. [How to use this document](#1-how-to-use-this-document)
2. [Tracking legend](#2-tracking-legend)
3. [Objectives and success criteria](#3-objectives-and-success-criteria)
4. [Phase overview](#4-phase-overview)
5. [Dependency map](#5-dependency-map)
6. [Weekly plan (sprints)](#6-weekly-plan-sprints)
7. [Acceptance criteria by phase (Definition of Done)](#7-acceptance-criteria-by-phase-definition-of-done)
8. [Risks and mitigations](#8-risks-and-mitigations)
9. [Prioritization (MoSCoW)](#9-prioritization-moscow)
10. [How this roadmap is updated](#10-how-this-roadmap-is-updated)

---

## 1. How to use this document

- Development is organized into **4 phases** (one per month) and **16 weekly
  sprints**.
- Each sprint lists concrete, verifiable **objectives**, **tasks** and
  **acceptance criteria**.
- Every task references a PRD requirement (`RF-xx` / `RNF-xx`) to preserve
  traceability.
- At the end of each sprint, the corresponding checkbox is updated and the real
  state is recorded in `git`.
- This document **does not replace** the PRD: the PRD defines the *what* and the
  *why*; this roadmap defines the *how*, *when* and *in what order*.

### 1.1 Conventions and development stack

- **Dependency and environment management:** [`uv`](https://docs.astral.sh/uv/)
  with `pyproject.toml` (PEP 621) and a locked `uv.lock`. `pip` and
  `requirements.txt` are never used directly; the environment is created with
  `uv sync`.
- **Layout:** `src/athlete_stress_sim/` (single package, *src layout*) with the
  `backend/`, `core/` and `frontend/` subpackages.
- **Lint and format:** `ruff`. **Typing:** `mypy`. **Tests:** `pytest` +
  `pytest-cov`.
- **Git hooks:** `pre-commit` (ruff, ruff-format, mypy, end-of-file-fixer,
  trailing-whitespace, check-yaml, check-toml, detect-private-key).
- **Orchestration:** the `Makefile` is the single entry point for commands;
  GitHub Actions CI runs `make lint`, `make typecheck` and `make test-cov`, never
  ad-hoc commands.
- **Python:** 3.12 pinned in `.python-version`; `requires-python` also allows
  3.11.

---

## 2. Tracking legend

| Mark | Meaning |
| --- | --- |
| `[ ]` | Pending |
| `[~]` | In progress |
| `[x]` | Completed |
| `[!]` | Blocked |

> Every phase milestone has a master checkbox in
> `## 7. Acceptance criteria by phase`.

---

## 3. Objectives and success criteria

**Final objective:** an end-to-end platform that ingests Polar telemetry,
quantifies training load (TRIMP/sRPE), models fitness-fatigue (ODE + NLS
calibration), estimates injury risk (ACWR) and provides an interactive dashboard
with a tapering simulator and race predictor to arrive at the half marathon in
good form.

**Measurable success criteria:**

1. The five functional requirement groups (`RF-01` → `RF-05`) are implemented
   and verified with tests.
2. The four non-functional requirements (`RNF-01` → `RNF-04`) are met.
3. Test coverage is at least **80 %** over `src/athlete_stress_sim/core`
   (metrics and models).
4. ODE simulation runs in **less than 0.5 s** (`RNF-02`).
5. The system is deployable with `docker compose up` and was used in a real
   routine for at least **2 weeks**.
6. The public `README.md` is written in English with LaTeX mathematics,
   architecture diagrams and real dashboard captures (portfolio).
7. Calibration behavior is reported honestly: with the available real-data
   window, the quality gate may not be passed and the system falls back to the
   physiological priors.

---

## 4. Phase overview

| Phase | Month | Weeks | Name | Main deliverable | Status |
| --- | --- | --- | --- | --- | --- |
| **F0** | 1 | S1–S4 | Foundations, Polar and DuckDB | Raw telemetry persisted | Done |
| **F1** | 2 | S5–S9 | Physiological engine | TRIMP, ACWR, ODE and calibration functional | Done |
| **F2** | 3 | S10–S13 | API + dashboard | Interactive dashboard and simulator | Done |
| **F3** | 4 | S14–S16 | Real use, validation and portfolio | Validated system + public documentation | Done |

### 4.1 Status summary

- **S1–S16:** delivered. The S14 maintenance item is closed; no blocking defects
  were found.
- **S16:** documentation complete, including the public README, dashboard
  captures, secret review, license, changelog, contribution and security files,
  and the `v1.0.0` release.
- **Release:** `v1.0.0` is tagged and published. The public README, documentation,
  validation report and dashboard captures are part of the release.

---

## 5. Dependency map

```text
S1 Config/Docker ──► S2 OAuth2 ──► S3 AccessLink ──► S4 Parser+DuckDB
                                                         │
                                                         ▼
                              S5 Running TRIMP ──► S6 Gym TRIMP ──► S7 ACWR
                                                                        │
                                                                        ▼
                                                        S8 Banister ODE ──► S9 EKF (historical)
                                                                               │
                                                                               ▼
S10 FastAPI ◄──────────────────────────────────────────────────────────────────┘
     │
     ▼
S11 Dash skeleton ──► S12 Status panel ──► S13 Simulator + decoupling
                                                    │
                                                    ▼
                                   S14 Real-data integration + NLS ──► S15 Docker/CI ──► S16 Public docs
```

`S9` is kept as a historical milestone: the EKF was replaced in `S14` by the
production NLS calibration.

---

## 6. Weekly plan (sprints)

### Phase 0 — Foundations, Polar connection and ingestion (Month 1)

#### Week 1 — Environment, repository and scaffolding

**Objective:** make the project reproducible from the first minute with a
complete toolchain.

- [x] Install `uv` and pin Python 3.12 with `.python-version`.
- [x] Initialize the project with `uv init` and the
  `src/athlete_stress_sim/` layout (single package).
- [x] Configure `pyproject.toml`: dependencies (`numpy`, `scipy`, `fitparse`,
  `duckdb`, `fastapi`, `uvicorn`, `dash`, `dash-mantine-components`, `plotly`,
  `pydantic`, `pydantic-settings`, `python-dotenv`, `httpx2`),
  `[project.scripts]`, `[tool.uv]`, `[tool.ruff]`, `[tool.mypy]`,
  `[tool.pytest.ini_options]`; generate `uv.lock`.
- [x] Create `src/athlete_stress_sim/backend/config.py` with physiological
  constants and credential placeholders (`hr_max`, `hr_rest`, `tau_1`, `tau_2`,
  `k_1`, `k_2`, `p0`, `sex`).
- [x] Create `.env.example` (client id, client secret, tokens, physiological
  priors and storage paths).
- [x] Create the `Makefile` with `install`, `lint`, `format`, `typecheck`,
  `test`, `test-cov`, `run-backend`, `run-frontend`, `db`, `docker-up`,
  `docker-logs`, `docker-down` and `clean`.
- [x] Configure `.pre-commit-config.yaml` (ruff, ruff-format, mypy,
  end-of-file-fixer, trailing-whitespace, check-yaml, check-toml,
  detect-private-key).
- [x] Configure `.github/workflows/ci.yml` to run `make lint`,
  `make typecheck` and `make test-cov` (no ad-hoc commands).
- [x] Configure `docker/Dockerfile.*` and `docker/docker-compose.yml`, installing
  dependencies through `uv sync`.
- [x] Milestone: `make install && make lint && make test-cov` and
  `docker compose up` work without errors.

#### Week 2 — Polar OAuth2 authentication

**Objective:** link the Polar account (`RF-01.1`).

- [x] Implement the Authorization Code flow with `state` using `httpx2`
  (confidential client, no PKCE).
- [x] Add `/auth/login` and `/auth/callback` endpoints in FastAPI.
- [x] Register the Polar user and persist access and refresh tokens in DuckDB.
- [x] Manage automatic token refresh before expiration.
- [x] Add unit tests for the flow with a mocked OAuth server.
- [x] Milestone: a valid `access_token` is obtained and renewed programmatically.

#### Week 3 — AccessLink client and catch-up sync

**Objective:** download sessions automatically (`RF-01.2`).

- [x] Implement `core/etl/polar_client.py`: list `exercises`, fetch summaries and
  download FIT files. TCX is not required because the Polar Ignite emits FIT.
- [x] Implement an idempotent **catch-up sync** (startup + `POST /sync`);
  webhooks/cron are deferred because the local deployment has no public HTTPS
  endpoint.
- [x] Record ingestion in DuckDB (`ingest_log`) as a queue for S4.
- [x] Handle errors, retries with backoff and `429` rate limiting.
- [x] Milestone: a new session is downloaded automatically and registered during
  a sync.

#### Week 4 — FIT parser and DuckDB persistence

**Objective:** persist second-by-second time series in DuckDB (`RF-01.3`,
`RNF-01`).

- [x] Parse FIT files with `fitparse`, extracting heart rate, speed/pace,
  cadence, altitude and cumulative distance.
- [x] Build the DuckDB OLAP model: `athlete`, `exercises`, `samples` and
  `session_rpe` tables.
- [x] Normalize and validate series (outliers, gaps, invalid samples).
- [x] Test the parser with synthetic FIT files generated in the tests (no real
  biometric data).
- [x] Milestone: a running session is persisted and queryable through SQL.

---

### Phase 1 — Physiological engine (Month 2)

#### Week 5 — Running TRIMP (Banister)

**Objective:** quantify running load (`RF-02.1`).

- [x] Implement `core/metrics/trimp.py` with
  `TRIMP = D · HR_r · a · e^(b·HR_r)` (male: `a=0.64`, `b=1.92`; female:
  `a=0.86`, `b=1.67`), integrated second by second.
- [x] Add `sex` (`male`/`female`) to `config.py` to select the coefficients.
- [x] Compute `HR_r` from heart rate, resting heart rate and maximum heart rate.
- [x] Test against hand-calculated reference values for both sexes.

#### Week 6 — Gym load (Foster session-RPE)

**Objective:** quantify strength load (`RF-02.2`, `RF-01.4`).

- [x] Implement `TRIMP_gym = RPE · D_min` (Foster session-RPE, Borg CR-10 0–10)
  in `core/metrics/rpe.py`.
- [x] Store strength sessions and their RPE in the `session_rpe` table.
- [x] Add an API endpoint for post-workout RPE (`POST /exercises/{id}/rpe`); the
  dashboard component is delivered in S11–S13.
- [x] Test the sRPE calculation and the endpoints.

#### Week 7 — ACWR (EWMA)

**Objective:** estimate injury risk (`RF-04.1`, `RF-04.2`).

- [x] Compute acute load (7-day EWMA) and chronic load (28-day EWMA),
  `λ = 2/(N+1)`.
- [x] Compute the `ACWR` ratio and risk matrix (sweet spot / warning / danger).
- [x] Assemble daily load (running TRIMP + gym sRPE) in `core/metrics/load.py`.
- [x] Test the EWMA series, daily aggregation and risk thresholds.

#### Week 8 — Banister model (ODE)

**Objective:** model fitness-fatigue (`RF-03.1`).

- [x] Implement the exact recurrence (`impulse_response`) and a numerical
  cross-check with `scipy.integrate.solve_ivp` (`odeint` is deprecated).
- [x] Compute `P(t) = P0 + k1·g(t) − k2·h(t)` and freshness.
- [x] Test stability and the response to a load impulse.
- [x] Benchmark `RNF-02` (< 0.5 s).

#### Week 9 — Extended Kalman Filter (EKF)

**Objective:** estimate individual parameters (`RF-03.2`). *Replaced in S14 by
NLS with fixed `tau` + ridge and a CV gate; kept as a historical reference.*

- [x] Implement an EKF with `filterpy` to estimate `k_1`, `k_2`, `tau_1` and
  `tau_2` (augmented state).
- [x] Integrate performance observations (the EKF consumes them; real extraction
  of pace at constant heart rate was deferred to S14).
- [x] Test with synthetic data (parameter convergence).

> **Historical note.** The EKF was a valid prototype but the gains and time
> constants were not identifiable enough from a single noisy performance series.
> The production path uses NLS with fixed priors and a cross-validation gate.

---

### Phase 2 — API and dashboard (Month 3)

#### Week 10 — FastAPI backend

**Objective:** expose metrics and simulations (`RF-05`).

- [x] Add REST endpoints: `/metrics/trimp/{exercise_id}`, `/metrics/acwr`,
  `/metrics/banister` and `/simulate`.
- [x] Add Pydantic request/response models
  (`backend/schemas/metrics.py`).
- [x] Integrate DuckDB and the physiological engine.
- [x] Add API integration tests (`tests/test_metrics_api.py`).

#### Week 11 — Dashboard skeleton and status panel

**Objective:** establish the visual structure and daily status panel
(`RF-05.1`).

- [x] Build `frontend/app.py` with Plotly Dash + Mantine (dark theme,
  `RNF-04`) and the Today/Trends/Plan tabs.
- [x] Add the readiness traffic light and freshness metric
  (`frontend/readiness.py`, `frontend/components/status.py`).
- [x] Build a responsive layout and base components (HTTP client
  `frontend/api.py`, initial load and Refresh button).
- [x] Add the **RPE pending** modal for strength sessions without RPE.

#### Week 12 — Dashboard: fitness-fatigue + ACWR

**Objective:** visualize the model dynamics.

- [x] Add the fitness / fatigue / freshness (TSB) chart over time
  (`frontend/components/fitness_chart.py`).
- [x] Add the ACWR risk gauge with the color matrix
  (`frontend/components/acwr_gauge.py`).
- [x] Connect the complete physiological status panel to the API
  (`frontend/app.py`).

#### Week 13 — Tapering simulator and decoupling

**Objective:** predictive planning (`RF-05.2`, `RF-05.3`).

- [x] Accept projected future sessions (e.g. "12 km at 5:00/km") through a form
  (`frontend/components/simulator.py`) and `POST /simulate/taper` (sRPE
  `RPE × duration`).
- [x] Add a predictive fatigue/form chart up to the half-marathon date (solid
  history + dashed forecast).
- [x] Add aerobic decoupling `EF = speed / HR` per kilometer
  (`core/metrics/decoupling.py` + `GET /metrics/decoupling/{id}`), visible in
  the dashboard (`frontend/components/decoupling.py`).
- [x] Test the simulator and the EF metric.

---

### Phase 3 — Real use, validation and portfolio (Month 4)

#### Week 14 — Real-routine integration and validation

**Objective:** put the system to work with real data.

- [x] Sync at least 2 weeks of real data (3 gym + 3 running days). Verified at
  S14 close: 14 runs + 11 gym sessions (2026-10-03 → 2026-11-03), 11/11 gym
  sessions with RPE. The final snapshot in [`validation.md`](validation.md) covers
  17 runs + 13 strength + 1 elliptical session and 16 calibration observations.
- [x] Support elliptical as a heart-rate activity: TRIMP load in ACWR/Banister,
  excluded from baseline, taper, decoupling and race prediction; `kind=elliptical`
  filter in `/exercises`.
- [x] Validate calibration against real observations. After the identifiability
  study, production uses NLS with fixed `tau` + ridge and a cross-validation gate
  (`GET /metrics/calibration`, deprecated alias `/metrics/ekf`); with 13
  observations at S14 close and 16 in the final snapshot, the gate is not passed
  and the system falls back to priors.
- [x] Tune the taper for the weeks before the half marathon. Implemented
  `POST /simulate/taper/plan` + the `Race taper` panel (factors 0.75/0.55/0.35,
  4-week baseline); validated with real data, maximum freshness falls on
  2026-12-13.
- [x] Race-time prediction (`RF-05.4`). Implemented `GET /metrics/best-efforts`
  and `POST /metrics/race-prediction` + the `Race predictor` panel with Riegel,
  critical speed, `%HRR`, EF, fitness adjustment, range and confidence.
- [x] Fix bugs found during real use. No blocking defects were found; minor
  frontend fixes landed and remaining polish is tracked as maintenance.

#### Week 15 — Optimization, Docker and CI/CD

**Objective:** make the system robust and reproducible (`RNF-03`).

- [x] Optimize DuckDB queries and simulation times. Batch reads
  (`list_exercises_with_rpe` + `query_all_samples`), lightweight `SampleRow`
  rows, an index on `samples(exercise_id)` and a database-revision cache:
  dashboard from 5.5 s to ~0.32 s warm, warm metric endpoints < 200 ms; the
  first cold request includes the snapshot load and can exceed that target.
- [x] Finalize Docker packaging and cold-start `docker compose up`. Runtime-only
  images with no data or secrets; `build --no-cache`, start with a real database
  and with an empty database verified.
- [x] Reach a green CI/CD pipeline (lint + test) in `.github/workflows/ci.yml`.
  CI runs `lint → typecheck → test-cov` with the 80 % gate on `core`; validated
  locally, GitHub run pending confirmation after the push.

#### Week 16 — Public documentation and portfolio

**Objective:** close the project in a presentable state.

- [x] Public `README.md` in English with:
  - [x] Mathematical explanation (LaTeX equations).
  - [x] Architecture diagram.
  - [x] Real dashboard captures.
- [x] Translate the PRD to English and update it to the as-built state.
- [x] Translate the roadmap to English and update it to the as-built state.
- [x] Translate and update the user guide to English.
- [x] Write `architecture.md` — system design, data flows and technical debt.
- [x] Write `mathematical-model.md` — load, Banister, calibration, ACWR and prediction.
- [x] Write `validation.md` — real-data snapshot, calibration, latency and quality gates.
- [x] Review exposed credentials and clean up secrets. No tracked `.env`, `.fit`,
  `.duckdb`, `.pem` or `.key` files and no real credentials in versioned content.
- [x] Add `LICENSE` (MIT), `CHANGELOG.md`, `CONTRIBUTING.md` and `SECURITY.md`.
- [x] Tag the `v1.0.0` release and publish the GitHub Release.

---

## 7. Acceptance criteria by phase (Definition of Done)

### Phase 0 — DoD

- [x] Authenticate against Polar AccessLink and persist tokens.
- [x] Persist a running session in DuckDB with second-by-second series.
- [x] Reproducible Docker environment with `docker compose up`.
- [x] Tests for `src/athlete_stress_sim/core/etl` are green.

### Phase 1 — DoD

- [x] TRIMP (running, elliptical and gym), ACWR, Banister ODE and calibration
  implemented and tested (EKF replaced by NLS in S14).
- [x] Coverage of `src/athlete_stress_sim/core` ≥ 80 %.
- [x] ODE simulation < 0.5 s.

### Phase 2 — DoD

- [x] FastAPI serves metrics and simulations.
- [x] Dashboard (dark mode) shows physiological status, fitness/fatigue/freshness,
  ACWR, aerobic decoupling and the tapering simulator.
- [x] End-to-end: dashboard ↔ API ↔ DuckDB works.

### Phase 3 — DoD

- [x] System validated with ≥ 2 weeks of real data.
- [x] Green CI/CD and reproducible Docker deployment. Docker verified cold; CI
  validated locally with `make test-cov` (GitHub run pending after the push).
- [x] Complete public documentation (English, LaTeX, diagrams, captures).

---

## 8. Risks and mitigations

| Risk | Impact | Probability | Mitigation |
| --- | --- | --- | --- |
| Polar API availability / rate limits | High | Medium | Idempotent catch-up sync (startup + button) with retries/backoff and `Retry-After`; local caching (S3). |
| AccessLink v4 (Dynamic API, JSON) could simplify ingestion | Medium | Low | Evaluated in S3; v3 (FIT) is retained and migration is deferred unless it adds value. |
| Insufficient data to calibrate the model (few weeks) | High | Medium | Use bibliographic priors; start with reference values (S1). |
| Mathematical complexity (ODE + calibration) takes longer than expected | High | Medium | Separate metrics (F1) from models (late F1); prioritize TRIMP/ACWR as the MVP. |
| Plotly Dash + Mantine learning curve | Medium | Medium | Early skeleton (S11); reusable components. |
| Limited example `.FIT` fixtures | Medium | Low | Generate synthetic data in addition to real captures (S4). |
| Accidental credential exposure | High | Low | `.env` in `.gitignore`; final review (S16). |
| Calibration identifiability | High | Medium | Fix `tau`, estimate only the gains with bounded ridge and a CV gate; fall back to priors when the gate fails. |
| Privacy leak in published screenshots | High | Low | Review and sanitize captures; never commit raw FIT files or the DuckDB database. |
| Documentation drift | Medium | Medium | Keep the PRD/roadmap as the source of truth; verify commands, formulas and links before release. |

---

## 9. Prioritization (MoSCoW)

**Must have (MVP core):**

- `RF-01` Polar ingestion + DuckDB
- `RF-02` TRIMP (running + gym)
- `RF-04` ACWR
- `RF-03.1` Banister ODE
- `RF-05.1` Status panel
- `RNF-01`, `RNF-02`, `RNF-03`

**Should have (high value, medium effort):**

- `RF-05.2` Tapering simulator and race taper
- `RF-03.2` Calibration (NLS)
- `RF-05.3` Aerobic decoupling
- `RF-05.4` Race-time prediction
- `RF-01.5` / `RF-02.3` Elliptical support

**Could have (if time allows):**

- Report export (PDF/CSV).
- Comparisons between training blocks.
- Push/email ACWR risk alerts.

**Won't have (outside the semester scope):**

- Real multi-user support (user zero only).
- Integration with other devices (Garmin, Whoop).

---

## 10. How this roadmap is updated

1. **At the start of each sprint:** review the current sprint and move its master
   checkbox to `[~]`.
2. **During the sprint:** mark individual tasks as they are completed.
3. **At the end of the sprint:** verify the phase DoD and update its checkbox in
   `## 7`.
4. **Scope changes:** any deviation from the PRD is recorded here with a note
   and, if structural, propagated to the PRD.
5. **Decision history:** recorded in `git commit` messages and repository
   issues/PRs.

> **Golden rule:** if a task does not appear in this document, it is either out
> of scope or must be added explicitly before implementation.

> This roadmap is frozen as the delivery record for `v1.0.0`. Future work should
> be tracked in a new roadmap or in the repository issue tracker.
