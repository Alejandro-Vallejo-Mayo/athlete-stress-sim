# Mathematical Model — Athlete Stress Sim

> **Document version:** 1.2.0 · **Product version:** 1.0.0 · **Status:** Final · **Last updated:** 2026-11-19
>
> **Audience:** reviewers and maintainers with a background in calculus, ordinary
> differential equations, linear algebra and applied statistics. This document
> defines the production mathematical model of `v1.0.0`, states its assumptions
> and documents the numerical and statistical choices behind the implementation.
>
> The model is a **monitoring and planning aid**, not a medical device. Its
> outputs are estimates derived from training telemetry and self-reported effort;
> they do not diagnose injury or replace professional assessment.

---

## Table of contents

1. [Purpose and scope](#1-purpose-and-scope)
2. [Notation and units](#2-notation-and-units)
3. [Load quantification](#3-load-quantification)
4. [Fitness-fatigue model](#4-fitness-fatigue-model)
5. [Calibration](#5-calibration)
6. [Acute:chronic workload ratio](#6-acutechronic-workload-ratio)
7. [Aerobic efficiency and decoupling](#7-aerobic-efficiency-and-decoupling)
8. [Taper and planning](#8-taper-and-planning)
9. [Race prediction](#9-race-prediction)
10. [Readiness score](#10-readiness-score)
11. [Statistical assumptions and validity](#11-statistical-assumptions-and-validity)
12. [Implementation map](#12-implementation-map)
13. [Reproducibility](#13-reproducibility)
14. [Limitations](#14-limitations)
15. [References](#15-references)

---

## 1. Purpose and scope

Athlete Stress Sim converts heterogeneous training sessions into a single daily
internal-load series, models the resulting fitness-fatigue dynamics and uses the
model to answer four practical questions:

1. **How much internal load did a session produce?**
2. **How fit and how fatigued is the athlete today?**
3. **Is the recent load progression risky, neutral or conservative?**
4. **What race time and taper plan are consistent with the observed training?**

The production pipeline is:

```text
running / elliptical ──► Banister TRIMP ─┐
strength             ──► Foster sRPE    ─┼──► daily load ──► Banister ODE
                                        │                   │
                                        │                   ├──► freshness / TSB
                                        │                   └──► ACWR
                                        │
running telemetry ──► efficiency factor ──► calibration ──► individual gains
```

The document covers the production path. The historical Extended Kalman Filter
(EKF) is mentioned only where it explains why the final calibration is different;
it is not part of the active model. This document is the canonical source for the
model equations, assumptions and references; the README, PRD and user guide
summarize it. The code remains the authoritative source for constants and edge
cases; [Section 12](#12-implementation-map) maps every mathematical object to its
module.

---

## 2. Notation and units

| Symbol | Meaning | Unit |
| --- | --- | --- |
| `D_min` | Session duration | min |
| `HR` | Heart rate | bpm |
| `HR_rest` | Resting heart rate | bpm |
| `HR_max` | Maximum heart rate | bpm |
| `HR_r` | Fractional heart-rate reserve | dimensionless, 0–1 |
| `a`, `b` | Banister weighting coefficients | dimensionless |
| `TRIMP` | Training impulse | arbitrary units (AU) |
| `RPE` | Session rating of perceived exertion | Borg CR-10, 0–10 |
| `w_t` | Daily training load | AU |
| `g_t` | Fitness component | AU |
| `h_t` | Fatigue component | AU |
| `τ_1`, `τ_2` | Fitness and fatigue time constants | days |
| `k_1`, `k_2` | Fitness and fatigue gains | dimensionless |
| `P_0` | Baseline performance | AU |
| `F_t` | Freshness / training-stress balance (TSB) | AU |
| `P_t` | Model performance | AU |
| `L_t` | Daily load used by ACWR | AU |
| `EWMA` | Exponentially weighted moving average | AU |
| `λ` | EWMA decay factor | dimensionless |
| `N` | EWMA window length | days |
| `ACWR` | Acute:chronic workload ratio | dimensionless |
| `EF` | Efficiency factor, `speed / HR` | m/s per bpm |
| `CS` | Critical speed | m/s |
| `D'` | Anaerobic distance reserve | m |
| `T` | Race or effort time | s |
| `D` | Race or effort distance | m |
| `%HRR` | Relative heart-rate reserve | dimensionless, often shown as % |

Two conventions matter throughout:

- **AU means arbitrary units.** Running TRIMP, strength sRPE and the model
  components share a numeric scale for relative comparisons, but they are not
  physiologically interchangeable.
- **Daily index.** `t` denotes a calendar day in the contiguous series built by
  `daily_load_series`; rest days are explicit zeros.

---

## 3. Load quantification

Training-load quantification and monitoring are broad topics with competing
definitions and measurement philosophies [16,17]. This project adopts a
heart-rate impulse for endurance work and a subjective session-RPE for strength
work, then combines both into one relative daily series.

### 3.1 Fractional heart-rate reserve

Heart-rate intensity is normalized with the heart-rate reserve fraction:

$$
HR_r = \mathrm{clamp}\!\left(
\frac{HR - HR_{\text{rest}}}{HR_{\max} - HR_{\text{rest}}},
0, 1
\right)
$$

The clamp protects the model from sensor spikes, warm-up artifacts and invalid
values. `HR_max` must be strictly greater than `HR_rest`; the implementation
raises an error otherwise.

### 3.2 Banister TRIMP

The Banister training impulse weights duration by an exponential function of
heart-rate reserve:

$$
TRIMP = D_{\min} \cdot HR_r \cdot y
$$

with

$$
y = a \cdot e^{b \cdot HR_r}
$$

The sex-specific coefficients follow Morton et al. [3]:

$$
a = 0.64,\; b = 1.92 \quad \text{(male)}
\qquad
a = 0.86,\; b = 1.67 \quad \text{(female)}
$$

For a session summarized by its average heart rate:

$$
TRIMP = D_{\min} \cdot HR_r \cdot a \cdot e^{b \cdot HR_r}
$$

The production path instead integrates the weighting factor over the stored
second-by-second samples:

$$
TRIMP = \sum_{i} \Delta t_{\min} \cdot HR_{r,i} \cdot a
\cdot e^{b \cdot HR_{r,i}}
$$

where `Δt_min` is the sample interval in minutes (one second by default).
Samples that are missing or non-positive contribute no load. This discrete
integral is the production implementation. The average-heart-rate form remains
available as the `trimp_from_average` helper, but the session load path does not
fall back to it: a session without usable heart-rate samples contributes no load.

**Why this matters.** The exponential term makes high-intensity minutes
disproportionately expensive. Two sessions with the same duration can therefore
produce very different TRIMP values, which is the intended behavior of the
Banister impulse.

### 3.3 Foster session-RPE

Heart rate is a poor proxy for strength training: it is low, intermittent and
strongly affected by rest intervals. Strength sessions therefore use Foster's
session-RPE method [4]:

$$
TRIMP_{\text{gym}} = RPE \cdot D_{\min}
$$

`RPE` is the whole-session effort on the Borg CR-10 scale (`0–10`), and `D_min`
is the session duration in minutes. A strength session without RPE contributes
no load.

### 3.4 Daily load aggregation

Let `S_d` be the set of sessions whose FIT `start_time` falls on calendar day
`d`. The daily load is:

$$
w_d = \sum_{s \in S_d} \text{load}(s)
$$

The series is made contiguous by inserting zeros for rest days:

$$
\text{series} = (w_{d_{\min}}, w_{d_{\min}+1}, \ldots, w_{d_{\max}})
$$

This zero-filling is essential: without it, fitness and fatigue would not decay
between sessions.

Load dispatch follows the activity family:

| Session family | Load |
| --- | --- |
| Running | Banister TRIMP from heart-rate samples |
| Elliptical | Banister TRIMP from heart-rate samples |
| Strength | Foster session-RPE |
| Other with valid HR | Banister TRIMP |
| Other without valid HR | No load |

Elliptical sessions contribute to daily load, ACWR and the Banister model, but
they are excluded from running-only analyses (baseline, taper, decoupling and
race prediction) because pace and distance are not directly comparable.

### 3.5 Scale and interpretation

Running TRIMP and strength sRPE are summed in the same arbitrary-unit series.
This is a deliberate simplification: it makes one daily load series possible for
ACWR and the fitness-fatigue model. It does **not** assert that one unit of
strength sRPE equals one unit of running TRIMP. The correct interpretation is
relative: compare the same athlete's trend over time, not the absolute load of a
strength session against a run.

---

## 4. Fitness-fatigue model

### 4.1 Continuous-time formulation

The Banister model represents performance as the difference between a
slow-decaying fitness component `g(t)` and a fast-decaying fatigue component
`h(t)`, both driven by the training-load rate `w(t)` [1,2,3]:

$$
\frac{dg(t)}{dt} = -\frac{1}{\tau_1}g(t) + w(t)
$$

$$
\frac{dh(t)}{dt} = -\frac{1}{\tau_2}h(t) + w(t)
$$

$$
P(t) = P_0 + k_1 g(t) - k_2 h(t)
$$

The physiological intuition is:

- `τ_1` is long (default `42` days), so fitness accumulates and decays slowly.
- `τ_2` is short (default `7` days), so fatigue accumulates and decays quickly.
- `k_1` and `k_2` set the relative contribution of each component.
- `P_0` is the baseline performance level in arbitrary units.

### 4.2 Impulse response and daily recurrence

Training is recorded once per day. The production model treats each day's load as
an impulse of area `w_t`, so the continuous solution is a convolution with an
exponential kernel. For an impulse train:

$$
g(t) = \sum_{t_i \le t} w_{t_i} e^{-(t-t_i)/\tau_1}
$$

$$
h(t) = \sum_{t_i \le t} w_{t_i} e^{-(t-t_i)/\tau_2}
$$

At integer days this is the exact recurrence used by `impulse_response`:

$$
g_t = g_{t-1}e^{-1/\tau_1} + w_t
$$

$$
h_t = h_{t-1}e^{-1/\tau_2} + w_t
$$

with `g_0 = h_0 = 0`.

The recurrence is cheap, deterministic and stable. It is the production path for
Banister, ACWR-adjacent projections, taper forecasts and the what-if simulator.

### 4.3 Freshness, TSB and performance

Freshness (also called training-stress balance, TSB) is the net model balance:

$$
F_t = k_1 g_t - k_2 h_t
$$

$$
P_t = P_0 + F_t
$$

With the default gains (`k_1 = 1`, `k_2 = 2`), freshness is
`fitness − 2 · fatigue`. Positive freshness means the fitness contribution
outweighs the fatigue contribution; negative freshness immediately after a hard
session is expected because fatigue rises faster than fitness.

The dashboard's readiness traffic light does not compare `F_t` to an absolute
threshold when enough history exists. It ranks the current value against the
athlete's own recent distribution; [Section 10](#10-readiness-score) defines
that score.

### 4.4 Numerical cross-check

The module also provides `solve_banister_ode`, which integrates the continuous
system with `scipy.integrate.solve_ivp` while holding the daily load constant
within each day. That is a different discretization from the impulse recurrence:
for one day of constant load `w`,

$$
g_1 = g_0 e^{-1/\tau_1} + w\left(1 - e^{-1/\tau_1}\right)
$$

whereas the impulse recurrence uses `g_1 = g_0 e^{-1/\tau_1} + w`. The
difference is the within-day factor `1 − e^{-1/τ}`. The numerical path is used as
an independent integration check and converges to the same steady state; it is
not the production sequence.

### 4.5 Worked example

Take `HR = 150` bpm, `HR_rest = 60` bpm and `HR_max = 200` bpm. Then

$$
HR_r = \frac{150-60}{200-60} \approx 0.643
$$

For a male athlete,

$$
y = 0.64e^{1.92 \times 0.643} \approx 2.199
$$

and a 60-minute session at that average heart rate yields

$$
TRIMP \approx 60 \times 0.643 \times 2.199 \approx 84.8 \text{ AU}
$$

Now apply a single 100 AU impulse with the default parameters
(`τ_1 = 42`, `τ_2 = 7`, `k_1 = 1`, `k_2 = 2`). The first days are:

| Day | Fitness `g` | Fatigue `h` | Freshness `F` |
| --- | ---: | ---: | ---: |
| 1 | 100.00 | 100.00 | −100.00 |
| 2 | 97.65 | 86.69 | −75.73 |
| 3 | 95.35 | 75.15 | −54.95 |
| 4 | 93.11 | 65.14 | −37.18 |
| 5 | 90.92 | 56.47 | −22.03 |

Fatigue decays faster than fitness, which is exactly the behavior a taper
exploits: reduce load, let fatigue fall, and preserve a larger fraction of
fitness.

---

## 5. Calibration

### 5.1 Why calibration is hard

The fitness-fatigue model is a phenomenological model, not a structural
physiological model. Fitting all parameters from a single noisy performance
series is ill-conditioned: the gains and time constants trade off against each
other, and different parameter combinations can produce similar curves. Vermeire
et al. [8] and Marchal et al. [9] discuss the statistical fragility of
fitness-fatigue predictions and the importance of identifiability,
regularization and out-of-sample validation.

The project originally implemented an EKF to estimate `k_1`, `k_2`, `τ_1` and
`τ_2` online (S9). The final production path replaces it with a simpler and more
transparent strategy:

- fix `τ_1` and `τ_2` at the physiological priors;
- estimate only `P_0`, `k_1` and `k_2`;
- use bounded ridge least squares;
- accept the fit only if it beats the prior baseline in cross-validation.

The label **NLS** is retained for continuity with the nonlinear calibration
literature, but the fitted subproblem is linear once the time constants are
fixed.

### 5.2 Observations

The observed performance signal is the session efficiency factor:

$$
EF = \frac{\text{speed}}{\text{HR}}
$$

At the session level, `session_efficiency` computes the mean of valid
per-second ratios:

$$
EF_s = \frac{1}{|V_s|}\sum_{i \in V_s}\frac{v_i}{HR_i}
$$

where `V_s` is the set of samples with positive speed and heart rate. Only running
sessions provide observations; strength sessions have no comparable speed.

Observations are normalized by their median to make the fit scale-free:

$$
y_s = \frac{EF_s}{\mathrm{median}(EF)}
$$

Multiple sessions on the same day are averaged. The observation is mapped to the
index of that day in the contiguous load series; sessions outside the series or
without a valid EF are ignored. The resulting data are a set
`{(d_i, y_i)}_{i=1}^{N}`.

### 5.3 Fixed time constants and ridge objective

Let `X` be the design matrix with rows

$$
x_i = \left(1,\; g_{d_i},\; -h_{d_i}\right)
$$

and let `β = (β_0, β_1, β_2)` be the intercept and the two effective gains. The
observation model is:

$$
y_i = \beta_0 + \beta_1 g_{d_i} - \beta_2 h_{d_i} + \varepsilon_i
$$

The fit minimizes a ridge-penalized least-squares objective [10]:

$$
\hat{\beta} = \arg\min_{\beta}
\left\| X\beta - y \right\|_2^2
+ \lambda \left\| \beta - \beta_{\text{prior}} \right\|_2^2
$$

subject to

$$
\beta_1 \ge 0, \qquad \beta_2 \ge 0, \qquad -10 \le \beta_0 \le 10
$$

in standardized units. The production value is `λ = 1e-2`. Columns are scaled by
their standard deviations before solving, and the bounded problem is solved with
`scipy.optimize.lsq_linear` (trust-region reflective method). The prior
coefficient vector is shaped to the prior freshness amplitude:

$$
s = \frac{\mathrm{std}(y)}{\mathrm{std}(F_{\text{prior}})}
$$

$$
\beta_{\text{prior}} =
\left(
1 - s \cdot \mathrm{median}(F_{\text{prior}}),
\; s k_1,\;
s k_2
\right)
$$

where `F_prior` is the prior-shaped freshness series over the observed days.

### 5.4 Acceptance gate and fallback

The fit is **not** accepted merely because the optimizer converges. It must pass
all of the following:

1. at least **8 observations**;
2. in-sample coefficient of determination `R² ≥ 0.1`;
3. leave-one-out cross-validation RMSE improvement of at least **5 %** over the
   prior-shaped baseline;
4. positive effective gains;
5. `τ_1 > τ_2`.

The cross-validation metric is based on leave-one-out validation [11]:

$$
\text{RMSE} = \sqrt{\frac{1}{N}\sum_{i=1}^{N}(y_i - \hat{y}_i)^2}
$$

$$
\text{improvement} = 1 - \frac{\text{RMSE}_{\text{fit}}}
{\text{RMSE}_{\text{prior}}}
$$

If any condition fails, `calibrate_banister` returns the physiological priors
together with the diagnostics that were computed. The dashboard then labels the
projection as prior-based. This fail-soft behavior is intentional: a bad fit is
worse than a transparent prior.

When the fit passes, the gains are rescaled to the prior freshness amplitude so
freshness stays in the same load units as the rest of the dashboard:

$$
s_{\text{rescale}} =
\frac{\mathrm{std}(F_{\text{prior}})}
{\mathrm{std}(F_{\text{fit}})}
$$

$$
k_1' = s_{\text{rescale}} k_1, \qquad
k_2' = s_{\text{rescale}} k_2, \qquad
P_0' = P_0^{\text{prior}}
$$

The time constants remain fixed at the priors.

### 5.5 Diagnostics and limitations

The API exposes:

- effective parameters and priors;
- `calibrated` flag;
- number of observations;
- `R²`;
- median efficiency used for normalization;
- calibrated and prior CV RMSE;
- relative CV improvement.

Important statistical caveats:

- **Small `N`.** Eight observations is a minimum for a three-parameter fit, not a
  large sample.
- **Autocorrelation.** Training and performance observations are a time series,
  not independent samples. Leave-one-out CV is not equivalent to
  forward-chaining validation; it can be optimistic.
- **In-sample `R²`.** The gate combines in-sample fit with out-of-sample
  improvement, but both are computed on a short, noisy series.
- **Fixed regularization.** `λ` is a design choice, not tuned per athlete.
- **Prior dependence.** The ridge penalty and the fallback both encode prior
  beliefs about plausible gains and time constants.

These choices are deliberate: they make the model stable, explainable and safe
to deploy for a single athlete with limited data.

---

## 6. Acute:chronic workload ratio

### 6.1 Exponentially weighted moving averages

For a daily load series `L_t`, the EWMA is:

$$
EWMA_t = \lambda L_t + (1-\lambda) EWMA_{t-1}
$$

$$
\lambda = \frac{2}{N+1}
$$

The series is seeded with the first load value. The implementation uses:

- `N = 7` for acute load, so `λ = 1/4 = 0.25`;
- `N = 28` for chronic load, so `λ = 2/29 ≈ 0.069`.

The acute and chronic EWMAs are computed independently over the same contiguous
daily series.

### 6.2 Ratio and risk zones

$$
ACWR_t = \frac{EWMA_t^{\text{acute}}}{EWMA_t^{\text{chronic}}}
$$

If the chronic EWMA is zero, the implementation returns `0.0` rather than
dividing by zero. This occurs at the very beginning of an empty or near-empty
history.

Risk zones follow the common load-management bands [5,6,7]:

| Zone | Condition |
| --- | --- |
| Undertraining | `ACWR < 0.8` |
| Sweet spot | `0.8 ≤ ACWR ≤ 1.3` |
| Warning | `1.3 < ACWR ≤ 1.5` |
| Danger | `ACWR > 1.5` |

### 6.3 Interpretation limits

- The EWMA seed creates a transient: early values are pulled toward the first
  load and need several weeks to stabilize.
- The ratio is a **load signal**, not an injury probability. It does not include
  sleep, stress, terrain, age, previous injury or recovery quality.
- The acute:chronic ratio has been debated in the sports-science literature;
  Williams et al. [6] and Murray et al. [7] discuss methodological choices and
  the EWMA formulation. The implementation follows the EWMA variant because it
  responds more smoothly than a simple rolling average.
- Because running TRIMP and strength sRPE share an arbitrary scale, the ratio is
  most useful within one athlete's own history, not across athletes or training
  modes.

---

## 7. Aerobic efficiency and decoupling

### 7.1 Efficiency factor

The efficiency factor relates speed to heart rate:

$$
EF = \frac{v}{HR}
$$

where `v` is speed in meters per second and `HR` is heart rate in bpm. A higher
EF means more speed at the same heart rate. The session-level EF used for
calibration is the mean of valid per-sample ratios (Section 5.2).

### 7.2 Per-kilometer EF and decoupling

For decoupling, samples are binned by completed kilometer using cumulative
distance. The per-kilometer efficiency factor is the ratio of summed speed to
summed heart rate over valid samples:

$$
EF_k = \frac{\sum_{i \in k} v_i}{\sum_{i \in k} HR_i}
$$

This is a ratio of means (with equal sample counts), not the mean of per-sample
ratios. The per-kilometer series is then split into halves at
`floor(n/2)`, and the decoupling percentage is:

$$
\text{decoupling} =
\frac{\overline{EF}_{\text{first}} - \overline{EF}_{\text{second}}}
{\overline{EF}_{\text{first}}} \times 100
$$

A positive value means EF fell in the second half: the athlete produced less
speed at the same heart rate. This is consistent with cardiovascular drift
during prolonged exercise [15]. Negative values mean EF rose; this can happen
when the athlete warms up or paces more evenly.

The computation requires at least **2 kilometers** with valid speed and
heart-rate data. With an odd number of kilometers, the split at `floor(n/2)`
gives the second half one extra segment.

The dashboard colors the result green at `≤ 5 %`, yellow between `5 %` and
`10 %`, and red above `10 %`. These are presentation bands, not clinical
thresholds.

---

## 8. Taper and planning

### 8.1 Recent running baseline

The taper planner starts from a recent running baseline computed over the last
four weeks before the taper:

- include running sessions with positive distance and duration;
- require at least four valid sessions;
- weekly volume = total distance / covered weeks;
- runs per week = `round(valid sessions / covered weeks)`, at least 1;
- pace = total minutes / total kilometers;
- RPE = mean session RPE, or `6.0` when none is recorded.

The baseline is a convenience, not a requirement: the user can enter the values
manually.

### 8.2 Taper factors and schedule

Weekly volume is reduced linearly while intensity (pace and RPE) is preserved.
For `W > 1` taper weeks, the factor for week `j` (zero-based) is:

$$
f_j = 0.75 + \frac{0.35-0.75}{W-1}\,j
$$

so a three-week taper uses `0.75`, `0.55`, `0.35`, and a one-week taper uses
`0.5`. The planned weekly volume is:

$$
V_j = f_j V_{\text{base}}
$$

For a three-run week, sessions are placed on Tuesday, Thursday and Sunday.
Additional runs follow a fixed weekday order, and no session is placed on or
after race day. This makes race morning a rest day in the projection and ensures
that the projected freshness includes the final decay.

### 8.3 Projected load and simulation

A planned running session is converted to load with session-RPE:

$$
D_{\min} = \text{distance}_{\text{km}} \cdot \text{pace}_{\min/\text{km}}
$$

$$
\text{load} = RPE \cdot D_{\min}
$$

The race-taper planner concatenates the real history and the planned sessions,
fills any remaining days up to race day with zero load, and applies the exact
Banister recurrence. The what-if simulator applies the same recurrence to the
history plus its planned sessions without padding to a race date.

### 8.4 Peak freshness

For the race-taper response, the implementation searches the window from
`7 × taper_weeks` days before race day through race day and reports:

- projected freshness on race morning;
- the day with the highest freshness inside that window;
- the peak value.

This is a descriptive projection of the model, not an optimizer. The plan does
not search over all possible session distributions; it applies a fixed,
explainable volume reduction and preserves pace/RPE.

---

## 9. Race prediction

### 9.1 Effort detection

For each running activity, the predictor builds a distance–time series from valid
samples with non-decreasing cumulative distance. For every target distance
(`1 km`, `3 km`, `5 km`, `10 km`, `21.0975 km`), a sliding window finds the
fastest segment covering at least that distance. The segment yields:

- elapsed time;
- average speed;
- average heart rate over the segment;
- relative heart-rate reserve;
- efficiency factor;
- intensity tier.

The fastest effort per distance across the recent 180 days is retained. The UI
shows the detected efforts; the API can also accept a manual race or time-trial
reference.

### 9.2 Intensity classification and fitness adjustment

Relative heart-rate reserve is:

$$
\%HRR = \frac{HR - HR_{\text{rest}}}{HR_{\max} - HR_{\text{rest}}}
$$

The tiers are:

| Tier | `%HRR` |
| --- | --- |
| `race` | `≥ 88 %` |
| `hard` | `80 % ≤ %HRR < 88 %` |
| `moderate` | `70 % ≤ %HRR < 80 %` |
| `easy` | `< 70 %` |

Each effort is adjusted by the Banister fitness change since its date:

$$
f = \mathrm{clamp}\!\left(
\frac{F_{\text{current}}}{F_{\text{effort}}},
0.8, 1.2
\right)
$$

$$
t_{\text{adjusted}} = t \cdot f^{-0.1}
$$

If current fitness is higher than at the time of the effort (`f > 1`), the
adjusted time decreases; the exponent `0.1` deliberately damps the correction.
The clamp prevents extreme extrapolation.

### 9.3 Heart-rate correction to race effort

A hard training effort is not a race effort. Assuming approximately constant
efficiency factor, speed scales with heart rate:

$$
c_{HR} = \mathrm{clamp}\!\left(
\frac{HR_{\text{race}}}{HR_{\text{effort}}},
1.0, 1.15
\right)
$$

$$
t_{\text{race-equivalent}} =
\frac{t_{\text{adjusted}}}{c_{HR}}
$$

The race-level heart rate depends on the target distance:

| Target distance | Race `%HRR` |
| --- | --- |
| `≤ 6 km` | `93 %` |
| `≤ 12 km` | `90 %` |
| `≤ 25 km` | `88 %` |
| `> 25 km` | `85 %` |

The correction is capped at `1.15` to avoid over-optimistic extrapolation from a
short, hard effort.

### 9.4 Riegel power law

Riegel's model predicts a target time from a reference effort [12]:

$$
T_2 = T_1 \left(\frac{D_2}{D_1}\right)^k
$$

The default exponent is `k = 1.06`. The UI also computes a slower range with
`k = 1.08`, applies tier-dependent widening and reports fast/slow bounds. The
central estimate is clamped to the fast/slow envelope.

The model assumes that endurance fatigue scales as a power law across distances.
It is most reliable when the reference and target distances are not too far
apart and when the reference is a genuine race or hard effort.

### 9.5 Critical speed

The critical-speed model separates a sustainable speed from a finite distance
reserve [13,14]:

$$
D = CS \cdot T + D'
$$

`CS` is the slope of distance versus time, and `D'` is the intercept. The
implementation fits the line by ordinary least squares on quality efforts
(`race` or `hard`) and requires:

- at least **2** quality efforts at distinct distances;
- a time ratio `max(T) / min(T) ≥ 1.2`;
- positive `CS`;
- non-negative `D'`.

The prediction is:

$$
T = \frac{D - D'}{CS}
$$

The uncertainty band uses the standard error of the slope, with a floor of
`2 %` of `CS`:

$$
T_{\text{fast}} = \frac{D-D'}{CS + u},
\qquad
T_{\text{slow}} = \frac{D-D'}{\max(CS-u, \epsilon)}
$$

The automatic model chooses critical speed only when at least **3** quality
efforts produce `R² ≥ 0.9`. Confidence is high at `R² ≥ 0.97`, medium at
`R² ≥ 0.9`, and low otherwise.

### 9.6 Heart-rate extrapolation

When only easy efforts are available, the predictor extrapolates speed from the
best observed efficiency factor and a race-level heart rate:

$$
HR_{\text{race}} = HR_{\text{rest}} +
r_{\text{race}}(HR_{\max} - HR_{\text{rest}})
$$

$$
v_{\text{race}} = \max(EF) \cdot HR_{\text{race}}
$$

$$
T = \frac{D}{v_{\text{race}}}
$$

The range is widened by `±15 %` and the confidence is always low. A real race or
time trial is a much stronger anchor.

### 9.7 Automatic selection, range and confidence

The automatic policy is:

1. critical speed if there are at least three quality efforts and `R² ≥ 0.9`;
2. otherwise Riegel if a race/hard reference exists;
3. otherwise heart-rate extrapolation.

Confidence depends on the reference tier and the distance ratio between the
reference and the target. The response always includes the model used, the
confidence level, the efforts used and explanatory notes. This makes the
prediction auditable rather than a single opaque number.

---

## 10. Readiness score

The readiness traffic light is presentation logic, not a physiological model.
It ranks the current freshness against the athlete's recent history:

$$
p = \frac{1}{|\mathcal{H}|}
\sum_{F \in \mathcal{H}} \mathbf{1}[F \le F_{\text{current}}]
$$

where `H` is the freshness history over the last 90 days. With at least 14
observations:

- `p ≥ 0.50` → **Ready**;
- `0.15 ≤ p < 0.50` → **Caution**;
- `p < 0.15` → **Rest**.

With fewer than 14 observations, absolute thresholds are used:

- `F ≥ 0` → Ready;
- `-5 ≤ F < 0` → Caution;
- `F < -5` → Rest.

The percentile approach is used because the absolute scale of freshness depends
on arbitrary gains and on whether calibration is active. The relative ranking is
therefore more stable across model configurations.

---

## 11. Statistical assumptions and validity

The model is deliberately pragmatic. Its main assumptions are:

1. **Linearity and superposition.** Fitness and fatigue respond linearly to
   daily load, and their effects combine additively. Real adaptation is not
   strictly linear.
2. **Time-invariant parameters.** The priors (and, when accepted, the calibrated
   gains) are constant over the modeled window. Real athletes adapt.
3. **Daily aggregation.** Within-day timing, session order and recovery between
   sessions are compressed into one daily load.
4. **Comparable load scale.** Running TRIMP and strength sRPE are treated as a
   common AU scale for ACWR and the model.
5. **Measurement quality.** `HR_max`, `HR_rest`, heart-rate samples and RPE are
   assumed to be sufficiently accurate. Errors propagate into TRIMP and the
   fitness-fatigue curves.
6. **Stationarity of efficiency.** Race prediction assumes that the efficiency
   factor and heart-rate reserve relationship are stable enough to extrapolate.
7. **Phenomenological interpretation.** The model describes observed training
   responses; it does not identify physiological mechanisms or causal effects.

Additional validity notes:

- The calibration gate is a **quality heuristic**, not a formal hypothesis test.
- Leave-one-out CV is not a temporal validation scheme. A forward-chaining
  validation would be preferable with longer histories.
- The race predictor is an extrapolation. Confidence labels are heuristic and
  should be read as relative, not probabilistic.
- ACWR and freshness are monitoring signals. They must be interpreted with
  training context, subjective well-being and several weeks of trend.

---

## 12. Implementation map

| Mathematical object | Module | Key function / constant |
| --- | --- | --- |
| Heart-rate reserve and TRIMP | `core/metrics/trimp.py` | `heart_rate_reserve`, `trimp_from_average`, `trimp_from_samples` |
| Session-RPE | `core/metrics/rpe.py` | `session_rpe_load` |
| Session load dispatch and daily series | `core/metrics/load.py` | `session_load`, `planned_session_load`, `daily_load_series` |
| Banister recurrence and ODE cross-check | `core/models/banister.py` | `impulse_response`, `solve_banister_ode`, `BanisterParams` |
| Calibration | `core/models/calibration.py` | `calibrate_banister`, `MIN_OBSERVATIONS`, `MIN_R_SQUARED`, `MIN_CV_IMPROVEMENT`, `RIDGE_LAMBDA` |
| Efficiency-factor observations | `core/metrics/performance.py` | `session_efficiency`, `performance_observations` |
| EWMA and ACWR | `core/metrics/acwr.py` | `ewma_lambda`, `ewma_series`, `acwr_series`, `classify_risk` |
| EF and decoupling | `core/metrics/decoupling.py` | `efficiency_factor`, `per_km_efficiency`, `aerobic_decoupling` |
| Taper baseline and schedule | `core/metrics/taper.py` | `running_baseline`, `taper_weekly_factors`, `build_taper_sessions` |
| Race efforts and prediction | `core/metrics/race_prediction.py` | `best_effort`, `select_best_efforts`, `fit_critical_speed`, `riegel_time`, `predict_race` |
| Readiness | `frontend/readiness.py` | `assess_readiness`, `freshness_percentile` |

---

## 13. Reproducibility

The model is covered by deterministic tests that use synthetic telemetry and
temporary databases:

```bash
make test
make test-cov
uv run pytest tests/test_trimp.py tests/test_rpe.py tests/test_load.py
uv run pytest tests/test_acwr.py tests/test_banister.py tests/test_calibration.py
uv run pytest tests/test_decoupling.py tests/test_taper.py tests/test_race_prediction.py
```

Tests use hand-calculated reference values where possible, synthetic FIT fixtures
for ingestion and injected HTTP transports for Polar clients. No test requires
network access or real biometric data.

---

## 14. Limitations

- The model is **phenomenological**, not a diagnosis or a guarantee.
- Joint estimation of gains and time constants is unstable on short histories;
  the production path fixes the time constants and regularizes the gains.
- Calibration may fall back to priors even with real data.
- The combined TRIMP/sRPE scale is a practical simplification.
- ACWR and freshness do not include sleep, stress, terrain, injury history or
  recovery quality.
- Taper factors are a fixed heuristic, not an optimized plan.
- Race prediction is an extrapolation from training efforts; it is not a
  same-day performance guarantee.
- Measurement errors in heart rate, maximal heart rate, resting heart rate and
  RPE propagate into every downstream metric.

---

## 15. References

1. Calvert, T. W., Banister, E. W., Savage, M. V., & Bach, T. (1976). A systems
   model of the effects of training on physical performance. *IEEE Transactions
   on Systems, Man, and Cybernetics*, SMC-6(2), 94–102.
   <https://doi.org/10.1109/TSMC.1976.5409179>
2. Banister, E. W. (1991). Modeling elite athletic performance. In H. J. Green,
   J. R. McDougall, & H. A. Wenger (Eds.), *Physiological Testing of the
   High-Performance Athlete* (2nd ed., pp. 403–424). Human Kinetics.
3. Morton, R. H., Fitz-Clarke, J. R., & Banister, E. W. (1990). Modeling human
   performance in running. *Journal of Applied Physiology*, 69(3), 1171–1177.
   <https://doi.org/10.1152/jappl.1990.69.3.1171>
4. Foster, C., Florhaug, J. A., Franklin, J., Gottschall, L., Hrovatin, L. A.,
   Parker, S., Doleshal, P., & Dodge, C. (2001). A new approach to monitoring
   exercise training. *Journal of Strength and Conditioning Research*, 15(1),
   109–115. <https://doi.org/10.1519/00124278-200102000-00019>
5. Gabbett, T. J. (2016). The training-injury prevention paradox: should
   athletes be training smarter and harder? *British Journal of Sports
   Medicine*, 50(5), 273–280.
   <https://doi.org/10.1136/bjsports-2015-095788>
6. Williams, S., West, S., Cross, M. J., & Stokes, K. A. (2017). Better way to
   determine the acute:chronic workload ratio? *British Journal of Sports
   Medicine*, 51(3), 209–210.
   <https://doi.org/10.1136/bjsports-2016-096589>
7. Murray, N. B., Gabbett, T. J., Townshend, A. D., & Blanch, P. (2017).
   Calculating acute:chronic workload ratios using exponentially weighted moving
   averages provides a more sensitive indicator of injury likelihood than rolling
   averages. *British Journal of Sports Medicine*, 51(9), 749–754.
   <https://doi.org/10.1136/bjsports-2016-097152>
8. Vermeire, K., Ghijs, M., Bourgois, J. G., & Boone, J. (2022). The
   fitness–fatigue model: what's in the numbers? *International Journal of
   Sports Physiology and Performance*, 17(5), 810–813.
   <https://doi.org/10.1123/ijspp.2021-0494>
9. Marchal, A., Benazieb, O., Weldegebriel, Y., Méline, T., & Imbach, F. (2025).
   Statistical flaws of the fitness-fatigue sports performance prediction model.
   *Scientific Reports*, 15, 3706.
   <https://doi.org/10.1038/s41598-025-88153-7>
10. Hoerl, A. E., & Kennard, R. W. (1970). Ridge regression: biased estimation
    for nonorthogonal problems. *Technometrics*, 12(1), 55–67.
    <https://doi.org/10.1080/00401706.1970.10488634>
11. Stone, M. (1974). Cross-validatory choice and assessment of statistical
    predictions. *Journal of the Royal Statistical Society: Series B*, 36(2),
    111–133. <https://doi.org/10.1111/j.2517-6161.1974.tb00994.x>
12. Riegel, P. S. (1981). Athletic records and human endurance. *American
    Scientist*, 69(3), 285–290.
13. Monod, H., & Scherrer, J. (1965). The work capacity of a synergic muscular
    group. *Ergonomics*, 8(3), 329–338.
    <https://doi.org/10.1080/00140136508930810>
14. Jones, A. M., Vanhatalo, A., Burnley, M., Morton, R. H., & Poole, D. C.
    (2010). Critical power: implications for determination of V̇O2max and
    exercise tolerance. *Medicine & Science in Sports & Exercise*, 42(10),
    1876–1890. <https://doi.org/10.1249/MSS.0b013e3181d9cf7f>
15. Coyle, E. F. (2001). Cardiovascular drift during prolonged exercise: new
    perspectives. *Exercise and Sport Sciences Reviews*, 29(2), 88–92.
    <https://doi.org/10.1097/00003677-200104000-00009>
16. Bourdon, P. C., Cardinale, M., Murray, A., Gastin, P., Kellmann, M., Varley,
    M. C., Gabbett, T. J., Coutts, A. J., Burgess, D. J., Gregson, W., & Cable,
    N. T. (2017). Monitoring athlete training loads: consensus statement.
    *International Journal of Sports Physiology and Performance*, 12(S2),
    S2-161–S2-170. <https://doi.org/10.1123/IJSPP.2017-0208>
17. Borresen, J., & Lambert, M. I. (2009). The quantification of training load,
    the training response and the effect on performance. *Sports Medicine*,
    39(9), 779–795.
    <https://doi.org/10.2165/11317780-000000000-00000>
