# Guía funcional y de interpretación del dashboard

Esta guía explica qué calcula **Athlete Stress Sim**, qué representa cada panel del dashboard y
cómo leer sus gráficas. Está pensada para usar la aplicación, no para sustituir al
[PRD](../athlete-stress-sim-PRD.md) ni al [ROADMAP](../ROADMAP.md), que son la referencia de
producto y planificación.

> No es consejo médico. Las métricas son estimaciones de carga interna y fatiga; úsalas para
> detectar tendencias, no para diagnosticar lesiones ni sustituir la valoración de un profesional.

## 1. Qué hace la aplicación

La aplicación convierte las sesiones de Polar en una serie diaria de carga y la usa para estimar
fitness, fatiga y riesgo de sobrecarga:

```text
Polar AccessLink
      │  descarga FIT
      ▼
DuckDB local (exercises, samples, session_rpe)
      │
      ├─ Carrera  → TRIMP de Banister
      └─ Fuerza   → session-RPE de Foster
      │
      ▼
Carga diaria (suma por día, días de descanso = 0)
      │
      ├─ ACWR (EWMA aguda 7 d / crónica 28 d)
      └─ Modelo Banister (fitness, fatiga, freshness)
      │
      ▼
FastAPI → Dashboard Dash/Mantine
```

- **Carrera**: la carga se calcula con el TRIMP de Banister integrado sobre la frecuencia cardíaca
  segundo a segundo.
- **Fuerza/gimnasio**: la carga se calcula con el session-RPE de Foster, `RPE × duración_min`. Para
  que cuente, la sesión debe tener un RPE registrado.
- **Carga diaria**: se suman las cargas de todas las sesiones de un día. Los días sin sesión entre
  la primera y la última fecha se rellenan con `0` para que la fatiga pueda decaer.
- **Unidades**: ambas cargas se expresan en unidades arbitrarias (AU) y el proyecto las trata como
  una escala común. No son magnitudes fisiológicas idénticas: sirven para comparar tendencias, no
  para comparar el valor absoluto de una sesión de fuerza con el de una carrera.

## 2. Cómo abrir el dashboard y actualizar los datos

```bash
make run-backend    # API en http://localhost:8000 (documentación interactiva en /docs)
make run-frontend   # dashboard en http://localhost:8050
```

- El botón **Refresh** lanza primero `POST /sync` (descarga y parsea las sesiones nuevas de Polar)
  y después recalcula todas las métricas. La sincronización es idempotente: no vuelve a descargar
  lo que ya está registrado. Si no se puede sincronizar, verás `Sync failed.` junto al botón y el
  dashboard se recarga con los datos locales.
- El dashboard muestra un aviso naranja **RPE pending** cuando hay sesiones de gimnasio sin RPE.
  Al pulsarlo se abre un diálogo para elegir la sesión e introducir su RPE
  (`POST /exercises/{id}/rpe`). Sin RPE, esa sesión no aporta carga.
- Si el backend no responde, el dashboard muestra textos como `Backend offline`, `No data yet` o
  `No training history yet`; no son errores de cálculo.

## 3. Mapa del dashboard

El dashboard se carga una vez al abrirlo y después se actualiza con **Refresh**. De arriba abajo:

| Zona | Contenido | Para qué sirve |
| --- | --- | --- |
| Cabecera | Título, aviso **RPE pending** y botón **Refresh** | Sincronizar, recargar métricas y completar RPE pendientes. |
| Fila superior izquierda | **Daily status** | Semáforo de preparación diaria y freshness actual. |
| Fila superior derecha | Tacómetro **ACWR** | Riesgo de sobrecarga según la carga aguda frente a la crónica. |
| Centro | **Fitness / Fatigue / Freshness** | Evolución del modelo de fitness-fatiga. |
| Panel inferior 1 | **Aerobic decoupling** | Deriva cardiovascular por kilómetro en una carrera. |
| Panel inferior 2 | **Tapering simulator** | Pronóstico de fitness-fatiga al añadir sesiones futuras. |
| Panel inferior 3 | **Race taper** | Plan de descarga automático hasta la Media Maratón. |

El aviso **RPE pending** solo aparece si hay sesiones de fuerza sin RPE. Muestra el número de
pendientes y abre un diálogo con un desplegable de sesiones, un campo de RPE, **Save RPE** y
**Apply**. Cada **Save RPE** guarda esa sesión y la quita del desplegable; **Apply** cierra el
diálogo y recalcula todas las métricas con los RPE ya guardados.

Los textos de la interfaz están en inglés; este documento usa esos mismos nombres para que puedas
localizarlos en pantalla.

## 4. Panel de estado diario (`Daily status`)

