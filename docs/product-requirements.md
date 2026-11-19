# Product Requirements Document (PRD)

## Athlete Stress Sim — Local-first training-load, fitness-fatigue and race-readiness platform

> **Document version:** 1.2.0 · **Product version:** 1.0.0 · **Status:** Final / as-built · **Last updated:** 2026-11-19
>
> This document describes the final `v1.0.0` implementation. Where the original
> plan and the delivered system differ, the as-built behavior is normative.
> Historical decisions and sprint tags are retained for traceability; the
> [`roadmap.md`](roadmap.md) is the delivery record.

| Field | Value |
| --- | --- |
| **Project** | Athlete Stress Sim |
| **Repository** | `athlete-stress-sim` |
| **Author** | Alejandro Vallejo Mayo — Double Degree in Mathematics and Computer Science, University of Seville |
| **User zero** | Personal preparation for a first half marathon (3 running days + 3 gym days per week) |
| **Device** | Polar Ignite via Polar AccessLink v3 |
| **Horizon** | 4 months / 16 weekly sprints |
| **Requirement source** | This document |
| **Planning source** | [`roadmap.md`](roadmap.md) |
| **User documentation** | [`user-guide.md`](user-guide.md) |
| **Public overview** | [`README.md`](../README.md) |
| **Release notes** | [`CHANGELOG.md`](../CHANGELOG.md) |

---

## Table of contents

