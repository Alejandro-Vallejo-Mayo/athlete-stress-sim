# Product Requirements Document (PRD)

## Proyecto: Biomechanical Fatigue & Load Management Optimizer (Athleta-Stress-Sim)

- **Autor:** Estudiante de Doble Grado en Matemáticas e Ingeniería Informática (Universidad de Sevilla)
- **Usuario Cero / Caso de Uso:** Preparación personal de primera Media Maratón (3 días de carrera + 3 días de gimnasio)
- **Dispositivo Integrado:** Polar Ignite (vía Polar AccessLink API)
- **Estado:** En Definición / Planificación
- **Duración Estimada:** 4 Meses (1 Cuatrimestre)
- **Versión:** 1.0.0
- **Repositorio objetivo:** `athleta-stress-sim`

# 1. Visión General del Producto

## 1.1 Contexto y Motivación

En el entrenamiento de resistencia e híbrido (carrera a pie + gimnasio), la mayor causa de estancamiento y lesiones por sobrecarga (fascitis plantar, periostitis, tendinitis) es el desequilibrio entre la **carga de entrenamiento** y la **capacidad de recuperación neuromuscular**. Las métricas convencionales (volumen semanal en kilómetros o minutos) ignoran la respuesta fisiológica individual y la acumulación de fatiga a medio plazo.

## 1.2 Objetivo del Sistema

`Athleta-Stress-Sim` es una plataforma end-to-end de análisis fisiológico personal que:

1. Ingesta y procesa automáticamente la telemetría de entrenamientos desde la **API oficial de Polar AccessLink** al sincronizar el reloj Polar Ignite.
2. Cuantifica la carga de entrenamiento (**TRIMP de Banister/Edwards**) integrando tanto las sesiones de carrera como el entrenamiento de fuerza ajustado por RPE.
3. Modela la dinámica **Fitness-Fatiga** mediante **Ecuaciones Diferenciales Ordinarias (EDO)** y ajusta los parámetros fisiológicos individuales usando un **Filtro de Kalman Extendido (EKF)**.
4. Evalúa el riesgo de lesión mediante la ratio de Carga Aguda/Crónica (**ACWR**).
5. Ofrece un **Dashboard Interactivo de Rendimiento y Simulador de Tapering** para planificar cargas y optimizar la puesta a punto de cara a la Media Maratón.

# 2. Alcance y Arquitectura Técnica

## 2.1 Stack Tecnológico

| Componente | Tecnología Seleccionada | Justificación Técnica |
|------------|-------------------------|----------------------|
| **Lenguaje Core** | Python 3.11+ | Ecosistema científico unificado (`scipy`, `statsmodels`, `filterpy`). |
| **Ingesta de Datos** | `httpx2` + OAuth2 | Integración con la API REST Polar AccessLink y Webhooks. |
| **Parsing de Archivos** | `fitparse` | Extracción de telemetría punto a punto de archivos `.FIT` / `.TCX`. |
| **Persistencia Analítica** | **DuckDB** | Almacenamiento analítico embebido OLAP para series temporales. |
| **Motor Fisiológico** | `SciPy` (EDO) + `FilterPy` (EKF) | Resolución numérica de sistemas continuos e inferencia bayesiana. |
| **Backend API** | **FastAPI** | Endpoints de simulación, gestión de OAuth2 y webhooks. |
| **Dashboard** | **Plotly Dash** + Mantine Components | Interfaz web avanzada, moderna y responsive. |
| **Infraestructura** | **Docker Compose** | Despliegue empaquetado y reproducible. |
| **Gestión de paquetes** | **uv** (`pyproject.toml` + `uv.lock`) | Resolución y entornos reproducibles, rápida y compatible con PEP 517/518/621. |
| **Lint + Formato** | **Ruff** | Linter y formateador unificado (sustituye flake8/black/isort). |
| **Tipado estático** | **mypy** | Seguridad de tipos en el código científico/numérico. |
| **Testing** | **pytest** + `pytest-cov` | Tests unitarios e integración con cobertura. |
| **Git Hooks** | **pre-commit** | Lint/formato/tipado automáticos antes de cada commit. |
| **Orquestación** | **Makefile** | Comandos únicos (`make install`, `make lint`, `make test`, `make docker-up`). |

# 3. Requisitos Funcionales y Formulación Matemática

## RF-01: Módulo de Ingesta y Telemetría Polar

### RF-01.1

Implementación del flujo de autenticación **OAuth2** con Polar AccessLink API para vincular la cuenta del usuario.