Muestra un semáforo calculado únicamente a partir del **freshness** del último día:

| Color | Nivel | Freshness (`F`) | Lectura práctica |
| --- | --- | --- | --- |
| Verde | **Ready** | `F >= 0` | La aptitud supera a la fatiga; buen momento para una sesión de calidad. |
| Amarillo | **Caution** | `-5 <= F < 0` | Fatiga acumulada moderada; conviene controlar la intensidad. |
| Rojo | **Rest** | `F < -5` | Fatiga alta; prioriza recuperación. |
| Gris | Sin datos | — | Todavía no hay historial de entrenamiento. |

El valor `Freshness: +X.X AU` es la diferencia neta del modelo:

```text
Freshness = k1 · fitness − k2 · fatiga
```

Con los valores por defecto (`k1 = 1`, `k2 = 2`) equivale a `fitness − 2 · fatiga`; el PRD lo
resume como `fitness − fatiga` porque usa la misma idea de balance neto. Un freshness negativo
justo después de una sesión dura es normal: la fatiga sube rápido y decae con una constante de
tiempo más corta que la aptitud. Lo relevante es la tendencia y cuánto tarda en recuperarse, no un
valor aislado.

## 5. Tacómetro ACWR

El ACWR (Acute:Chronic Workload Ratio) compara la carga reciente con la carga de las últimas
semanas:

```text
EWMA_hoy = λ · carga_hoy + (1 − λ) · EWMA_ayer
λ = 2 / (N + 1)
ACWR = EWMA_aguda(7 días) / EWMA_crónica(28 días)
```

El tacómetro muestra el **último día disponible** y colorea el número según la zona:

| Zona | ACWR | Significado |
| --- | --- | --- |
| **Undertraining** (azul) | `< 0.8` | Carga reciente baja frente al historial; posible desacondicionamiento. |
| **Sweet spot** (verde) | `0.8 – 1.3` | Progresión considerada segura. |
| **Warning** (amarillo) | `> 1.3 – 1.5` | Incremento de carga a vigilar. |
| **Danger** (rojo) | `> 1.5` | Pico de carga; riesgo elevado de sobrecarga. |

Cómo interpretarlo:

- Un ACWR cercano a `1` indica que la carga aguda es similar a la crónica.
- Un valor alto significa que los últimos 7 días pesan mucho más que la base de 28 días; suele
  aparecer tras un bloque intenso o al volver de un parón.
- Un valor bajo puede indicar descarga, taper o pérdida de estímulo, no necesariamente algo malo.
- El dial está dibujado de `0` a `2.0`; si el valor real supera `2.0`, el indicador numérico se
  sigue mostrando, pero queda fuera de la escala visual.
- El EWMA se inicializa con el primer valor de carga, así que los primeros días parten de un ACWR
  de `1.0` y van convergiendo. Hasta acumular varias semanas (idealmente ~28 días), el valor está
  dominado por el arranque y debe leerse con cautela.
- El ACWR es una señal de carga, no una predicción de lesión: no incorpora sueño, estrés, terreno,
  edad ni calidad del descanso.

## 6. Gráfica `Fitness / Fatigue / Freshness`

Tres líneas con la evolución diaria del modelo de Banister:

| Línea | Color | Qué representa |
| --- | --- | --- |
| **Fitness** | Azul | Aptitud acumulada; sube con la carga y decae lentamente. |
| **Fatigue** | Rojo | Fatiga acumulada; sube con la carga y decae rápidamente. |
| **Freshness (TSB)** | Verde | Balance neto `k1 · fitness − k2 · fatiga`; positivo = preparado. |

El modelo usa una recurrencia diaria:

```text
fitness_t = fitness_{t−1} · e^(−1/τ1) + carga_t
fatiga_t  = fatiga_{t−1}  · e^(−1/τ2) + carga_t
freshness_t = k1 · fitness_t − k2 · fatiga_t
performance_t = p0 + freshness_t
```

Valores por defecto: `τ1 = 45` días, `τ2 = 15` días, `k1 = 1`, `k2 = 2`, `p0 = 0`. Se pueden
cambiar con las variables `ATHLETE_TAU_1`, `ATHLETE_TAU_2`, `ATHLETE_K_1`, `ATHLETE_K_2` y
`ATHLETE_P0`.

Patrones habituales:

- **Bloque de carga**: la fatiga sube más rápido que el fitness, el freshness cae y luego se
  recupera al reducir la carga. Es el comportamiento esperado de una sobrecarga funcional.
- **Taper**: al bajar la carga, la fatiga cae antes que el fitness; el freshness repunta mientras
  el fitness se mantiene. Esa es la señal que busca el simulador.
