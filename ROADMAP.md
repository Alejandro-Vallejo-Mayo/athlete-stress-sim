# Roadmap Maestro — Athleta-Stress-Sim

> **Documento rector del desarrollo.** Toda tarea de implementación debe poder trazarse hasta una de las semanas y sus criterios de aceptación aquí definidos.
>
> - **Proyecto:** Biomechanical Fatigue & Load Management Optimizer
> - **Horizonte:** 4 meses (16 semanas) · 1 cuatrimestre
> - **Usuario cero:** preparación personal de primera Media Maratón (3 días carrera + 3 días gimnasio)
> - **Dispositivo:** Polar Ignite (Polar AccessLink API)
> - **Fuente de requisitos:** `athlete-stress-sim-PRD.md` (v1.0.0)
> - **Estado:** En planificación

---

## Índice

1. [Cómo usar este documento](#1-cómo-usar-este-documento)
2. [Leyenda de seguimiento](#2-leyenda-de-seguimiento)
3. [Objetivos y criterios de éxito](#3-objetivos-y-criterios-de-éxito)
4. [Visión general de fases](#4-visión-general-de-fases)
5. [Mapa de dependencias](#5-mapa-de-dependencias)
6. [Plan semanal (Sprints)](#6-plan-semanal-sprints)
7. [Criterios de aceptación por fase (Definition of Done)](#7-criterios-de-aceptación-por-fase)
8. [Riesgos y mitigaciones](#8-riesgos-y-mitigaciones)
9. [Priorización (MoSCoW)](#9-priorización-moscow)
10. [Cómo se actualiza este roadmap](#10-cómo-se-actualiza-este-roadmap)

---

## 1. Cómo usar este documento

- El desarrollo se organiza en **4 fases** (una por mes) y **16 sprints semanales**.
- Cada sprint lista **objetivos**, **tareas** y **criterios de aceptación** concretos y verificables.
- Cada tarea se referencia contra un requisito del PRD (`RF-xx` / `RNF-xx`) para mantener trazabilidad.
- Al final de cada sprint se marca la casilla correspondiente y se registra el estado real en `git`.
- Este documento **no sustituye** al PRD: el PRD define el *qué* y el *porqué*; este roadmap define el *cómo*, *cuándo* y *en qué orden*.

### 1.1 Convenciones y stack de desarrollo

- **Gestión de dependencias y entorno:** [`uv`](https://docs.astral.sh/uv/) con `pyproject.toml` (PEP 621) y `uv.lock` bloqueado. Nunca se usa `pip`/`requirements.txt` directamente; el entorno se crea con `uv sync`.
- **Layout:** `src/athlete_stress_sim/` (paquete único, *src layout*) con submódulos `backend/`, `core/` y `frontend/`.
- **Lint y formato:** `ruff` (linter + formatter). **Tipado:** `mypy`. **Tests:** `pytest` + `pytest-cov`.
- **Git hooks:** `pre-commit` (ruff, ruff-format, mypy, end-of-file-fixer, trailing-whitespace, check-yaml, check-toml, detect-private-key).
- **Orquestación:** `Makefile` como única puerta de entrada a los comandos; el CI de GitHub Actions invoca `make lint` y `make test`, nunca comandos sueltos.

---

## 2. Leyenda de seguimiento

| Marca | Significado |
|-------|-------------|
| `[ ]` | Pendiente |
| `[~]` | En progreso |
| `[x]` | Completado |
| `[!]` | Bloqueado |

> Cada hito de fase tiene una casilla maestra en `## 7. Criterios de aceptación por fase`.

---

## 3. Objetivos y criterios de éxito

**Objetivo final:** una plataforma end-to-end que ingeste telemetría Polar, calcule carga (TRIMP), modele Fitness-Fatiga (EDO + EKF), evalúe riesgo de lesión (ACWR) y ofrezca un dashboard interactivo con simulador de *tapering* para llegar óptimamente a la Media Maratón.

**Criterios de éxito (medibles):**

1. Los 5 requisitos funcionales (`RF-01` → `RF-05`) implementados y verificados con tests.
2. Los 4 requisitos no funcionales (`RNF-01` → `RNF-04`) cumplidos.
3. Cobertura de tests ≥ 80 % en `src/athlete_stress_sim/core` (métricas + modelos).
4. Simulación EDO < 0.5 s (`RNF-02`).
5. Sistema desplegado con `docker compose up` y usable en rutina real durante al menos 2 semanas.
6. `README.md` público en inglés con matemática (LaTeX), diagramas y capturas reales (portfolio).

---

## 4. Visión general de fases

| Fase | Mes | Semanas | Nombre | Entregable principal |
|------|-----|---------|--------|----------------------|
| **F0** | 1 | S1–S4 | Fundamentos, Polar y DuckDB | Telemetría cruda persistida |
| **F1** | 2 | S5–S9 | Motor Fisiológico | TRIMP, ACWR, EDO y EKF funcionales |
| **F2** | 3 | S10–S13 | API + Dashboard | Dashboard interactivo + simulador |
| **F3** | 4 | S14–S16 | Uso real, validación y portfolio | Sistema validado + README público |

---

## 5. Mapa de dependencias

```text
S1 Config/Docker ──► S2 OAuth2 ──► S3 AccessLink ──► S4 Parser+DuckDB
                                                         │
                                                         ▼
                              S5 TRIMP carrera ──► S6 TRIMP gym ──► S7 ACWR
                                                                        │
                                                                        ▼
                                                        S8 EDO Banister ──► S9 EKF
                                                                               │
                                                                               ▼
S10 FastAPI ◄─────────────────────────────────────────────────────────────────┘
     │
     ▼
S11 Dash skeleton ──► S12 Panel estado ──► S13 Simulador + desacoplamiento
                                                       │
                                                       ▼
                                         S14 Integración real ──► S15 Docker/CI ──► S16 Portfolio
```

---

## 6. Plan semanal (Sprints)

### Fase 0 — Fundamentos, Conexión Polar e Ingesta (Mes 1)

#### Semana 1 — Entorno, repo y scaffolding
**Objetivo:** dejar el proyecto reproducible desde el minuto cero, con tooling completo.

- [x] Instalar `uv` y fijar Python 3.12 con `.python-version`.
- [x] Inicializar proyecto con `uv init` y layout `src/athlete_stress_sim/` (paquete único).
- [x] Configurar `pyproject.toml`: dependencias (`scipy`, `statsmodels`, `filterpy`, `httpx2`, `fitparse`, `duckdb`, `fastapi`, `uvicorn`, `dash`, `dash-mantine-components`, `pydantic`), `[project.scripts]`, `[tool.uv]`, `[tool.ruff]`, `[tool.mypy]`, `[tool.pytest.ini_options]`; generar `uv.lock`.
- [x] Crear `src/athlete_stress_sim/backend/config.py` con constantes fisiológicas y placeholders de credenciales (`HR_max`, `HR_reposo`, `tau_1`, `tau_2`, `k_1`, `k_2`, `b`).
- [x] Crear `.env.example` (client_id, client_secret, access_token, etc.).
- [x] Crear `Makefile` con targets: `install`, `lint`, `format`, `typecheck`, `test`, `run-backend`, `run-frontend`, `docker-up`, `docker-down`.
- [x] Configurar `.pre-commit-config.yaml` (ruff, ruff-format, mypy, end-of-file-fixer, trailing-whitespace, check-yaml, check-toml, detect-private-key).
- [x] Configurar `.github/workflows/ci.yml` que invoque `make lint`, `make typecheck` y `make test` (no comandos sueltos).
- [x] Configurar `docker/Dockerfile.*` y `docker-compose.yml` instalando dependencias vía `uv sync`.
- [x] Hito: `make install && make lint && make test` y `docker compose up` funcionan sin errores.

#### Semana 2 — Autenticación OAuth2 Polar
**Objetivo:** vincular la cuenta Polar (`RF-01.1`).

- [x] Implementar flujo Authorization Code + `state` con `httpx2` (cliente confidencial, sin PKCE).
- [x] Endpoints `/auth/login` y `/auth/callback` en FastAPI.
- [x] Registrar usuario Polar y persistir tokens (access + refresh) en DuckDB o config cifrada.
- [x] Gestión de refresco de token automático (expiración).
- [x] Tests unitarios del flujo con servidor OAuth mockeado.
- [x] Hito: se obtiene y renueva un `access_token` válido de forma programática.

#### Semana 3 — Cliente AccessLink y sincronización catch-up
**Objetivo:** descargar sesiones automáticamente (`RF-01.2`).

- [x] Cliente `src/athlete_stress_sim/core/etl/polar_client.py`: listar `exercises`, obtener resúmenes y descargar `.FIT`/`.TCX`.
- [x] Sincronización *catch-up* idempotente (arranque + `POST /sync`); webhooks/cron diferidos (uso local, sin HTTPS pública).
- [x] Registro de ingesta en DuckDB (`ingest_log`) como cola para S4.
- [x] Manejo de errores, reintentos con backoff y `429` (rate limiting).
- [x] Hito: al sincronizar, una sesión nueva se descarga automáticamente y queda registrada.

#### Semana 4 — Parser FIT/TCX y persistencia DuckDB
**Objetivo:** series temporales segundo a segundo en DuckDB (`RF-01.3`, `RNF-01`).

- [x] Parser `.FIT` con `fitparse` extrayendo `HR_t`, `pace_t` (velocidad), cadencia y altitud (TCX diferido; el Polar emite FIT).
- [x] Modelo de datos OLAP en DuckDB: tablas `exercises`, `samples`, `athlete`.
- [x] ETL de normalización y validación de series (outliers, gaps).
- [x] Tests de parser con archivos `.FIT` sintéticos generados en test (sin datos biométricos reales).
- [x] Hito: una sesión de carrera queda persistida y consultable por SQL.

---

### Fase 1 — Motor Fisiológico (Mes 2)

#### Semana 5 — TRIMP de carrera (Banister)
**Objetivo:** cuantificar carga de carrera (`RF-02.1`).

- [x] Implementar `src/athlete_stress_sim/core/metrics/trimp.py` con `TRIMP = D · HR_r · a · e^{b·HR_r}` (hombre: a=0.64, b=1.92; mujer: a=0.86, b=1.67), integrado segundo a segundo.
- [x] Añadir a `config.py` la variable `sex` (`male`/`female`) para seleccionar los parámetros (a, b).
- [x] Cálculo de `HR_r` a partir de HR (media y/o por segundo), reposo y máxima.
- [x] Tests contra valores de referencia calculados a mano (ambos sexos).

#### Semana 6 — Carga de gimnasio (sRPE de Foster)
**Objetivo:** cuantificar carga de fuerza (`RF-02.2`, `RF-01.4`).

- [x] Modelo `TRIMP_gym = RPE · D_min` (session-RPE de Foster, Borg CR-10 0–10) en `core/metrics/rpe.py`.
- [x] Registro de sesiones de fuerza y del RPE en la tabla `session_rpe` de DuckDB.
- [x] API para introducir RPE post-entreno (`POST /exercises/{id}/rpe`); componente de dashboard diferido a S11–S13.
- [x] Tests del cálculo sRPE y de los endpoints.

#### Semana 7 — ACWR (EWMA)
**Objetivo:** evaluar riesgo de lesión (`RF-04.1`, `RF-04.2`).

- [x] Cálculo de Carga Aguda (EWMA 7 días) y Crónica (EWMA 28 días), `λ = 2/(N+1)`.
- [x] Ratio `ACWR` y matriz de alerta (Sweet Spot / Advertencia / Peligro).
- [x] Ensamblado de carga diaria (TRIMP carrera + sRPE gimnasio) en `core/metrics/load.py`.
- [x] Tests de la serie EWMA, del agregado diario y de los umbrales.

#### Semana 8 — Modelo Banister (EDO)
**Objetivo:** modelar Fitness-Fatiga (`RF-03.1`).

- [x] Recurrencia exacta (`impulse_response`) + resolución numérica con `scipy.integrate.solve_ivp` (`odeint` deprecado).
- [x] Calcular `P(t) = P0 + k1·g(t) − k2·h(t)` y `Freshness`.
- [x] Tests de estabilidad y de respuesta a un impulso de carga.
- [x] Bench para verificar `RNF-02` (< 0.5 s).

#### Semana 9 — Filtro de Kalman Extendido (EKF)
**Objetivo:** ajustar parámetros individuales (`RF-03.2`).

- [x] Implementar EKF con `filterpy` para estimar `k_1, k_2, tau_1, tau_2` (estado aumentado).
- [x] Integrar observaciones de rendimiento (el EKF las consume; la extracción real de ritmo a HR constante se difiere a S14).
- [x] Tests con datos sintéticos (convergencia de parámetros).

---

### Fase 2 — API y Dashboard (Mes 3)

#### Semana 10 — Backend FastAPI
**Objetivo:** exponer métricas y simulaciones (`RF-05`).

- [x] Endpoints REST: `/metrics/trimp/{exercise_id}`, `/metrics/acwr`, `/metrics/banister`, `/simulate`.
- [x] Modelos Pydantic (`src/athlete_stress_sim/backend/schemas/metrics.py`) de request/response.
- [x] Integración con DuckDB y el motor fisiológico.
- [x] Tests de integración de la API (`tests/test_metrics_api.py`).

#### Semana 11 — Dashboard (skeleton + panel de estado)
**Objetivo:** estructura visual y panel diario (`RF-05.1`).

- [x] App `src/athlete_stress_sim/frontend/app.py` con Plotly Dash + Mantine (tema oscuro, `RNF-04`).
- [x] Semáforo de *Readiness Score* y métrica de *Freshness* (`frontend/readiness.py`, `frontend/components/status.py`).
- [x] Layout responsive y componentes base (cliente HTTP `frontend/api.py`, carga inicial + botón Refresh).

#### Semana 12 — Dashboard (Fitness-Fatiga + ACWR)
**Objetivo:** visualizar la dinámica del modelo.

- [x] Gráfico de Fitness / Fatiga / Forma (TSB) a lo largo del tiempo (`frontend/components/fitness_chart.py`).
- [x] Tacómetro de riesgo ACWR con matriz de colores (`frontend/components/acwr_gauge.py`).
- [x] Panel de estado fisiológico completo y conectado a la API (`frontend/app.py`).

#### Semana 13 — Simulador de tapering y desacoplamiento
**Objetivo:** planificación predictiva (`RF-05.2`, `RF-05.3`).

- [x] Entrada de entrenamientos futuros proyectados (ej. "12 km a 5:00/km") vía formulario (`frontend/components/simulator.py`) + `POST /simulate/taper` (sRPE `RPE × duración`).
- [x] Gráfico predictivo de fatiga/forma hasta el día de la Media Maratón (histórico sólido + pronóstico discontinuo).
- [x] Métrica de desacoplamiento aeróbico `EF = velocidad / HR` por kilómetros (`core/metrics/decoupling.py` + `GET /metrics/decoupling/{id}`).
- [x] Tests del simulador y de la métrica EF.

---

### Fase 3 — Uso real, validación y portfolio (Mes 4)

#### Semana 14 — Integración en rutina real y validación
**Objetivo:** poner el sistema a trabajar con datos reales.

- [ ] Sincronizar al menos 2 semanas de datos reales (3 gym + 3 carrera).
- [ ] Validar parámetros EKF contra observaciones reales.
- [ ] Ajustar tapering para las semanas previas a la Media Maratón.
- [ ] Corrección de bugs encontrados en uso real.

#### Semana 15 — Optimización, Docker y CI/CD
**Objetivo:** dejar el sistema robusto y reproducible (`RNF-03`).

- [ ] Optimizar consultas DuckDB y tiempos de simulación.
- [ ] Empaquetado final Docker y `docker compose up` en frío.
- [ ] Pipeline CI/CD verde (lint + test) en `.github/workflows/ci.yml`.

#### Semana 16 — Documentación pública y portfolio
**Objetivo:** cerrar el proyecto presentable.

- [ ] `README.md` público en inglés con:
  - [ ] Explicación matemática (ecuaciones LaTeX).
  - [ ] Diagrama de arquitectura.
  - [ ] Capturas reales del dashboard.
- [ ] Revisión de credenciales expuestas y limpieza de secretos.
- [ ] Tag de release `v1.0.0`.

---

## 7. Criterios de aceptación por fase

### Fase 0 — DoD
- [x] Se puede autenticar contra Polar AccessLink y persistir tokens.
- [x] Una sesión de carrera queda persistida en DuckDB con series segundo a segundo.
- [x] Entorno Docker reproducible con `docker compose up`.
- [x] Tests de `src/athlete_stress_sim/core/etl` en verde.

### Fase 1 — DoD
- [x] TRIMP (carrera y gym), ACWR, EDO Banister y EKF implementados y testeados.
- [x] Cobertura de `src/athlete_stress_sim/core` ≥ 80 %.
- [x] Simulación EDO < 0.5 s.

### Fase 2 — DoD
- [x] API FastAPI sirve métricas y simulaciones.
- [x] Dashboard (dark mode) muestra estado fisiológico, Fitness/Fatiga/Forma, ACWR y simulador de tapering.
- [x] End-to-end: dashboard ↔ API ↔ DuckDB funcional.

### Fase 3 — DoD
- [ ] Sistema validado con ≥ 2 semanas de datos reales.
- [ ] CI/CD verde y despliegue Docker reproducible.
- [ ] `README.md` público completo (inglés, LaTeX, diagramas, capturas).

---

## 8. Riesgos y mitigaciones

| Riesgo | Impacto | Probabilidad | Mitigación |
|--------|---------|--------------|------------|
| Dependencia de disponibilidad/rate-limit de la API Polar | Alto | Media | Sincronización *catch-up* idempotente (arranque + botón) con reintentos/backoff y `Retry-After`; cacheo local (S3). |
| `AccessLink` v4 (Dynamic API, JSON) podría simplificar la ingesta | Medio | Baja | Evaluada en S3; se mantiene v3 (FIT/TCX) y la migración se difiere a F3 si aporta valor. |
| Datos insuficientes para calibrar el EKF (pocas semanas) | Alto | Media | Usar priors bibliográficos; arrancar con valores de referencia (S1). |
| Complejidad matemática (EDO + EKF) consume más tiempo del previsto | Alto | Media | Separar métricas (F1) de modelos (F1 tardía); priorizar TRIMP/ACWR como MVP. |
| Curva de aprendizaje de Plotly Dash + Mantine | Medio | Media | Esqueleto temprano (S11); componentes reutilizables. |
| Fixtures `.FIT` de ejemplo limitadas | Medio | Baja | Generar datos sintéticos además de capturas reales (S4). |
| Exposición accidental de credenciales | Alto | Baja | `.env` en `.gitignore`; revisión final (S16). |

---

## 9. Priorización (MoSCoW)

**Must have (núcleo del MVP):**
- `RF-01` Ingesta Polar + DuckDB
- `RF-02` TRIMP (carrera + gym)
- `RF-04` ACWR
- `RF-03.1` EDO Banister
- `RF-05.1` Panel de estado
- `RNF-01`, `RNF-02`, `RNF-03`

**Should have (alto valor, esfuerzo medio):**
- `RF-05.2` Simulador de tapering
- `RF-03.2` EKF
- `RF-05.3` Desacoplamiento aeróbico

**Could have (si sobra tiempo):**
- Exportación de reportes (PDF/CSV).
- Comparativas entre bloques de entrenamiento.
- Alertas push/email de riesgo ACWR.

**Won't have (fuera de alcance del cuatrimestre):**
- Soporte multi-usuario real (solo usuario cero).
- Integración con otros dispositivos (Garmin, Whoop).

---

## 10. Cómo se actualiza este roadmap

1. **Al inicio de cada sprint:** se revisa el sprint en curso y se mueve a `[~]` la casilla maestra correspondiente.
2. **Durante el sprint:** se marcan las tareas individuales a medida que se completan.
3. **Al final del sprint:** se verifica el DoD de la fase y se actualiza su casilla en `## 7`.
4. **Cambios de alcance:** cualquier desviación del PRD se refleja aquí con una nota y, si es estructural, se propaga también al PRD.
5. El historial de decisiones se registra en los mensajes de `git commit` y en issues/PRs del repositorio.

> **Regla de oro:** si una tarea no aparece en este documento, o bien no forma parte del alcance, o bien debe añadirse explícitamente antes de implementarse.