1. [Document status](#1-document-status)
2. [Product overview](#2-product-overview)
3. [Scope and technical architecture](#3-scope-and-technical-architecture)
4. [Functional requirements](#4-functional-requirements)
5. [Non-functional requirements](#5-non-functional-requirements)
6. [Requirement status summary](#6-requirement-status-summary)
7. [Project structure](#7-project-structure)
8. [Development plan by milestones](#8-development-plan-by-milestones)
9. [Success criteria and acceptance](#9-success-criteria-and-acceptance)
10. [Constraints, assumptions and risks](#10-constraints-assumptions-and-risks)
11. [Glossary](#11-glossary)
12. [Related documents](#12-related-documents)

---

## 1. Document status

This PRD is the product-level contract for Athlete Stress Sim. It defines
**what** the system does, **why** it exists and **how each requirement is
formulated**. The [`roadmap.md`](roadmap.md) defines **when** and **in what
order** the work was delivered. Equations in this document define the required
behavior; the canonical derivations, assumptions and references live in
[`mathematical-model.md`](mathematical-model.md).

Requirement identifiers (`RF-xx`, `RNF-xx`) and sprint tags (`S1`–`S16`) are
stable. Three requirements were added during implementation:

- `RF-01.5` — activity classification, including elliptical sessions.
- `RF-02.3` — elliptical training load.
- `RF-05.4` — race-time prediction.

`RF-03.2` was originally specified as an Extended Kalman Filter (EKF). The final
implementation uses bounded ridge least squares with fixed time constants and a
cross-validation gate. The EKF remains documented as a historical milestone.

---

## 2. Product overview

### 2.1 Context and motivation

In endurance and hybrid training (running plus strength work), a major contributor
to stagnation and overuse complaints — plantar fasciitis, shin splints,
tendinopathy — is the mismatch between **training load** and **neuromuscular
recovery capacity**. Conventional metrics such as weekly kilometers or total
minutes can obscure the individual physiological response and the accumulation
of fatigue over several weeks.

Athlete Stress Sim addresses that gap with a local, reproducible pipeline that
turns raw Polar telemetry into a daily load series and uses it to estimate
fitness, fatigue and overload risk.

### 2.2 Product objective

Athlete Stress Sim is an end-to-end personal physiological analysis platform
that:

1. Ingests and processes training telemetry from the **official Polar
   AccessLink API** when the Polar Ignite watch is synchronized.
2. Quantifies training load with **Banister TRIMP** for heart-rate activities
   and **Foster session-RPE** for strength sessions.
3. Models **fitness-fatigue dynamics** with ordinary differential equations
   (ODEs) and calibrates the individual gains with a bounded ridge fit and a
   cross-validation gate.
4. Estimates overload risk with the **acute:chronic workload ratio (ACWR)**.
5. Provides an interactive **performance dashboard, tapering simulator and race
   predictor** to plan load and arrive at the half marathon in good form.

### 2.3 User zero and real use case

The first user is the author: a student preparing for a first half marathon with
a hybrid weekly routine of three running sessions and three strength sessions.
The system was used with real Polar data for a 41-day validation window
(2026-10-03 → 2026-11-12) before the `v1.0.0` release. The aggregate snapshot and
diagnostics are documented in [`validation.md`](validation.md).

### 2.4 Scope and non-goals

**In scope**

- Single-user, local-first deployment.
- Polar AccessLink OAuth2 and FIT ingestion.
- Running, strength and elliptical activity handling.
- Daily load, ACWR, Banister fitness-fatigue and calibration.
- Dashboard, taper simulation, decoupling analysis and race prediction.
- Docker Compose deployment and a reproducible development workflow.

**Out of scope**

- Multi-user accounts or tenant isolation.
- Devices other than Polar AccessLink (Garmin, Whoop, Apple Watch, etc.).
- Clinical diagnosis, injury prediction or medical advice.
- Webhooks or cron-based push ingestion (deferred; catch-up sync is used).
- PDF/CSV report export and push/email risk alerts.
- Native mobile applications or real-time streaming.

---

## 3. Scope and technical architecture

### 3.1 System boundaries

```text
Polar AccessLink v3
        │  OAuth2 + FIT download
        ▼
Local ingestion pipeline
        │  parse + normalize
        ▼
DuckDB (local analytical store)
        │  daily load + performance observations
        ▼
FastAPI metrics and simulation service
        │  HTTP/JSON
        ▼
Plotly Dash + Mantine dashboard
```

All biometric data remains in a local DuckDB file. The system does not send
training data to third parties (`RNF-01`).

### 3.2 Technology stack

| Layer | Technology | Role |
| --- | --- | --- |
| Language | Python 3.12 (3.11+ allowed) | Core implementation |
| Environment | `uv` + `pyproject.toml` + `uv.lock` | Reproducible dependency resolution |
| HTTP / OAuth2 | `httpx2` + `httpcore2` | Polar AccessLink client |
| FIT parsing | `fitparse` | Second-by-second telemetry extraction |
| Analytical store | DuckDB | Embedded OLAP persistence |
| Numerical engine | NumPy + SciPy | ODE integration and bounded least squares |
| API | FastAPI + Uvicorn | REST endpoints and OpenAPI docs |
| Dashboard | Plotly Dash + Dash Mantine Components | Dark, information-dense UI |
| Contracts/config | Pydantic v2 + pydantic-settings | Schemas and environment configuration |
| Testing | pytest + pytest-cov | Unit, integration and coverage gates |
| Quality | ruff + mypy + pre-commit | Lint, format and static typing |
| Delivery | Docker Compose + GitHub Actions | Reproducible deployment and CI |

> The production calibration path does **not** use `filterpy` or an EKF. The
> EKF was implemented in S9 and replaced in S14 by the current NLS calibration.

### 3.3 Data model

| Table | Purpose |
| --- | --- |
| `athlete` | Single user-zero identity (`polar_user_id`) and creation timestamp |
| `exercises` | Session metadata (sport, start time, duration, distance, heart rate) |
| `samples` | Second-by-second telemetry (heart rate, speed, cadence, altitude, distance) |
| `session_rpe` | Session-RPE for strength sessions |
| `ingest_log` | Ingestion audit and pending-work queue |
| `oauth_tokens` | Polar access and refresh tokens |

Storage reads return lightweight `SampleRow` tuples rather than Pydantic models.
Metrics use a cached daily snapshot keyed by the database revision to avoid
repeated per-session queries.

### 3.4 API surface

The backend exposes routers for:

- `/auth/*` — Polar OAuth2 login, callback, status and token refresh.
- `/sync`, `/sync/status` — catch-up ingestion and counters.
- `/exercises*` — session listing, detail, filtering and RPE updates.
- `/metrics/{trimp,acwr,banister,calibration,running-baseline,decoupling}` —
  physiological metrics. `/metrics/ekf` remains a deprecated alias.
- `/metrics/best-efforts`, `/metrics/race-prediction` — race prediction.
- `/simulate`, `/simulate/taper`, `/simulate/taper/plan` — what-if and taper
  planning.
- `/health`, `/config/physiology` — liveness and non-secret physiology.

Interactive API documentation is generated by FastAPI at `/docs`.

---

## 4. Functional requirements

### RF-01: Ingestion and Polar telemetry

#### RF-01.1 — Polar OAuth2

Implement the OAuth2 Authorization Code flow with the Polar AccessLink API to
link the user account. The client is confidential and does not use PKCE. Access
and refresh tokens are persisted locally and refreshed automatically before
expiration.

#### RF-01.2 — Automatic session retrieval

Download new `exercises` registered by the Polar Ignite. The delivered
implementation uses an **idempotent catch-up sync**:

- one sync at backend startup when `POLAR_SYNC_ON_STARTUP=true`;
- one on-demand sync through `POST /sync` and the dashboard **Refresh** action.

Polar's exercise listing covers the last 30 days; sessions already downloaded
remain in DuckDB. Webhooks and cron jobs are deferred because the local
deployment has no public HTTPS endpoint. Retries use backoff and honor rate
limits.

#### RF-01.3 — Telemetry parsing

Ingest second-by-second series from FIT files:

- heart rate (`HR_t`);
- speed and derived pace (`Pace_t`);
- cadence;
- altitude;
- cumulative distance.

The parser normalizes units, flags out-of-range samples as invalid, nulls the
invalid values and keeps the rows so gaps remain visible. TCX is not required
because the Polar Ignite emits FIT.

#### RF-01.4 — Strength training and session-RPE

Record sessions classified as strength/muscle training and allow the user to
enter the **session RPE on the Borg CR-10 scale (0–10)** after the workout. The
dashboard exposes an **RPE pending** notice and a modal backed by
`POST /exercises/{id}/rpe`. Without an RPE, a strength session contributes no
load.

#### RF-01.5 — Activity classification

Classify each session into one of four families:

- **running** — contributes running-specific metrics;
- **strength** — uses session-RPE;
- **elliptical** — uses heart-rate TRIMP but is excluded from running-specific
  metrics;
- **other** — stored but contributes no load unless it has valid heart-rate
  samples.

Elliptical is checked before strength because Polar may report a generic
`training` sport with a `cardio_training` sub-sport.

---

### RF-02: Training-load quantification

#### RF-02.1 — Running TRIMP (Banister)

The training impulse is calculated from the exponential heart-rate weighting
factor:

$$
TRIMP = D \cdot HR_r \cdot y
$$

where

$$
HR_r = \mathrm{clamp}\!\left(
\frac{HR - HR_{\text{rest}}}{HR_{\max} - HR_{\text{rest}}},
0, 1
\right)
$$

and

$$
y = a \cdot e^{b \cdot HR_r}
$$

with sex-specific coefficients:

$$
a = 0.64,\; b = 1.92 \quad \text{(male)}
\qquad
a = 0.86,\; b = 1.67 \quad \text{(female)}
$$

`D` is the duration in minutes. The production path integrates the weighting
factor over the second-by-second heart-rate series rather than using only the
average heart rate:

$$
TRIMP = \sum_{i} \Delta t_{\min} \cdot HR_{r,i} \cdot a \cdot e^{b \cdot HR_{r,i}}
$$

#### RF-02.2 — Strength load (Foster session-RPE)

Heart rate is a poor load proxy for strength training, so strength sessions use
Foster's session-RPE method:

$$
TRIMP_{\text{gym}} = RPE \cdot D_{\min}
$$

where `RPE` is the whole-session effort on the Borg CR-10 scale (0–10) and
`D_min` is the duration in minutes. The result is expressed in arbitrary units
(AU) and added to the running load series.

#### RF-02.3 — Elliptical load

Elliptical sessions use the same Banister TRIMP as running because they provide
valid heart-rate telemetry. They contribute to daily load, ACWR and the
fitness-fatigue model. They are excluded from running-specific analyses
(baseline, taper, decoupling and race prediction) because pace and distance are
not directly comparable.

#### RF-02.4 — Daily load assembly

Session loads are summed per calendar day. Days between the first and last
session are filled with `0.0` so fitness and fatigue can decay on rest days.
Running TRIMP and strength session-RPE share the same arbitrary-unit scale; the
combination is a practical simplification, not a claim of physiological
equivalence.

---

### RF-03: Physiological engine

#### RF-03.1 — Banister fitness-fatigue model (ODE)

The net performance `P(t)` responds to the daily load sequence `w(t)` through
two first-order components:

$$
\frac{dg(t)}{dt} = -\frac{1}{\tau_1}g(t) + w(t)
\qquad \text{(fitness)}
$$

$$
\frac{dh(t)}{dt} = -\frac{1}{\tau_2}h(t) + w(t)
\qquad \text{(fatigue)}
$$

$$
P(t) = P_0 + k_1 \cdot g(t) - k_2 \cdot h(t)
$$

For daily impulsive loads, the exact recurrence is:

$$
g_t = g_{t-1}e^{-1/\tau_1} + w_t
\qquad
h_t = h_{t-1}e^{-1/\tau_2} + w_t
$$

$$
F_t = k_1 g_t - k_2 h_t
\qquad
P_t = P_0 + F_t
$$

`F_t` is the **freshness** or training-stress balance (TSB). Positive freshness
means the athlete is prepared; negative freshness immediately after a hard
session is expected because fatigue rises faster than fitness.

Reference defaults and priors:

- `HR_max = 200` bpm;
- `HR_rest = 60` bpm;
- `tau_1 = 42` days (fitness);
- `tau_2 = 7` days (fatigue);
- `k_1 = 1.0`;
- `k_2 = 2.0`;
- `P_0 = 0.0`.

The exact recurrence is the production path. `solve_ivp` provides a numerical
cross-check with the continuous-time formulation. `odeint` is not used.

#### RF-03.2 — Individual calibration (NLS with fixed time constants)

The final calibration replaces the historical EKF. The fitness-fatigue model is
ill-conditioned when the gains and time constants are estimated jointly from a
single noisy performance series. The production path therefore:

- fixes `tau_1` and `tau_2` at the physiological priors;
- estimates only `P_0`, `k_1` and `k_2`;
- uses observed running performance as the efficiency factor
  `EF = speed / HR`, normalized by its median;
- solves a bounded, ridge-regularized linear least-squares problem.

The observation model is:

$$
y_d = \beta_0 + \beta_1 g_d - \beta_2 h_d + \varepsilon_d
$$

and the fit minimizes:

$$
\hat{\beta} = \arg\min_{\beta}
\left\| X\beta - y \right\|_2^2
+ \lambda \left\| \beta - \beta_{\text{prior}} \right\|_2^2
$$

The acceptance gate also requires positive gains and `tau_1 > tau_2`. The fitted
coefficients are rescaled to the prior freshness amplitude so the dashboard keeps
expressing freshness in load units.

A calibration is accepted only when **all** of the following hold:

- at least **8 observations**;
- in-sample **R² ≥ 0.1**;
- at least **5 % leave-one-out cross-validation RMSE improvement** over the
  prior-shaped baseline;
- positive gains and `tau_1 > tau_2`.

Otherwise the system silently falls back to the physiological priors. The
result is exposed through `GET /metrics/calibration`; `GET /metrics/ekf` is a
deprecated alias.

> **Historical note (S9 → S14).** The original PRD specified an Extended Kalman
> Filter for online parameter inference. The EKF was implemented and tested, but
> the identifiability study showed that the gains and time constants could not be
> estimated reliably from the available data. The NLS calibration is the
> production path from S14 onward.

---

### RF-04: Injury-risk prevention with ACWR

#### RF-04.1 — Acute and chronic load

Compute the exponentially weighted moving averages (EWMA) of daily load:

$$
EWMA_t = \lambda L_t + (1-\lambda) EWMA_{t-1},
\qquad
\lambda = \frac{2}{N+1}
$$

where `N = 7` days for acute load and `N = 28` days for chronic load. The ratio
is:

$$
ACWR_t = \frac{EWMA_t^{\text{acute}}}{EWMA_t^{\text{chronic}}}
$$

The EWMA is seeded with the first load value, so the first days start near
`ACWR = 1.0` and converge as history accumulates.

#### RF-04.2 — Risk matrix

| Zone | ACWR | Interpretation |
| --- | --- | --- |
| **Undertraining** | `< 0.8` | Recent load is low relative to history; possible deconditioning or taper. |
| **Sweet spot** | `0.8 – 1.3` | Considered a safe progression range. |
| **Warning** | `> 1.3 – 1.5` | Load increase to monitor. |
| **Danger** | `> 1.5` | Load spike; elevated overuse-risk signal. |

ACWR is a load signal, not an injury diagnosis. It does not include sleep,
stress, terrain, age or recovery quality.

---

### RF-05: Interactive performance dashboard

The dashboard is a Dash + Mantine application with three top-level tabs:
**Today**, **Trends** and **Plan**. The interface uses a dark, high-density
sports aesthetic (`RNF-04`).

#### RF-05.1 — Daily physiological status

The **Today** view provides:

- a readiness traffic light derived from the latest freshness value;
- the current freshness in AU;
- an ACWR risk gauge;
- quick summary statistics.

Readiness is relative to the athlete's own recent history. With at least 14 days
of history, the color is based on the percentile of the latest freshness over
the last 90 days:

| Color | Level | Condition |
| --- | --- | --- |
| Green | **Ready** | `>= P50` |
| Yellow | **Caution** | `P15 – P50` |
| Red | **Rest** | `< P15` |
| Gray | No data | No training history |

With fewer than 14 days, absolute thresholds are used: `F >= 0` ready,
`-5 <= F < 0` caution and `F < -5` rest.

#### RF-05.2 — Tapering simulator and race-aware taper plan

The **Plan** tab contains a what-if tapering simulator and an automatic race
taper planner.

**What-if simulator**

- The user enters a future session: date, distance (km), pace (min/km) and RPE
  (0–10).
- The planned session load is estimated as:

$$
D_{\min} = \text{distance}_{\text{km}} \cdot \text{pace}_{\min/\text{km}}
\qquad
\text{load} = RPE \cdot D_{\min}
$$

- The backend projects fitness, fatigue and freshness over the history plus the
  planned sessions.
- The chart uses a solid line for real history, a dashed line for the forecast
  and a vertical boundary between them.

**Race taper plan**

- The user supplies race date, weekly volume, runs per week, pace, RPE and taper
  weeks.
- Weekly volume decreases linearly while intensity (pace and RPE) is preserved:
  factors `0.75 → 0.35` for a multi-week taper (`0.75`, `0.55`, `0.35` for three
  weeks); a one-week taper uses `0.5`.
- The default baseline is the last four weeks of running data, requiring at
  least four valid sessions.
- Sessions are placed on Tuesday, Thursday and Sunday for a three-run week and
  never on or after race day, so race morning is a rest day in the projection.
- The plan models running only; gym sessions must be adjusted separately.

#### RF-05.3 — Aerobic decoupling

For a selected run, compute the efficiency factor per kilometer:

$$
EF_k = \frac{\sum_{i \in k} v_i}{\sum_{i \in k} HR_i}
$$

where `v` is speed in meters per second and `HR` is heart rate in bpm. With
equal sample counts this is the ratio of mean speed to mean heart rate. Higher
EF means more speed at the same heart rate.

Compare the two halves of the run:

$$
\text{decoupling} =
\frac{\overline{EF}_{\text{first}} - \overline{EF}_{\text{second}}}
{\overline{EF}_{\text{first}}} \times 100
$$

A positive value indicates cardiovascular drift (EF fell in the second half). At
least two kilometers with valid speed and heart-rate data are required.

#### RF-05.4 — Race-time prediction

Given a target distance (5K, 10K, half marathon, marathon or a custom distance),
estimate the time the athlete could achieve at maximal race effort. Predictions
use detected best efforts from training and/or a user-provided race or time
trial.

Candidate efforts are classified by relative heart-rate reserve (`%HRR`) and
efficiency factor so that easy running does not make the prediction artificially
slow:

| Tier | %HRR | Use |
| --- | --- | --- |
| `race` | `>= 88 %` | Direct reference; high confidence |
| `hard` | `80 – 88 %` | Reference with medium confidence |
| `moderate` | `70 – 80 %` | Low-confidence reference only |
| `easy` | `< 70 %` | Not used as race pace; fitness/EF trend only |

Two distance-time models are supported, with a heart-rate extrapolation fallback:

**Riegel power law**

$$
T_2 = T_1 \left(\frac{D_2}{D_1}\right)^k,
\qquad k \approx 1.06
$$

**Critical speed**

$$
D = CS \cdot T + D'
$$

The automatic model selection uses critical speed when at least three quality
efforts at different distances produce a good fit; otherwise it uses Riegel. If
only easy efforts exist, it extrapolates speed from the efficiency factor and a
race-level heart rate and reports low confidence.

Each effort is adjusted by the Banister fitness change since its date and
converted to an equivalent race effort. Target race-level `%HRR` is approximately
93 % for short races, 90 % for 10K, 88 % for the half marathon and 85 % for the
marathon. The response includes predicted time, pace, fast/slow range, model,
confidence, the efforts used and explanatory notes.

> This is a **potential** prediction, not a guarantee for today: it does not
> subtract same-day fatigue. A real race or time trial substantially increases
> confidence.

---

## 5. Non-functional requirements

### RNF-01 — Privacy and local storage

All biometric data is stored in a local DuckDB file and is never shared with
third parties. Raw FIT files, the DuckDB database and real biometric captures
must not be committed to the repository. Dashboard screenshots published in the
documentation are reviewed and sanitized; unsanitized captures are not committed.

### RNF-02 — Simulator performance

ODE simulations and numerical integration must run in **less than 0.5 seconds**.
Additional performance targets in the delivered implementation are a warm
dashboard load of roughly 0.3 seconds and warm metric endpoints below 200 ms,
achieved through batch reads and a cached session snapshot. The first cold request
includes the initial snapshot load and can exceed the warm target.

### RNF-03 — Containerized deployment

The system runs as an isolated multi-service deployment through Docker Compose.
Runtime images contain application dependencies only — no secrets, raw data or
local databases.

### RNF-04 — Visual design

The dashboard uses a dark mode with a modern, information-dense sports
aesthetic. Layouts are responsive and remain readable on laptop screens.

---

## 6. Requirement status summary

Status reflects the final `v1.0.0` implementation. All functional and
non-functional requirements are implemented. The automated suite covers the core,
API and frontend behavior; deployment and real-data behavior are validated
separately. The calibration gate may still fall back to the priors on short or
noisy histories.

| ID | Requirement | Priority | Status | Notes |
| --- | --- | --- | --- | --- |
| `RF-01.1` | Polar OAuth2 | Must | Implemented | Confidential client; automatic refresh |
| `RF-01.2` | Automatic session retrieval | Must | Implemented | Catch-up sync; webhooks deferred |
| `RF-01.3` | FIT telemetry parsing | Must | Implemented | Second-by-second series |
| `RF-01.4` | Strength session-RPE | Must | Implemented | API + dashboard modal |
| `RF-01.5` | Activity classification | Should | Implemented | Running, strength, elliptical, other |
| `RF-02.1` | Running TRIMP | Must | Implemented | Per-sample Banister integration |
| `RF-02.2` | Strength sRPE load | Must | Implemented | Foster CR-10 method |
| `RF-02.3` | Elliptical load | Should | Implemented | Load-only; excluded from running metrics |
| `RF-02.4` | Daily load assembly | Must | Implemented | Rest days filled with zero |
| `RF-03.1` | Banister ODE | Must | Implemented | Exact recurrence + `solve_ivp` cross-check |
| `RF-03.2` | Individual calibration | Should | Implemented | NLS with fixed `tau`, ridge and CV gate; priors fallback |
| `RF-04.1` | ACWR / EWMA | Must | Implemented | Acute 7 d / chronic 28 d |
| `RF-04.2` | Risk matrix | Must | Implemented | Four zones |
| `RF-05.1` | Daily status dashboard | Must | Implemented | Readiness, freshness and ACWR |
| `RF-05.2` | Taper simulation and plan | Should | Implemented | What-if + race taper |
| `RF-05.3` | Aerobic decoupling | Should | Implemented | EF per kilometer |
| `RF-05.4` | Race-time prediction | Should | Implemented | Riegel, critical speed, HR extrapolation |
| `RNF-01` | Local privacy | Must | Implemented | Local DuckDB |
| `RNF-02` | Simulator performance | Must | Implemented | ODE < 0.5 s |
| `RNF-03` | Docker Compose | Must | Implemented | Runtime-only images |
| `RNF-04` | Dark visual design | Must | Implemented | Dash + Mantine |

---

## 7. Project structure

```text
athlete-stress-sim/
├── .github/
│   └── workflows/
│       └── ci.yml
├── .pre-commit-config.yaml
├── docker/
│   ├── Dockerfile.backend
│   ├── Dockerfile.frontend
│   └── docker-compose.yml
├── docs/
│   ├── assets/
│   ├── product-requirements.md
│   ├── roadmap.md
│   ├── user-guide.md
│   ├── architecture.md
│   ├── mathematical-model.md
│   └── validation.md
├── src/
│   └── athlete_stress_sim/
│       ├── backend/
│       │   ├── api/
│       │   │   ├── oauth.py
│       │   │   ├── ingest.py
│       │   │   ├── exercises.py
│       │   │   ├── metrics.py
│       │   │   └── prediction.py
│       │   ├── schemas/
│       │   ├── config.py
│       │   └── main.py
│       ├── core/
│       │   ├── etl/
│       │   ├── metrics/
│       │   ├── models/
│       │   └── storage/
│       └── frontend/
│           └── components/
├── tests/
├── .env.example
├── .python-version
├── LICENSE
├── CHANGELOG.md
├── CONTRIBUTING.md
├── SECURITY.md
├── Makefile
├── pyproject.toml
├── uv.lock
└── README.md
```

---

## 8. Development plan by milestones

| Month | Sprints | Milestone | Status |
| --- | --- | --- | --- |
| 1 | S1–S4 | Environment, OAuth2, AccessLink sync, FIT parser and DuckDB persistence | Done |
| 2 | S5–S9 | TRIMP, session-RPE, ACWR, Banister ODE and initial EKF calibration | Done (EKF superseded in S14) |
| 3 | S10–S13 | FastAPI metrics, dashboard, simulator and decoupling | Done |
| 4 | S14–S16 | Real-data validation, NLS calibration, optimization, Docker/CI and documentation | Done |

Detailed sprint acceptance criteria and risks live in [`roadmap.md`](roadmap.md).

---

## 9. Success criteria and acceptance

The project is considered complete when:

1. All five functional requirement groups (`RF-01` → `RF-05`) are implemented
   and covered by tests.
2. The four non-functional requirements (`RNF-01` → `RNF-04`) are met.
3. Test coverage is at least **80 %** over `src/athlete_stress_sim/core`.
4. ODE simulation runs in less than **0.5 seconds**.
5. The system is deployable with `docker compose up` and was used in a real
   training routine for at least **two weeks**.
6. The public `README.md` is written in English with mathematical explanations,
   architecture diagrams and real dashboard captures.
7. The calibration behavior is reported honestly: with the available real-data
   window, the quality gate may not be passed and the system falls back to the
   physiological priors.
8. The repository includes the MIT `LICENSE`, a `CHANGELOG.md`, contribution
   guidance (`CONTRIBUTING.md`) and a security policy (`SECURITY.md`).

---

## 10. Constraints, assumptions and risks

- **Single user.** The system is designed for user zero, not as a multi-tenant
  service.
- **Polar API dependency.** Availability and rate limits can delay ingestion;
  the catch-up sync is idempotent and retries with backoff.
- **Limited history.** The exercise listing covers the last 30 days; older
  sessions remain local but are not re-downloaded.
- **Calibration data.** A single noisy performance series may not satisfy the
  identifiability gate; priors are the safe fallback.
- **Combined load scale.** Running TRIMP and strength sRPE are summed in
  arbitrary units although they are not physiologically identical. Use the
  series for relative trends, not absolute cross-modality comparisons.
- **Not medical advice.** ACWR and freshness are monitoring signals, not
  diagnoses. They do not replace professional assessment.
- **Privacy.** The repository must never contain `.env` files, tokens, raw FIT
  files, the DuckDB database or unsanitized biometric screenshots.
- **Scope control.** Webhooks, other devices, multi-user support and report
  export remain outside `v1.0.0`.

---

## 11. Glossary

| Term | Meaning |
| --- | --- |
| **TRIMP** | Training impulse; internal load from heart-rate intensity and duration |
| **sRPE** | Session rating of perceived exertion (Borg CR-10) multiplied by duration |
| **HRR** | Heart-rate reserve; `(HR - HR_rest) / (HR_max - HR_rest)` |
| **AU** | Arbitrary units; relative internal-load scale |
| **ACWR** | Acute:chronic workload ratio |
| **EWMA** | Exponentially weighted moving average |
| **Fitness** | Slow-decaying positive adaptation component of the Banister model |
| **Fatigue** | Fast-decaying negative component of the Banister model |
| **Freshness / TSB** | Net balance `k1 · fitness − k2 · fatigue` |
| **EF** | Efficiency factor; speed divided by heart rate |
| **Decoupling** | Relative EF change between the two halves of a run |
| **Taper** | Planned load reduction before a race while preserving intensity |
| **NLS** | Calibration approach that fixes the time constants and estimates the gains; the resulting subproblem is a bounded ridge linear least-squares fit |
| **Ridge** | L2 regularization toward the prior parameter shape |
| **CV gate** | Acceptance test based on leave-one-out cross-validation |
| **Priors** | Reference physiological parameters used as fallback |
| **User zero** | The first and only real user of the system |

---

## 12. Related documents

- [`roadmap.md`](roadmap.md) — phases, sprints, acceptance criteria and risks.
- [`user-guide.md`](user-guide.md) — dashboard interpretation and endpoint reference.
- [`architecture.md`](architecture.md) — system design, data flows and technical debt.
- [`mathematical-model.md`](mathematical-model.md) — derivations, calibration and references.
- [`validation.md`](validation.md) — real-data validation, calibration diagnostics and performance.
- [`README.md`](../README.md) — public project overview and quick start.
- [`CONTRIBUTING.md`](../CONTRIBUTING.md) — development workflow and contribution guidelines.
- [`SECURITY.md`](../SECURITY.md) — security model, reporting and privacy expectations.
- [`CHANGELOG.md`](../CHANGELOG.md) — release history.
- [`LICENSE`](../LICENSE) — MIT license.

> The technical deep dives live under `docs/` and are linked from the public
> README.