- **Descanso prolongado**: ambas curvas bajan; el freshness puede subir, pero también se pierde
  fitness.
- **Días sin sesión**: se introducen como carga `0`, de modo que las curvas decaen en lugar de
  quedarse planas.

La gráfica muestra solo el historial persistido, no el pronóstico. El eje X usa etiquetas
`mes día` (sin año), y el eje Y está en AU: compara formas y tendencias, no valores absolutos entre
personas. La API también devuelve `performance`, pero el dashboard no la dibuja.

> El dashboard calibra los parámetros con el EKF a partir del rendimiento observado (EF por
> carrera). Si hay pocas observaciones o el ajuste no explica suficiente varianza (R² bajo), se
> usan los **priors** de configuración como respaldo. Puedes consultar el resultado en
> `GET /metrics/ekf`.

## 7. Panel de desacoplamiento aeróbico (`Aerobic decoupling`)

Este panel analiza una carrera concreta, seleccionable en **Run**. Calcula el factor de eficiencia
por kilómetro:

```text
EF_km = velocidad_media_km / FC_media_km
```

La gráfica de barras muestra `EF` en cada kilómetro. Un EF más alto significa más velocidad a la
misma frecuencia cardíaca, es decir, mejor eficiencia aeróbica.

El porcentaje de desacoplamiento compara las dos mitades de la carrera:

```text
decoupling = (EF_media_primera_mitad − EF_media_segunda_mitad)
             / EF_media_primera_mitad × 100
```

- **Valor positivo**: el EF cayó en la segunda mitad; hay deriva cardiovascular (mismo pulso, menos
  velocidad). Puede indicar fatiga, deshidratación, calor, terreno o falta de durabilidad.
- **Valor cercano a cero**: eficiencia estable durante toda la carrera.
- **Valor negativo**: el EF subió en la segunda mitad; suele ocurrir al calentar o al regular mejor
  el esfuerzo.

Requisitos y matices:

- Hacen falta al menos **2 kilómetros con datos válidos** de velocidad y FC; si no, el panel indica
  `Not enough data to compute decoupling`.
- Se usa velocidad, no ritmo: por eso un EF mayor siempre es mejor, aunque en ritmo (`min/km`) un
  número menor sea más rápido.
- La aplicación no define umbrales de bueno/malo. Como referencia orientativa de entrenamiento (no
  implementada en el código), se suele considerar aceptable una deriva inferior a ~5 %, pero el
  contexto (calor, hidratación, desnivel, duración) importa más que el número aislado.
- Compara la misma ruta y condiciones, y mira la tendencia entre sesiones más que una única carrera.

## 8. Simulador de tapering (`Tapering simulator`)

Permite añadir sesiones futuras y ver cómo evolucionarían fitness, fatiga y freshness:

1. Rellena **Date**, **Distance (km)**, **Pace (min/km)** y **RPE (0–10)**.
2. Pulsa **Add** para añadir la sesión a la lista; **Clear** vacía la lista.
3. Pulsa **Simulate** para pedir el pronóstico al backend (`POST /simulate/taper`).

La carga de una sesión planificada se estima como:

```text
duración_min = distancia_km × ritmo_min_km
carga = RPE × duración_min
```

Es decir, se usa session-RPE también para las carreras proyectadas, para mantener la misma escala
de AU que el historial. No es un TRIMP calculado con FC futura, porque esa FC no existe.

La gráfica resultante:

- **Línea sólida**: historial real.
- **Línea discontinua**: pronóstico a partir de las sesiones añadidas.
- **Línea vertical punteada**: frontera entre historial y pronóstico.
- Si no hay historial, todo el trazado es pronóstico y la frontera no aparece.

Cómo usarlo:

- Añade las sesiones que planeas hasta la carrera y observa si el freshness llega positivo el día
  objetivo.
- Un taper correcto mantiene el fitness mientras la fatiga cae; si añades demasiada carga cerca de
  la carrera, la fatiga seguirá alta y el freshness no repuntará.
- El simulador no conoce el objetivo de tiempo ni el resultado real de la carrera: solo proyecta
  carga, fitness y fatiga.
- Las fechas deben ser futuras para que el pronóstico tenga sentido. El pronóstico usa los mismos
  parámetros que la gráfica histórica (calibrados si la validación lo permite, si no los priors).
- La escala de carga mezcla TRIMP de carrera y sRPE de fuerza; interpreta el resultado como
  tendencia relativa, no como una predicción exacta de rendimiento.

### Plan de taper hacia la carrera (`Race taper`)

El segundo formulario genera automáticamente un plan de descarga para las semanas previas a la
Media Maratón. Igual que el simulador, empieza **vacío** (sin valores precargados):

