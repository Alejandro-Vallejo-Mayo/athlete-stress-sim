# Validation Report — Athlete Stress Sim

> **Document version:** 1.2.0 · **Product version:** 1.0.0 · **Status:** Final · **Last updated:** 2026-11-19
>
> **Scope:** technical and real-data validation of the `v1.0.0` implementation.
> This report covers ingestion, storage, metric computation, calibration, API
> behavior, dashboard data flow, taper/race-prediction plumbing, performance and
> quality gates.
>
> **Not a clinical validation.** The project is a personal monitoring and
> planning tool. It does not claim to prevent injuries, diagnose overtraining or
> predict race performance with clinical accuracy.

---

## Table of contents

1. [Validation questions](#1-validation-questions)
2. [Validation method](#2-validation-method)
3. [Data snapshot](#3-data-snapshot)
4. [Data quality and coverage](#4-data-quality-and-coverage)
5. [Calibration results](#5-calibration-results)
6. [Metric and feature validation](#6-metric-and-feature-validation)
7. [Performance benchmarks](#7-performance-benchmarks)
8. [Quality gates](#8-quality-gates)
9. [Deployment validation](#9-deployment-validation)
10. [Threats to validity](#10-threats-to-validity)
11. [What this report does and does not establish](#11-what-this-report-does-and-does-not-establish)
12. [Reproducibility](#12-reproducibility)
13. [Conclusion](#13-conclusion)
14. [Related documents](#14-related-documents)

---

## 1. Validation questions

The validation work answers the following questions:

1. **Ingestion:** can the system download, parse and persist real Polar sessions
   end to end?
2. **Coverage:** are the three activity families (running, strength and
   elliptical) handled by the correct load path?
3. **Metrics:** do the ACWR, fitness-fatigue, decoupling, taper and race
   prediction paths run on the real history and return interpretable outputs?
4. **Calibration:** does the quality gate behave as designed when real
   observations are limited or noisy?
5. **Performance:** are the dashboard/API and ODE simulation within the project's
   latency targets?
6. **Quality:** do lint, typing, tests and coverage pass the CI definition of
   done?
7. **Deployment:** is the container topology valid and reproducible?
8. **Honesty:** are failed or weak validations reported as such, rather than
   hidden by optimistic claims?

---

## 2. Validation method

The report uses three complementary methods.

### 2.1 Real-data replay

The local DuckDB file `data/athleta.duckdb` was used as the source of truth. The
same code paths used by the API were exercised:

- `SessionStore` for persisted exercises and samples;
- `_load_session_data`, `_assemble_daily_loads`, `_calibration` and
  `impulse_response` for the metrics pipeline;
- `running_baseline` and `build_taper_sessions` for planning;
- `select_best_efforts` and `predict_race` for race prediction.

Only aggregate counts and model diagnostics are reported. Raw FIT files,
heart-rate traces, pace traces and the local `.env` are not reproduced.

### 2.2 Performance measurement

A local Uvicorn server was started with `POLAR_SYNC_ON_STARTUP=false` and the
metric endpoints were timed with repeated HTTP requests. The first request to an
endpoint includes the initial snapshot load; later requests reuse the revision
cache. The 3,650-day ODE recurrence was also timed directly.

These are **single-user local measurements**, not a load test or a production
SLA. They are useful because the intended deployment is one athlete on one
machine.

### 2.3 Quality gates

The CI definition of done was executed locally:

```bash
make lint
make typecheck
make test-cov
```

The coverage gate is 80 % branch coverage over `src/athlete_stress_sim/core`.
Docker Compose configuration was validated with `docker compose config`.

---

## 3. Data snapshot

**Snapshot date:** 2026-11-13.

| Field | Value |
| --- | --- |
| Persisted sessions | 31 |
| Date range | 2026-10-03 → 2026-11-12 |
| Calendar span | 41 days |
| Days with at least one session | 30 |
| Rest days in the series | 11 |
| Persisted telemetry samples | 93,011 |
| Sessions with samples | 31 / 31 |

### 3.1 Session composition

| Activity family | Sessions | Load path |
| --- | ---: | --- |
| Running | 17 | Banister TRIMP from heart-rate samples |
| Strength | 13 | Foster session-RPE |
| Elliptical | 1 | Banister TRIMP from heart-rate samples; excluded from running-only metrics |
| Other | 0 | No session in this snapshot |
| **Total** | **31** | |

This snapshot is an extension of the S14 validation window. At S14 close, the
reported set was 14 running sessions + 11 gym sessions through 2026-11-03. The
final snapshot used here adds later sessions and one elliptical session, bringing
the calibration observation count to 16.

---

## 4. Data quality and coverage

### 4.1 Strength RPE coverage

| Metric | Value |
| --- | ---: |
| Strength sessions | 13 |
| Strength sessions with RPE | 13 |
| Strength sessions without RPE | 0 |
| RPE coverage | 100 % |

All strength sessions in the snapshot contribute load. The **RPE pending**
workflow is therefore not exercised by missing real RPE in the final dataset,
but it remains covered by automated tests.

### 4.2 Daily load coverage

| Metric | Value |
| --- | ---: |
| Days in the daily series | 41 |
| Days with load | 30 |
| Days with zero load (rest) | 11 |
| Sessions without computable load | 0 |

The daily series is contiguous and includes explicit rest days, so the
fitness-fatigue model can decay between sessions.

### 4.3 Activity separation

- Running sessions feed Banister TRIMP, ACWR, the fitness-fatigue model,
  decoupling, the running baseline and race prediction.
- Strength sessions feed session-RPE and the combined daily load.
- The single elliptical session feeds daily load, ACWR and Banister but is
  excluded from running-only paths. The `/exercises?kind=elliptical` filter and
  the running-only selectors are covered by tests.

---

## 5. Calibration results

The calibration pipeline was executed on the real snapshot with the active local
physiological priors.

| Diagnostic | Value |
| --- | --- |
| Observations | 16 |
| Minimum required | 8 |
| Calibrated | **False** |
| In-sample `R²` | 0.026 |
| Minimum `R²` | 0.1 |
| CV RMSE, calibrated fit | 0.1428 |
| CV RMSE, prior baseline | 0.1993 |
| Relative CV improvement | 28.3 % |
| Minimum CV improvement | 5 % |
| Effective parameters | Configured priors (fallback) |

### 5.1 Interpretation

The fit **improved cross-validated RMSE by 28.3 %**, but it failed the
in-sample `R²` gate (`0.026 < 0.1`). The production policy therefore rejected the
calibration and returned the configured priors.

This is the expected and desired behavior:

- the observation series is short and noisy;
- a model that improves one validation metric while explaining little in-sample
  variance is not trusted;
- the dashboard reports prior-based projections instead of presenting a fragile
  fit as personalized.

The result is consistent with the identifiability concerns documented in the
[mathematical model](mathematical-model.md): the gains and time constants are
not reliably identifiable from a few weeks of data. The final system keeps the
time constants fixed and requires both in-sample and out-of-sample evidence
before accepting a calibration.

### 5.2 What would change the outcome

The calibration could pass with:

- more observations across a longer training block;
- more variation in performance and load;
- cleaner efficiency-factor observations;
- a stable heart-rate/pace relationship.

No threshold was relaxed to force a pass. The prior fallback is an explicit
feature, not a workaround hidden from the user.

---

## 6. Metric and feature validation

### 6.1 ACWR

The ACWR series was computed over the full 41-day daily load series. At the final
snapshot date:

| Field | Value |
| --- | --- |
| Latest ACWR | 0.94 |
| Zone | Sweet spot |
| Acute EWMA | 110.49 AU |
| Chronic EWMA | 117.57 AU |

The result is plausible for the period: recent load is close to the chronic
baseline. The value is reported only as a sanity check, not as an injury-risk
prediction. The early-series EWMA transient is visible in the data and is
documented as a limitation.

### 6.2 Fitness-fatigue and readiness

- The exact Banister recurrence runs over the 41-day series.
- The dashboard receives fitness, fatigue, performance and freshness and renders
  the Today/Trends panels.
- Readiness uses the percentile of the latest freshness over the available
  history, with the documented absolute-threshold fallback.
- The calibration fallback is visible through `/metrics/calibration`; the
  dashboard labels the projection as prior-based.

### 6.3 Aerobic decoupling

| Metric | Value |
| --- | ---: |
| Running sessions | 17 |
| Runs with computable decoupling | 16 |
| Runs without enough data | 1 |

The decoupling endpoint and panel work on real telemetry. Sixteen runs had at
least two kilometers with valid speed and heart-rate samples; one did not. The
UI reports the unavailable case explicitly instead of inventing a value.

### 6.4 Taper planning

A race-taper plan was generated from the recent running baseline for a
2026-12-13 race date:

| Field | Value |
| --- | --- |
| Planned sessions | 8 |
| Taper weeks | 3 |
| Weekly factors | 0.75, 0.55, 0.35 |
| Last planned session | 2026-12-10 |
| Session on or after race day | None |

The plan preserves pace and RPE, places sessions on the preferred weekdays and
projects the fitness-fatigue model through race morning. The plan models running
only; gym sessions are intentionally not reduced by this endpoint.

### 6.5 Race prediction

| Field | Value |
| --- | --- |
| Detected best efforts | 4 |
| Reference distances | 1, 3, 5, 10 km |
| Effort tiers | moderate, hard, moderate, moderate |
| Half-marathon model | Riegel |
| Half-marathon confidence | Low |
| Estimate produced | Yes |

The predictor produced an estimate, but it correctly reported **low confidence**
because the available references are not half-marathon or race efforts. No
half-marathon or marathon reference exists in this snapshot. This is a useful
negative validation: the confidence system does not pretend that a 10 km moderate
effort is a strong half-marathon anchor.

### 6.6 Dashboard data flow

The real-use phase exercised the dashboard, and this validation re-ran the API
paths behind it. The frontend test suite covers the callbacks and display states:

- initial load of the Today/Trends panels;
- Refresh with a sync attempt and local fallback;
- RPE modal and session editor flows through the API;
- decoupling run selector;
- What-if simulator and race-taper form paths;
- race-predictor request/response path;
- offline and empty-state handling.

The dashboard is a server-side consumer of the API; no browser-side DuckDB access
is involved.

---

## 7. Performance benchmarks

### 7.1 API latency

Measured on 2026-11-13 with a local Uvicorn process on `127.0.0.1:8010`, using
repeated `curl` requests. Values are wall-clock request times.

| Endpoint | First request (cold) | Subsequent requests (warm) |
| --- | ---: | ---: |
| `/health` | 1.7 ms | 1.4–1.5 ms |
| `/metrics/banister` | 335 ms | 60–70 ms |
| `/metrics/acwr` | 27 ms | 26–33 ms |
| `/metrics/calibration` | 61 ms | 58–61 ms |
| `/metrics/running-baseline` | 21 ms | 18–20 ms |

The cold `/metrics/banister` request includes the initial snapshot load. The warm
path reuses the revision-keyed cache and is substantially faster.

### 7.2 Dashboard

The S15 end-to-end measurement reduced the warm dashboard load from approximately
**5.5 s to ~0.32 s**. The current API benchmark is consistent with that result:
the dashboard performs several API calls and rendering work in addition to the
individual endpoint timings.

### 7.3 ODE simulation

A 3,650-day impulse response (ten years of daily load) was timed directly:

| Run | Time |
| --- | ---: |
| 1 | 1.08 ms |
| 2 | 0.89 ms |
| 3 | 0.65 ms |

The result is well below the **0.5 s** requirement (`RNF-02`). The numerical
`solve_ivp` cross-check is also covered by tests.

### 7.4 Benchmark caveats

- Single-user, local machine; no concurrent users.
- The process was already warm after the first call.
- The frontend rendering time depends on the browser and screen.
- These numbers are evidence of fitness for the intended deployment, not a
  capacity or stress test.

---

## 8. Quality gates

The local CI definition of done was executed on 2026-11-13.

| Gate | Result |
| --- | --- |
| `make lint` | Passed; ruff check and format clean |
| `make typecheck` | Passed; mypy strict on 57 source files |
| `make test-cov` | 322 tests passed |
| Core branch coverage | **93.81 %** |
| Coverage threshold | 80 % |

Coverage is intentionally measured over `src/athlete_stress_sim/core` only.
Backend routers, frontend components and the Dash app are exercised by tests but
are outside the enforced coverage source.

The suite covers:

- ETL parsing, normalization and sport classification;
- Polar OAuth and AccessLink retries with injected transports;
- DuckDB stores with temporary databases;
- TRIMP, sRPE, ACWR, Banister, calibration, decoupling, taper and race
  prediction;
- API contracts and status codes;
- frontend panels, callbacks and offline/empty states;
- performance smoke tests for the ODE path.

---

## 9. Deployment validation

### 9.1 Docker Compose

`docker compose -f docker/docker-compose.yml config` validates the Compose file.
The topology is:

- backend on port 8000 with the `data/` volume and an optional `.env`;
- frontend on port 8050 with `API_URL=http://backend:8000`;
- backend healthcheck against `/health`;
- frontend `depends_on` the healthy backend.

The runtime images were cold-built during S15 and started with both a real
database and an empty database. Images contain runtime dependencies only; data,
raw FIT files and secrets are not baked into them.

### 9.2 CI

The GitHub Actions workflow runs:

```text
uv sync --all-groups --frozen
make lint
make typecheck
make test-cov
```

The local equivalent passed. The remote GitHub run should be confirmed after the
release push; this report does not claim a remote run that has not been observed.

---

## 10. Threats to validity

### 10.1 Internal validity

- **Single athlete, single device.** The data comes from one Polar Ignite and one
  training routine. Results do not generalize to other athletes, devices or
  sports.
- **Short history.** The 41-day window is enough to exercise the pipeline, not
  enough to estimate stable physiological parameters.
- **No ground truth.** There are no injury labels, laboratory measurements or
  criterion race results. The report validates internal consistency and
  behavior, not physiological truth.
- **Measurement error.** Heart rate, maximal heart rate, resting heart rate and
  RPE are estimates. Errors propagate into TRIMP, EF, calibration and prediction.
- **Autocorrelation.** Training and performance observations are a time series;
  leave-one-out CV is not a temporal validation scheme.

### 10.2 External validity

- The calibration gate is a heuristic, not a clinical decision rule.
- ACWR does not include sleep, stress, terrain, previous injury or recovery
  quality.
- The taper factors are a fixed heuristic, not an optimized prescription.
- Race prediction is an extrapolation, especially when the reference and target
  distances differ greatly.
- The combined TRIMP/sRPE scale is a practical simplification across training
  modes.

### 10.3 Construct validity

- **Freshness** is a model quantity in arbitrary units, not a direct measurement
  of recovery.
- **Readiness** is a relative percentile, not a medical clearance.
- **Low confidence** in race prediction is meaningful only relative to the
  predictor's own tiers; it is not a calibrated probability.
- The dashboard is a decision aid, not an autonomous coach.

---

## 11. What this report does and does not establish

**Establishes**

- The end-to-end ingestion and persistence path works on real Polar data.
- Running, strength and elliptical sessions follow the intended load paths.
- The metric, taper and prediction pipelines run on the real history and return
  the documented response shapes.
- Calibration fails safely to priors when the quality gate is not met.
- API latency and ODE runtime are within the project's targets for a single-user
  local deployment.
- Lint, typing, tests and coverage pass locally.
- Docker Compose configuration is valid and the intended topology is coherent.

**Does not establish**

- That the model prevents injuries or overtraining.
- That the calibrated parameters are physiologically true.
- That ACWR or freshness predict injury for this or any other athlete.
- That race predictions are accurate on race day.
- That the system is ready for multi-user, public or clinical deployment.
- That the remote GitHub Actions run is green until it is observed after a push.

---

## 12. Reproducibility

### 12.1 Quality and coverage

```bash
make lint
make typecheck
make test-cov
```

### 12.2 API benchmark

```bash
POLAR_SYNC_ON_STARTUP=false \
  uv run uvicorn athlete_stress_sim.backend.main:app \
  --host 127.0.0.1 --port 8010

curl -s -o /dev/null -w '%{time_total}\n' http://127.0.0.1:8010/metrics/banister
curl -s -o /dev/null -w '%{time_total}\n' http://127.0.0.1:8010/metrics/acwr
curl -s -o /dev/null -w '%{time_total}\n' http://127.0.0.1:8010/metrics/calibration
```

### 12.3 Docker configuration

```bash
docker compose -f docker/docker-compose.yml config
```

### 12.4 Data hygiene

The validation used the local `data/athleta.duckdb` file. Raw FIT files and the
database are git-ignored and were not committed. The report contains aggregate
counts and derived diagnostics only; it does not reproduce biometric traces,
credentials or the local `.env`.

---

## 13. Conclusion

Athlete Stress Sim is validated as an **end-to-end personal training-load
platform** on a real 41-day dataset:

- ingestion, parsing and persistence work;
- all three activity families follow the correct load paths;
- the metrics, taper and race-prediction paths execute on real data;
- the calibration gate correctly rejects an unstable fit and falls back to
  priors;
- the API and ODE engine meet the project's latency targets;
- lint, typing, 322 tests and 93.81 % core coverage pass locally;
- the Docker Compose topology is coherent.

The most important validation result is deliberately conservative: with 16 real
observations, the calibration improves cross-validated RMSE but does not explain
enough in-sample variance, so the system does **not** pretend to be calibrated.
This is the intended behavior for a personal tool built on limited, noisy data.

The release documentation, dashboard captures, secret review and
license/changelog are complete. The only remaining step is the `v1.0.0` tag after
the final push and CI confirmation.

---

## 14. Related documents

- [`product-requirements.md`](product-requirements.md) — requirements and acceptance criteria.
- [`roadmap.md`](roadmap.md) — delivery history and validation context.
- [`architecture.md`](architecture.md) — runtime topology, caching and failure modes.
- [`mathematical-model.md`](mathematical-model.md) — model definitions, calibration gate and limitations.
- [`user-guide.md`](user-guide.md) — dashboard interpretation and troubleshooting.
- [`README.md`](../README.md) — public overview and quick start.
- [`CONTRIBUTING.md`](../CONTRIBUTING.md) — development workflow and contribution guidelines.
- [`SECURITY.md`](../SECURITY.md) — security model, reporting and privacy expectations.
- [`CHANGELOG.md`](../CHANGELOG.md) — release history.
- [`LICENSE`](../LICENSE) — MIT license.