### RF-01.2

Listener de webhooks/cron para descargar automáticamente nuevas sesiones (`exercises`) registradas por el Polar Ignite.

### RF-01.3 (Parsing de Telemetría)

Ingesta de series temporales segundo a segundo:

- Frecuencia cardíaca ($HR_t$)
- Ritmo ($Pace_t$)
- Cadencia
- Altitud

### RF-01.4 (Entrenamiento de Gimnasio)

Registro de sesiones con perfil *"Fuerza/Musculación"* y componente interactivo en dashboard para introducir el **RPE (Escala Borg 1-10)** post-entreno.

---

## RF-02: Cuantificación de la Carga Fisiológica (TRIMP)

### RF-02.1 (Carrera - TRIMP de Banister)

$$
TRIMP = D \cdot HR_r \cdot y
$$

donde

$$
HR_r = \frac{HR_{\text{media}} - HR_{\text{reposo}}}{HR_{\max} - HR_{\text{reposo}}}
$$

y

$$
y = e^{b \cdot HR_r}
\qquad (b = 1.92 \text{ para hombres})
$$

*(Donde $D$ es la duración en minutos).*

### RF-02.2 (Gimnasio - TRIMP Ajustado por RPE)

$$
TRIMP_{\text{Gym}}
=
D
\cdot
\left(
\frac{HR_{\text{media}} - HR_{\text{reposo}}}
{HR_{\max} - HR_{\text{reposo}}}
\right)
\cdot
\left(
\frac{RPE}{10}
\right)^\alpha
$$

---

## RF-03: Motor Fisiológico (Modelo Banister EDO + Filtro de Kalman)

### RF-03.1 (Ecuaciones Diferenciales Ordinarias)

Modelado del Rendimiento Neto $P(t)$ como respuesta a la secuencia de impulsos de carga $w(t)$:

$$
P(t)
=
P_0
+
k_1 \cdot g(t)
-
k_2 \cdot h(t)
$$

$$
\frac{dg(t)}{dt}
=
-\frac{1}{\tau_1}g(t)
+
w(t)
\qquad
\text{(Evolución de la Aptitud / Fitness)}
$$

$$
\frac{dh(t)}{dt}
=
-\frac{1}{\tau_2}h(t)
+
w(t)
\qquad
\text{(Evolución de la Fatiga)}
$$

Valores iniciales de referencia:

- $\tau_1 \approx 45$ días (aptitud)
- $\tau_2 \approx 15$ días (fatiga)

### RF-03.2 (Filtro de Kalman Extendido - EKF)

Inferencia bayesiana en tiempo real de las constantes individuales:

- $k_1$
- $k_2$
- $\tau_1$
- $\tau_2$

Ajustándose secuencialmente a medida que se registran nuevos entrenamientos y métricas de rendimiento observadas (por ejemplo, ritmo a pulso constante).

---

## RF-04: Prevención de Lesiones (ACWR - Acute:Chronic Workload Ratio)

### RF-04.1

Cálculo de la Carga Aguda (EWMA 7 días) y Carga Crónica (EWMA 28 días):

$$
ACWR_t
=
\frac{
\text{EWMA}_{\text{Aguda}}(7\text{ días})
}{
\text{EWMA}_{\text{Crónica}}(28\text{ días})
}
$$

### RF-04.2 (Matriz de Alerta de Riesgo)

- $ACWR < 0.8$: Sub-entrenamiento / Desacondicionamiento.
- $0.8 \le ACWR \le 1.3$: **Zona Dulce (Sweet Spot)**. Progresión segura.
- $1.3 < ACWR \le 1.5$: Zona de Advertencia.
- $ACWR > 1.5$: **Zona de Peligro (Spike de Carga)**. Alto riesgo de lesión por sobrecarga.

---

## RF-05: Dashboard Interactivo de Rendimiento

### RF-05.1 (Panel de Estado Fisiológico Diario)

- Semáforo de preparación diaria (*Readiness Score*).
- Métrica de forma física actual:

$$
Freshness = Fitness - Fatiga
$$

- Tacómetro de riesgo ACWR.

### RF-05.2 (Simulador de Tiradas y Tapering)

- Módulo donde introducir entrenamientos futuros proyectados (ej. *"Tirada larga de 18 km a 5:15 min/km el domingo"*).
- Gráfico predictivo que muestra cómo evolucionará la curva de fatiga y la forma física hasta el día de la Media Maratón.

### RF-05.3 (Análisis de Desacoplamiento Aeróbico)

