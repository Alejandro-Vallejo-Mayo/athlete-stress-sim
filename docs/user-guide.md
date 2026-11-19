# User Guide — Dashboard and Metric Interpretation

> **Document version:** 1.2.0 · **Product version:** 1.0.0 · **Status:** Final · **Last updated:** 2026-11-19
>
> This guide explains what Athlete Stress Sim calculates, what each dashboard
> panel represents and how to read its charts. It is written for using the
> application, not for replacing the [PRD](product-requirements.md) (product
> contract), the [roadmap](roadmap.md) (historical delivery record) or the
> canonical [mathematical model](mathematical-model.md).
>
> **This is not medical advice.** The metrics are estimates of internal load and
> fatigue. Use them to detect trends, not to diagnose injuries or replace a
> professional assessment.

---

## Table of contents

1. [What the application does](#1-what-the-application-does)
2. [Quick start](#2-quick-start)
3. [Sync, RPE and data corrections](#3-sync-rpe-and-data-corrections)
4. [Dashboard map](#4-dashboard-map)
5. [Today](#5-today)
6. [Trends](#6-trends)
7. [Plan](#7-plan)
8. [Metric definitions and formulas](#8-metric-definitions-and-formulas)
9. [Configuration reference](#9-configuration-reference)
10. [API endpoints](#10-api-endpoints)
11. [Troubleshooting](#11-troubleshooting)
12. [Limitations and interpretation](#12-limitations-and-interpretation)

---

## 1. What the application does

Athlete Stress Sim turns Polar training sessions into a daily load series and
uses that series to estimate fitness, fatigue and overload risk:

```text
Polar AccessLink
      │  FIT download
      ▼
Local DuckDB (exercises, samples, session_rpe)
      │
      ├─ Running / elliptical → Banister TRIMP (heart rate)
      └─ Strength             → Foster session-RPE
      │
      ▼
Daily load (sum per day; rest days = 0)
      │
      ├─ ACWR (7-day acute / 28-day chronic EWMA)
      └─ Banister model (fitness, fatigue, freshness)
      │
      ▼
FastAPI → Dash/Mantine dashboard
```

- **Running:** load is calculated with Banister TRIMP integrated over the
  second-by-second heart-rate series.
- **Elliptical:** also uses heart-rate TRIMP, so it contributes to daily load,
  ACWR and the fitness-fatigue model. It is excluded from running-specific
  metrics (baseline, taper, decoupling and race prediction) because pace and
  distance are not directly comparable.
- **Strength/gym:** load is calculated with Foster session-RPE,
  `RPE × duration_min`. The session must have an RPE to contribute load.
- **Daily load:** all sessions on the same day are summed. Days without a
  session between the first and last recorded dates are filled with `0` so
  fatigue can decay.
- **Units:** both load types are expressed in arbitrary units (AU) and treated
  as a common scale. They are not physiologically identical; use them to compare
  trends, not the absolute value of a strength session against a run.
- **Privacy:** all biometric data stays in the local DuckDB file. The
  application does not share training data with third parties; the only external
  service is the Polar AccessLink API used for ingestion. See
  [`SECURITY.md`](../SECURITY.md) for the deployment security model.

---

## 2. Quick start

### Prerequisites

- Python 3.12 (3.11 is also allowed by the package metadata).
- [`uv`](https://docs.astral.sh/uv/) installed.
- A Polar AccessLink client (client id and secret).
- Docker is optional for the containerized deployment.

### Local development

```bash
make install          # uv sync --all-groups + pre-commit hooks
cp .env.example .env  # then fill in the Polar credentials
make run-backend      # API at http://localhost:8000 (docs at /docs)
make run-frontend     # dashboard at http://localhost:8050
```

Open <http://localhost:8050> for the dashboard and
<http://localhost:8000/docs> for the interactive API documentation.

### Polar AccessLink setup

1. Create an AccessLink client at
   <https://admin.polaraccesslink.com/>.
2. Register a redirect URI that matches `POLAR_REDIRECT_URI` exactly. The
   default is `http://localhost:8000/auth/callback`.
3. Put `POLAR_CLIENT_ID` and `POLAR_CLIENT_SECRET` in `.env`.
4. Start the backend and open `GET /auth/login` to link the account.
5. Press **Refresh** in the dashboard, or call `POST /sync`, to run the first
   catch-up sync.

The catch-up sync is idempotent: sessions already downloaded are not downloaded
again. Polar's exercise listing covers the last 30 days; older sessions remain
in DuckDB but are not re-downloaded.

### Docker

```bash
make docker-up     # build and start backend + frontend
make docker-logs   # follow the logs
make docker-down   # stop the services
```

The dashboard is available at <http://localhost:8050> and the API at
<http://localhost:8000>. Docker Compose reads `.env` when present and mounts the
local `data/` directory.

### Useful commands

| Command | Purpose |
| --- | --- |
| `make lint` | Run ruff and check formatting |
| `make format` | Auto-fix and format the code |
| `make typecheck` | Run mypy |
| `make test` | Run the test suite |
| `make test-cov` | Run tests with the 80 % core-coverage gate |
| `make db` | Open an interactive DuckDB shell (`con`) |
| `make clean` | Remove caches and build artifacts |

---

## 3. Sync, RPE and data corrections

### Refresh and sync

The **Refresh** button in the header does two things:

1. Calls `POST /sync` to download and parse new Polar sessions.
2. Reloads all dashboard metrics from the local database.

The header shows a short result such as `Synced +2 · parsed 2`. If the sync
cannot reach Polar, it shows `Sync failed.` and the dashboard still reloads using
the local data. Sync failures do not delete or invalidate existing sessions.

At backend startup, a catch-up sync also runs when
`POLAR_SYNC_ON_STARTUP=true`.

### Recording strength RPE

Strength sessions need a session RPE on the Borg CR-10 scale (0–10) to contribute
load. The dashboard surfaces this in two places:

- the orange **RPE pending** button in the header;
- the **Gym RPE** card in the **Today** tab.

Both open the **Update gym RPE** modal:

1. Select the pending gym session.
2. Enter an RPE between 0 and 10 (step 0.5).
3. Use **Save & next** to keep the modal open for the next session or
   **Save & close** to save and reload the metrics.

Sessions without RPE are excluded from load and ACWR. If you add a missing RPE,
the daily load, fitness-fatigue curves, ACWR and readiness can change.

### Correcting session data

The **Session data** card in the **Today** tab opens a manual editor. Select a
session and correct:

- start time;
- distance (km);
- duration (minutes);
- average heart rate (bpm);
- maximum heart rate (bpm).

Use **Save changes** to persist the correction and reload the dashboard. This is
useful when a FIT file has missing or inconsistent metadata.

---

## 4. Dashboard map

The application uses three top-level tabs. The interface labels are in English,
and this guide uses the same names so you can locate them on screen.

| Area | Content | Purpose |
| --- | --- | --- |
| Header | Title, **RPE pending**, sync status, **Refresh** | Refresh Polar data, reload metrics and complete pending RPE. |
| **Today** | Daily status, Load risk, At a glance, Freshness trend, Gym RPE, Session data | Daily readiness, ACWR and data hygiene. |
| **Trends** | Training load, Aerobic decoupling, Recent sessions | Historical model behavior, run efficiency and session review. |
| **Plan** | Race taper, What-if, Race predictor | Plan the final weeks and estimate race potential. |

The **Plan** tab opens on **Race taper** by default; **What-if** and **Race
predictor** are nested pills inside it.

---

## 5. Today

### 5.1 Daily status

The **Daily status** card shows a readiness traffic light, the current freshness
and, when enough history exists, the percentile of the current freshness in the
recent distribution.

| Color | Level | Condition |
| --- | --- | --- |
| Green | **Ready** | Current freshness `>= P50` of the last 90 days |
| Yellow | **Caution** | Between `P15` and `P50` |
| Red | **Rest** | `< P15` |
| Gray | No data | No training history yet |

With fewer than 14 days of history, absolute thresholds are used instead:

- `freshness >= 0` → ready;
- `-5 <= freshness < 0` → caution;
- `freshness < -5` → rest.

The card also shows `Freshness: +X.X AU` and, when available,
`Recent percentile: Pxx`. A negative freshness immediately after a hard session
is normal: fatigue rises quickly and decays faster than fitness. Focus on the
trend and recovery time, not on a single value.

### 5.2 Load risk (ACWR)

The **Load risk** card shows the latest ACWR value, its risk zone and the acute
and chronic components:

```text
Acute 7d   = EWMA of daily load with a 7-day window
Chronic 28d = EWMA of daily load with a 28-day window
Ratio      = acute / chronic
```

| Zone | ACWR | Meaning |
| --- | --- | --- |
| **Undertraining** (blue) | `< 0.8` | Recent load is low relative to history; possible deconditioning or taper. |
| **Sweet spot** (green) | `0.8 – 1.3` | Considered a safe progression range. |
| **Warning** (yellow) | `> 1.3 – 1.5` | Load increase to monitor. |
| **Danger** (red) | `> 1.5` | Load spike; elevated overuse-risk signal. |

The strip is normally drawn from `0` to `2.0`. If the ratio is higher, the axis
extends and the numeric value remains visible. The EWMA starts from the first
load value, so the first days are close to `1.0` and converge as history
accumulates. Wait for several weeks (ideally around 28 days) before reading the
ratio as a stable signal.

### 5.3 At a glance

The **At a glance** card summarizes four values:

- **Freshness** — current net balance and its 7-day change.
- **ACWR** — current ratio and risk zone.
- **Fitness** — current fitness component and its 7-day change.
- **Fatigue** — current fatigue component and its 7-day change.

The 7-day delta is shown only when enough history exists; otherwise the card
shows `7d —`.

### 5.4 Freshness trend

The **Freshness trend** card is a compact sparkline with a zero line:

- **Above zero:** freshness is positive; the athlete is relatively fresh.
- **Below zero:** fatigue dominates; this is expected after hard sessions.
- **Rest days:** load is `0`, so the curve decays instead of staying flat.

The full fitness, fatigue and freshness history is in the **Trends** tab.

### 5.5 Gym RPE

The **Gym RPE** card reports how many gym sessions still need an RPE. If none are
pending, it says that all gym sessions have RPE logged. If some are pending, the
**Review RPE** button opens the same modal as the header.

### 5.6 Session data

The **Session data** card lets you select any session and correct its date,
distance, duration or heart-rate fields. The editor is a data-quality tool, not a
way to rewrite the physiological model: corrected metadata immediately changes
the load and downstream metrics.

---

## 6. Trends

### 6.1 Training load

The **Training load** chart shows three daily series:

| Line | Color | Meaning |
| --- | --- | --- |
| **Fitness** | Blue | Slow-decaying positive adaptation; rises with load and decays slowly. |
| **Fatigue** | Red | Fast-decaying negative component; rises with load and decays quickly. |
| **Freshness (TSB)** | Green | Net balance `k1 · fitness − k2 · fatigue`; positive means prepared. |

Use the **30d**, **90d**, **180d**, **1y** and **All** buttons to change the
window. The current values are also shown as chips above the chart.

Typical patterns:

- **Load block:** fatigue rises faster than fitness, freshness falls, then
  recovers when load decreases. This is the expected functional-overload
  response.
- **Taper:** when load drops, fatigue falls before fitness; freshness rises while
  fitness is preserved. This is the signal the taper tools target.
- **Prolonged rest:** both curves fall; freshness may rise, but fitness is also
  lost.
- **Rest days:** inserted as load `0`, so the curves decay.

The y-axis is in AU. Compare shapes and trends, not absolute values between
athletes. The model also exposes `performance`, but the dashboard does not plot
it.

> The dashboard calibrates the model gains from observed running performance
> (efficiency factor per run). To avoid the model's identifiability problem, the
> time constants `tau1` and `tau2` stay **fixed at the priors** and only `p0`,
> `k1` and `k2` are estimated with bounded least squares and a ridge penalty
> toward the prior shape. The fit is accepted only when it explains enough
> in-sample variance **and** improves leave-one-out cross-validation RMSE over
> the prior-shaped baseline. Otherwise the configured priors are used. Check the
> result at `GET /metrics/calibration`; the old `/metrics/ekf` endpoint remains
> available as a deprecated alias.

### 6.2 Aerobic decoupling

The **Aerobic decoupling** panel analyzes one selected run. The efficiency factor
is:

```text
EF_km = sum speed in m/s / sum heart rate in bpm
```

With equal sample counts this is the ratio of mean speed to mean heart rate.
Higher EF means more speed at the same heart rate. The bar chart shows EF per
kilometer and a dotted mean reference line.

The summary compares the two halves of the run:

```text
decoupling = (EF_first_half − EF_second_half) / EF_first_half × 100
```

- **Positive:** EF fell in the second half; cardiovascular drift (same heart
  rate, lower speed). Possible causes include fatigue, dehydration, heat, terrain
  or limited durability.
- **Near zero:** stable efficiency throughout the run.
- **Negative:** EF rose in the second half; common when warming up or pacing more
  evenly.

The UI colors the result green at `<= 5 %`, yellow between `5 %` and `10 %`, and
red above `10 %`. These are orientation bands, not medical thresholds; context
(heat, hydration, elevation, duration) matters more than a single number.
Decoupling requires at least **2 kilometers** with valid speed and heart-rate
data. The panel uses speed, not pace: a higher EF is always better.

### 6.3 Recent sessions

The **Recent sessions** card lists the latest runs and gym sessions with:

- date and activity type;
- distance, duration and average heart rate when available;
- an RPE badge (`RPE n`, `RPE pending` or `No RPE`).

Use **Review RPE** to open the pending-RPE modal. Gym sessions without RPE do not
contribute load.

---

## 7. Plan

### 7.1 Race taper

The **Race taper** panel generates a progressive pre-race plan. It opens by
default when you select the **Plan** tab.

1. Fill in **Race date**, **Weekly km**, **Runs/week**, **Pace (min/km)**,
   **RPE (0–10)** and **Taper weeks**.
2. Optionally press **Use recent baseline** to prefill the recent weekly volume,
   runs per week, pace and RPE; the taper defaults to three weeks. If no baseline
   is available, enter the values manually.
3. Press **Plan taper**.

The weekly volume decreases linearly while intensity (pace and RPE) is preserved:

- multi-week taper: factors from `0.75` to `0.35`;
- three-week taper: `0.75`, `0.55`, `0.35`;
- one-week taper: `0.5`.

The baseline is the last four weeks of running data and requires at least four
valid sessions. For a three-run week, sessions are placed on Tuesday, Thursday
and Sunday and never on or after race day, so race morning is a rest day in the
projection. The chart marks race day with a vertical line and shows the forecast
through race morning.

The plan models running only. Gym sessions are not reduced automatically; adjust
them separately if you want to model the complete taper.

### 7.2 What-if simulator

The **What-if** panel projects future sessions on top of the real history.

1. Fill in **Date**, **Distance (km)**, **Pace (min/km)** and **RPE (0–10)**.
2. Press **Add** to append the session to the planned list; **Clear** empties it.
3. Press **Simulate**.

**Use recent baseline** fills a typical session distance, pace and RPE from the
last four weeks; the date still has to be chosen manually. If no recent baseline
is available, enter the values manually. Planned session load is estimated as:

```text
duration_min = distance_km × pace_min_per_km
load = RPE × duration_min
```

This uses session-RPE for projected runs because future heart rate does not
exist. The chart uses:

- **solid line:** real history;
- **dashed line:** forecast from the planned sessions;
- **vertical dotted line:** boundary between history and forecast.

If there is no history, the entire chart is a forecast and the boundary is
omitted. The status line reports the projected number of days and the model used
(calibrated or priors). Add sessions up to the race to see whether freshness
turns positive on race morning.

### 7.3 Race predictor

The **Race predictor** estimates the time you could achieve at maximal effort.

1. Choose a **Race distance**: 5 km, 10 km, half marathon, marathon or
   **Custom**.
2. If you choose **Custom**, enter the distance in kilometers.
3. Press **Predict**.

The result shows:

- predicted time and pace;
- fast and slow bounds;
- model and confidence;
- explanatory notes;
- the efforts used, under **Efforts used**.

**Advanced model** lets you force **Auto (recommended)**, **Riegel**,
**Critical speed** or **HR extrapolation**, and adjust the Riegel exponent
(default `1.06`). Auto uses critical speed when possible, then Riegel, then
heart-rate extrapolation.

Candidate efforts are classified by relative heart-rate reserve (`%HRR`):

| Tier | %HRR | Use |
| --- | --- | --- |
| `race` | `>= 88 %` | Direct reference; high confidence |
| `hard` | `80 – 88 %` | Reference with medium confidence |
| `moderate` | `70 – 80 %` | Low-confidence reference only |
| `easy` | `< 70 %` | Not used as race pace; fitness/EF trend only |

The UI predicts from detected best efforts. The API also accepts a manual
`reference` (distance and time) for custom integrations. Easy running does not
make the prediction artificially slow because efforts are corrected by heart
rate and efficiency factor, not by raw pace.

> The prediction is a **potential**, not a guarantee for today. It does not
> subtract same-day fatigue. A real race or time trial substantially increases
> confidence.

---

## 8. Metric definitions and formulas

These are quick-reference formulas; the canonical definitions, assumptions and
references live in [`mathematical-model.md`](mathematical-model.md).

### 8.1 Banister TRIMP (running and elliptical)

$$
TRIMP = D \cdot HR_r \cdot a \cdot e^{b \cdot HR_r}
$$

where

$$
HR_r = \mathrm{clamp}\!\left(
\frac{HR - HR_{\text{rest}}}{HR_{\max} - HR_{\text{rest}}},
0, 1
\right)
$$

and the coefficients are:

- male: `a = 0.64`, `b = 1.92`;
- female: `a = 0.86`, `b = 1.67`.

`D` is the duration in minutes. The implementation integrates over the
second-by-second heart-rate series instead of using only the average heart rate.

### 8.2 Foster session-RPE (strength)

$$
TRIMP_{\text{gym}} = RPE \cdot D_{\min}
$$

`RPE` is the whole-session effort on the Borg CR-10 scale (0–10) and `D_min` is
the duration in minutes.

### 8.3 Daily load

Session loads are summed per calendar day. Days between the first and last
session are filled with `0.0`. Running TRIMP and strength sRPE share the same AU
scale; this is a practical simplification, not a claim of physiological
equivalence.

### 8.4 Banister fitness-fatigue model

$$
\frac{dg}{dt} = -\frac{g}{\tau_1} + w(t)
\qquad
\frac{dh}{dt} = -\frac{h}{\tau_2} + w(t)
$$

$$
P(t) = P_0 + k_1 g(t) - k_2 h(t)
$$

For daily loads:

$$
g_t = g_{t-1}e^{-1/\tau_1} + w_t
\qquad
h_t = h_{t-1}e^{-1/\tau_2} + w_t
$$

$$
Freshness_t = k_1 g_t - k_2 h_t
\qquad
Performance_t = P_0 + Freshness_t
$$

Default priors: `tau_1 = 42` days, `tau_2 = 7` days, `k_1 = 1.0`,
`k_2 = 2.0`, `P_0 = 0.0`.

### 8.5 Calibration gate

Calibration is attempted only when there are at least **8 observations**. The fit
is accepted only if:

- in-sample `R² >= 0.1`;
- leave-one-out cross-validation RMSE improves by at least **5 %** over the
  prior-shaped baseline;
- the gains are positive and `tau_1 > tau_2`.

Otherwise the physiological priors are used. This is why some dashboards show
prior-shaped curves even with real data.

### 8.6 ACWR

$$
EWMA_t = \lambda L_t + (1-\lambda) EWMA_{t-1},
\qquad
\lambda = \frac{2}{N+1}
$$

with `N = 7` for acute load and `N = 28` for chronic load:

$$
ACWR_t = \frac{EWMA_t^{\text{acute}}}{EWMA_t^{\text{chronic}}}
$$

### 8.7 Efficiency factor and decoupling

$$
EF_k = \frac{\sum_{i \in k} v_i}{\sum_{i \in k} HR_i}
$$

$$
\text{decoupling} =
\frac{\overline{EF}_{\text{first}} - \overline{EF}_{\text{second}}}
{\overline{EF}_{\text{first}}} \times 100
$$

`v` is speed in meters per second and `HR` is heart rate in bpm. With equal
sample counts, `EF_k` is the ratio of mean speed to mean heart rate.

### 8.8 Race prediction

Riegel:

$$
T_2 = T_1 \left(\frac{D_2}{D_1}\right)^k,
\qquad k \approx 1.06
$$

Critical speed:

$$
D = CS \cdot T + D'
$$

Efforts are adjusted by the Banister fitness change since their date and converted
to an equivalent race effort. Target race-level `%HRR` is approximately 93 % for
short races, 90 % for 10K, 88 % for the half marathon and 85 % for the marathon.

---

## 9. Configuration reference

Configuration uses environment variables with the `POLAR_` and `ATHLETE_`
prefixes, plus `API_URL` and `DASH_DEBUG` for the frontend. Copy `.env.example`
to `.env`; `.env` is git-ignored and must never be committed.

| Variable | Default | Purpose |
| --- | --- | --- |
| `POLAR_CLIENT_ID` | empty | Polar AccessLink client id (required for sync) |
| `POLAR_CLIENT_SECRET` | empty | Polar AccessLink client secret (required for sync) |
| `POLAR_REDIRECT_URI` | `http://localhost:8000/auth/callback` | Must match the URI registered in Polar |
| `POLAR_AUTHORIZE_URL` | Polar authorization endpoint | OAuth2 authorization URL |
| `POLAR_TOKEN_URL` | Polar token endpoint | OAuth2 token URL |
| `POLAR_API_URL` | `https://www.polaraccesslink.com/v3` | AccessLink API base URL |
| `POLAR_SCOPE` | `accesslink.read_all` | Requested OAuth2 scope |
| `POLAR_MEMBER_ID` | `athlete-stress-sim` | Partner member id used to register the user |
| `POLAR_SYNC_ON_STARTUP` | `true` | Run a catch-up sync when the backend starts |
| `ATHLETE_HR_MAX` | `200` | Maximum heart rate (bpm) |
| `ATHLETE_HR_REST` | `60` | Resting heart rate (bpm) |
| `ATHLETE_TAU_1` | `42.0` | Fitness time constant (days) |
| `ATHLETE_TAU_2` | `7.0` | Fatigue time constant (days) |
| `ATHLETE_K_1` | `1.0` | Fitness gain |
| `ATHLETE_K_2` | `2.0` | Fatigue gain |
| `ATHLETE_P0` | `0.0` | Baseline performance |
| `ATHLETE_SEX` | `male` | Selects the Banister TRIMP coefficients |
| `ATHLETE_DB_PATH` | `data/athleta.duckdb` | Local DuckDB database path |
| `ATHLETE_RAW_DATA_DIR` | `data/raw` | Directory for raw Polar files |
| `API_URL` | `http://localhost:8000` | Backend base URL used by the dashboard (Compose sets `http://backend:8000`) |
| `DASH_DEBUG` | `true` | Enable Dash debug mode; set `false` in containerized deployments |

> `.env.example` contains the user-zero reference values and matches the code
> defaults (`HR_max=200`, `HR_rest=60`, `tau_1=42`, `tau_2=7`). Adjust them to
> your own physiology.

---

## 10. API endpoints

The dashboard uses the same API. Interactive documentation is available at
`http://localhost:8000/docs`.

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Backend liveness |
| `GET` | `/config/physiology` | Active physiological constants (no credentials) |
| `GET` | `/auth/login` | Start the Polar OAuth2 flow |
| `GET` | `/auth/callback` | OAuth2 callback |
| `GET` | `/auth/status` | Polar account link status |
| `GET` | `/auth/refresh` | Refresh the access token |
| `POST` | `/sync` | Download and parse new Polar sessions |
| `GET` | `/sync/status` | Ingestion counters and parsed sessions |
| `GET` | `/exercises?kind=all\|run\|gym\|elliptical` | List sessions |
| `GET` | `/exercises/{id}` | Read one session |
| `POST` | `/exercises/{id}/rpe` | Record a strength-session RPE |
| `PATCH` | `/exercises/{id}` | Correct session metadata |
| `GET` | `/metrics/trimp/{id}` | Internal load of one session |
| `GET` | `/metrics/acwr` | Daily ACWR series and zones |
| `GET` | `/metrics/banister` | Daily fitness, fatigue, performance and freshness |
| `GET` | `/metrics/calibration` | Calibrated Banister gains and validation diagnostics |
| `GET` | `/metrics/ekf` | Deprecated alias of `/metrics/calibration` |
| `GET` | `/metrics/running-baseline` | Recent weekly volume, pace and RPE |
| `GET` | `/metrics/decoupling/{id}` | EF per kilometer and decoupling for a run |
| `GET` | `/metrics/best-efforts` | Best efforts with `%HRR` and EF |
| `POST` | `/metrics/race-prediction` | Predict a race time |
| `POST` | `/simulate` | Simulate an arbitrary daily-load series |
| `POST` | `/simulate/taper` | Project planned sessions over the history |
| `POST` | `/simulate/taper/plan` | Generate a progressive race-taper plan |

---

## 11. Troubleshooting

| Symptom | Likely cause | Action |
| --- | --- | --- |
| **Backend offline** | The API is not running or `API_URL` is wrong | Start the backend with `make run-backend`; in Docker, check `make docker-logs` |
| **Sync failed.** | Polar token expired, no network, or invalid credentials | Open `/auth/status`, re-link with `/auth/login`, check `.env`, then Refresh again |
| **No training history yet** | The database has no sessions | Run `POST /sync` or press Refresh |
| **No data yet** in a panel | That metric has no valid samples (e.g. no heart rate or no run) | Sync more sessions or check the session data |
| **RPE pending** | Strength sessions are missing an RPE | Open the modal and save an RPE for each session |
| **ACWR near 1.0** at the start | EWMA is seeded with the first load value | Wait for several weeks of history before interpreting the ratio |
| **Calibration not active** | Fewer than 8 observations or the CV gate failed | Check `GET /metrics/calibration`; the priors are being used |
| **Not enough data to compute decoupling** | Fewer than 2 kilometers with valid speed and heart rate | Choose a longer run or check the telemetry |
| **Low-confidence race prediction** | Only easy efforts are available | Add a race/time trial through the API or run a harder effort |
| **Use recent baseline does nothing** | Fewer than 4 valid running sessions in the last 4 weeks | Enter the baseline values manually or sync more runs |
| **Docker build looks frozen** | First image build downloads dependencies | Wait; follow progress with `make docker-logs` |

---

## 12. Limitations and interpretation

- **Only sessions with calculable load count.** A strength session without RPE,
  or a run/elliptical session without heart-rate samples, contributes no load and
  can make ACWR and the curves underestimate real training.
- **Elliptical is global load, not running.** It contributes to ACWR and
  Banister but does not appear in the decoupling selector, running baseline,
  race prediction or taper plan.
- **Polar history is limited.** The client lists exercises from the last 30 days;
  already downloaded sessions stay in DuckDB. The first sync does not rebuild
  months of history.
- **Calibration depends on data quantity and quality.** With few weeks, observed
  performance barely varies and the fit may not pass the R² and
  cross-validation gates; the dashboard then uses the priors. Check
  `/metrics/calibration` to see whether calibration is active and how much it
  improves.
- **Race prediction is a potential**, not a guarantee. It depends on the quality
  of the references (tests/races), the `%HRR` of the efforts and distance
  extrapolation. Training segments are not equivalent to a full race effort.
- **The taper plan models running only.** It assumes training between today and
  the start of the taper follows the history; it does not reduce gym sessions
  automatically.
- **The combined load scale is a simplification.** Running TRIMP and strength
  sRPE are summed in AU even though they are not physiologically equivalent.
- **ACWR and freshness are signals, not diagnoses.** High or low values should
  be checked against how you feel, training context and several weeks of trend.
- **Refresh depends on Polar connectivity.** If the token has expired or there is
  no network, sync fails but local metrics remain available.