1. Rellena **Race date** (por ejemplo `2026-12-13`), **Weekly km**, **Runs/week**,
   **Pace (min/km)**, **RPE** y **Taper weeks**.
2. Pulsa **Plan taper** para pedir el plan al backend (`POST /simulate/taper/plan`).

El volumen semanal se reduce de forma lineal (factores `0.75 → 0.55 → 0.35` para tres semanas)
manteniendo el ritmo y el RPE, es decir, se conserva la intensidad. Las sesiones se colocan en
martes, jueves y domingo y nunca caen el día de la carrera, de modo que el freshness de la mañana
de carrera es el objetivo del pronóstico. La gráfica marca la carrera con una línea vertical.

Si quieres una referencia, `GET /metrics/running-baseline` devuelve el volumen semanal, el número
de carreras y el ritmo medios de las últimas cuatro semanas, pero el formulario no los precarga:
los introduces tú.

> El plan solo proyecta carrera: no reduce las sesiones de gimnasio. Ajusta esas sesiones aparte si
> quieres modelar la descarga completa.

## 9. Endpoints útiles

La API expone las mismas métricas que consume el dashboard. La documentación interactiva está en
`http://localhost:8000/docs`.

| Método | Ruta | Uso |
| --- | --- | --- |
| `GET` | `/health` | Comprobar que el backend está vivo. |
| `GET` | `/config/physiology` | Ver los priors fisiológicos activos (sin credenciales). |
| `GET` | `/auth/login` | Iniciar el flujo OAuth2 con Polar. |
| `GET` | `/auth/callback` | Callback OAuth2. |
| `GET` | `/auth/status` | Estado de la vinculación con Polar. |
| `GET` | `/auth/refresh` | Renovar el token de acceso. |
| `POST` | `/sync` | Descargar y parsear sesiones nuevas de Polar. |
| `GET` | `/sync/status` | Contadores de ingesta y sesiones parseadas. |
| `GET` | `/exercises?kind=all\|run\|gym` | Listar sesiones. |
| `GET` | `/exercises/{id}` | Ver una sesión. |
| `POST` | `/exercises/{id}/rpe` | Registrar el RPE de una sesión de fuerza. |
| `GET` | `/metrics/trimp/{id}` | Carga interna de una sesión. |
| `GET` | `/metrics/acwr` | Serie diaria de ACWR y zonas. |
| `GET` | `/metrics/banister` | Serie diaria de fitness, fatiga, performance y freshness. |
| `GET` | `/metrics/ekf` | Parámetros Banister calibrados por el EKF y su validación (R²). |
| `GET` | `/metrics/running-baseline` | Volumen, ritmo y RPE medios de las últimas 4 semanas. |
| `GET` | `/metrics/decoupling/{id}` | EF por kilómetro y desacoplamiento de una carrera. |
| `POST` | `/simulate` | Simular una serie de cargas diarias arbitraria. |
| `POST` | `/simulate/taper` | Simular sesiones planificadas sobre el historial. |
| `POST` | `/simulate/taper/plan` | Generar un plan de taper progresivo hasta race day. |

## 10. Limitaciones que afectan a la interpretación

- **Solo cuentan las sesiones con carga calculable**. Una sesión de fuerza sin RPE, o una carrera
  sin muestras de FC, no aporta carga y puede hacer que el ACWR y las curvas subestimen el
  entrenamiento real. Si añades un RPE que faltaba, las métricas cambiarán.
- **El historial de Polar es limitado**. El cliente consulta el listado de ejercicios de los
  últimos 30 días; lo ya descargado permanece en DuckDB. La primera sincronización no reconstruye
  meses de pasado.
- **La calibración del EKF depende de la cantidad de datos**. Con pocas semanas el rendimiento
  observado (EF) apenas varía y el ajuste puede no superar el umbral de calidad (R²), en cuyo caso
  el dashboard usa los priors. Consulta `/metrics/ekf` para ver si la calibración está activa.
- **El plan de taper solo modela carrera** y asume que el entrenamiento entre hoy y el inicio de la
  descarga sigue el historial; no reduce automáticamente las sesiones de gimnasio.
- **La carga combinada es una simplificación**: TRIMP de carrera y sRPE de fuerza se suman en AU
  aunque no sean equivalentes fisiológicamente.
- **El ACWR y el freshness son señales**, no diagnósticos. Valores altos o bajos deben contrastarse
  con cómo te sientes, el contexto de entrenamiento y la evolución a lo largo de varias semanas.
- **Refresh depende de que el backend pueda contactar con Polar**. Si el token ha caducado o no hay
  red, la sincronización falla (`Sync failed.`) pero las métricas locales siguen disponibles.