Métrica:

$$
EF
=
\frac{\text{Ritmo o Potencia}}
{HR}
$$

calculada por kilómetros para detectar fatiga cardiovascular durante las tiradas largas.

# 4. Requisitos No Funcionales

### RNF-01 (Privacidad y Almacenamiento Local)

Todos los datos biométricos se almacenan en un archivo local `DuckDB` y nunca se comparten con terceros.

### RNF-02 (Rendimiento del Simulador)

Las simulaciones de EDO e integración numérica deben ejecutarse en:

$$
< 0.5 \text{ segundos}
$$

### RNF-03 (Despliegue Contenerizado)

Ejecución multi-servicio aislada vía Docker Compose.

### RNF-04 (Diseño Visual)

Interfaz oscura (*Dark Mode*) con estética deportiva moderna de alta densidad de información.

# 5. Estructura del Proyecto (Directorio)

```text
athleta-stress-sim/
├── .github/
│   └── workflows/
│       └── ci.yml               # Pipeline CI/CD (invoca targets del Makefile)
├── .pre-commit-config.yaml      # Git hooks (ruff, mypy, etc.)
├── docker/
│   ├── Dockerfile.backend
│   ├── Dockerfile.frontend
│   └── docker-compose.yml
├── data/
│   └── athleta.duckdb           # Base de datos analítica local
├── src/
│   └── athlete_stress_sim/      # Paquete único (src layout)
│       ├── __init__.py
│       ├── backend/
│       │   ├── api/             # Endpoints FastAPI y OAuth2 Polar
│       │   ├── config.py        # Credenciales API y constantes fisiológicas
│       │   ├── main.py          # App FastAPI
│       │   └── schemas/         # Modelos Pydantic
│       ├── core/
│       │   ├── etl/             # Client Polar AccessLink y Parser FIT
│       │   ├── metrics/         # Algoritmos TRIMP, ACWR y Desacoplamiento
│       │   └── models/          # Resolutor EDO Banister y Filtro de Kalman
│       └── frontend/
│           ├── app.py           # Aplicación Plotly Dash
│           └── components/      # Componentes del Dashboard
├── tests/
│   ├── test_etl.py
│   ├── test_metrics.py
│   └── test_banister_model.py
├── .env.example
├── .python-version              # Versión de Python fijada por uv
├── Makefile                     # Targets de desarrollo (install, lint, test, run, docker)
├── pyproject.toml               # Configuración única de dependencias y tooling
├── uv.lock                      # Lockfile reproducible
├── PRD.md
├── README.md
└── ROADMAP.md
```

# 6. Plan de Desarrollo por Hitos (4 Meses)

## Mes 1: Conexión Polar, Ingesta y DuckDB

1. Configuración del entorno (uv, pre-commit, Makefile) y repositorio Docker.
2. Implementación de la autenticación OAuth2 y llamadas a Polar AccessLink.
3. Desarrollo del parser para extraer frecuencia cardíaca, tiempo y ritmo.
4. Almacenamiento estructurado de las series temporales en DuckDB.

---

## Mes 2: Motor Fisiológico (TRIMP, ACWR y Modelo Banister EDO)

1. Implementación del cálculo de TRIMP de Banister/Edwards.
2. Implementación de TRIMP ajustado por RPE para gimnasio.
3. Desarrollo del módulo ACWR mediante EWMA.
4. Implementación del modelo Fitness-Fatiga usando `SciPy.integrate.odeint`.
5. Ajuste inicial de parámetros mediante **Filtro de Kalman Extendido (EKF)**.

---

## Mes 3: Dashboard Interactivo en Plotly Dash

1. Creación de la API REST en FastAPI para servir métricas y simulaciones.
2. Desarrollo del frontend en Plotly Dash.
3. Panel principal con:
   - Fitness
   - Fatiga
   - Forma (TSB, Training Stress Balance)
4. Indicador dinámico de riesgo ACWR.
5. Simulador predictivo de entrenamientos futuros y tapering.

---

## Mes 4: Uso Real en Entrenamiento, Validaciones y Portfolio

1. Integración completa del sistema en una rutina real (3 días de gym + 3 días de carrera).
2. Validación del simulador ajustando el tapering para las semanas previas a la Media Maratón.
3. Optimización de rendimiento y empaquetado Docker.
4. Redacción del `README.md` público en inglés incluyendo:
   - Explicaciones matemáticas.
   - Ecuaciones LaTeX.
   - Diagramas de arquitectura.
   - Capturas del dashboard real.
