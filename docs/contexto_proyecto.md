# Contexto del Proyecto — Predicción de Aglomeración en el Metro de Londres

> Documento fuente para NotebookLM y otros asistentes.
> Última actualización: 18 de mayo de 2026.

---

## Resumen ejecutivo

El proyecto consiste en desarrollar una **API REST en Flask** que incorpora un modelo de Machine Learning entrenado para predecir el **nivel de aglomeración (crowding)** en estaciones del Metro de Londres en función del día y la hora. La API se despliega en un entorno con URL pública. El proyecto forma parte de la asignatura "Productivización" y debe entregarse acompañado de un repositorio de GitHub, documentación técnica y una presentación oral de diez minutos seguida de cinco minutos de preguntas.

---

## El encargo

El enunciado oficial pide construir un servicio sencillo pero funcional que recorra el ciclo completo de un producto de datos: desarrollo, integración del modelo y despliegue.

### Requisitos obligatorios

La API debe exponer cuatro rutas:

1. Una ruta de **estado del servicio** (`/health`).
2. Una ruta con parámetros en el **path**.
3. Una ruta con parámetros en la **query string**.
4. Una ruta que reciba datos en el **cuerpo** (JSON).

El modelo debe cargarse **una sola vez al iniciar la aplicación** y emplearse dentro de al menos uno de los endpoints. El despliegue debe realizarse en una de estas plataformas: **AWS EC2**, **Render** o **PythonAnywhere**, dejando la API accesible mediante una URL pública.

### Entregables

- Nombres y apellidos de los integrantes del equipo.
- Repositorio con el código fuente.
- Archivo `requirements.txt`.
- Instrucciones para ejecutar el proyecto en local.
- URL del servicio desplegado.
- Ejemplos de peticiones y respuestas.
- Breve documentación técnica.
- Presentación oral con diagrama de arquitectura y demo en vivo.

La aplicación debe estar **activa durante la presentación**, con un vídeo grabado de respaldo por si fallara el despliegue en directo.

---

## Equipo

Juan Antonio Moreno y Pablo. Dos integrantes.

---

## Tema elegido y justificación

El proyecto se centra en la **predicción de aglomeración (crowding)** en estaciones de transporte público de Londres. La pregunta que la API responde es:

> *"¿Cómo de saturada va a estar la estación X el día Y a la hora Z?"*

### Por qué este tema (en vez de predecir tiempo de viaje)

Una primera propuesta — predecir el tiempo de viaje entre dos estaciones — se descartó tras evaluarla críticamente. Predecir el tiempo de viaje **es lo que ya hacen Google Maps y el Journey Planner oficial de TfL**, con datos en tiempo real procedentes de millones de usuarios. Un modelo entrenado con un dataset histórico no podría competir y el proyecto sería percibido como "una versión peor de Google Maps".

La aglomeración, en cambio, **no la predicen esas herramientas**. TfL solo expone el patrón típico actual; nadie ofrece predicción a futuro por estación y franja horaria de quince minutos. El valor diferencial es claro y defendible ante el tribunal de evaluación.

### Casos de uso defendibles

- Decidir entre viajar inmediatamente o esperar para ir más cómodo.
- Personas con ansiedad social, claustrofobia o sensibilidad sensorial.
- Viajeros con niños pequeños, sillas de ruedas, equipaje voluminoso.
- Planificación turística (evitar Oxford Circus o King's Cross saturadas).
- Optimización de rutas alternativas en hora punta.

---

## Dataset principal: NUMBAT

NUMBAT (*Network Usage Model Briefing And Tracking*) es el modelo de uso de red publicado por Transport for London (TfL) bajo licencia abierta. Cubre **London Underground + London Overground + DLR + Elizabeth Line** (Tramlink aparece listado pero no se mide).

### Características

- **URL del portal:** https://crowding.data.tfl.gov.uk/
- **Documentación oficial (PDF):** https://crowding.data.tfl.gov.uk/NUMBAT/Intro_to_NUMBAT.pdf
- **Granularidad temporal:** 15 minutos a lo largo de un día tipo (`HHMM-HHMM`, p. ej. `0500-0515`).
- **Granularidad espacial:** estación individual.
- **Tipos de día publicados:** varían con el año.
  - 2017: `MTT` (Mon-Thu Typical), `SAT`, `SUN` — 3 categorías.
  - 2019: `MTT`, `FRI`, `SAT`, `SUN` — 4 categorías (FRI separado).
  - 2023+: `MON`, `TWT` (Tue-Wed-Thu), `FRI`, `SAT`, `SUN` — **5 categorías**, separando el lunes post-COVID.
- **Años disponibles:** 2017 a 2024 (snapshots de otoño).
- **Formato:** archivos Excel (`.xlsx`), cada uno con **10 hojas internas**: `_Cover`, `LineLookUp`, `Link_Loads`, `Link_Frequencies`, `Line_Boarders`, `Station_Flows`, `Station_Entries`, `Station_Exits`, `Station_Boarders`, `Station_Alighters`.
- **Acceso:** descarga HTTP directa, sin necesidad de API key, registro o scraping.
- **Licencia:** TfL Open Data Licence, compatible con la UK Open Government Licence.

### Hoja utilizada: `Station_Entries`

De las 10 hojas, usamos `Station_Entries`, que da el número de pasajeros que **entran** por la puerta de cada estación en cada franja de 15 minutos. La diferencia con `Station_Boarders` es importante: *boarders* incluye también a quienes ya estaban dentro y cambian de línea; *entries* mide solo entradas desde la calle, que es la mejor señal para "aglomeración en la estación" en el MVP.

### Estructura técnica del archivo

- **Tres filas de cabecera apiladas.** La fila 0 trae etiquetas-paraguas (`Station Entries`, `hour (hr)`), la fila 1 sub-etiquetas (hora 5..28, índice qhr 21..116), y la **fila 2** contiene los **nombres reales** de columna. Hay que leer el Excel con `header=2`.
- **Columnas reales** (107 en total): `NLC`, `ASC`, `Station`, `Fare Zone`, `Total`, `Early`, `AM Peak`, `Midday`, `PM Peak`, `Evening`, `Late`, más las **96 franjas** de 15 minutos (`0500-0515`, `0515-0530`, …, `0445-0500`, cubriendo el ciclo operativo 05:00 → 04:59 del día siguiente).
- **471 filas por archivo** (todas las estaciones de la red de raíles TfL).
- **39 filas todas-cero** por archivo: estaciones de Tramlink u otras no medidas en NUMBAT. Se filtran antes de entrenar (`Total > 0`), dejando **432 estaciones válidas**.
- **Valores decimales** (no enteros) porque NUMBAT es un *modelo reconciliado* de día tipo, no un conteo crudo. Reconcilia Oyster, contactless, validaciones de torniquete y encuestas. Por ese motivo, además, días afectados por disrupciones o eventos (huelgas, fallos, partidos) **están excluidos** del dataset por TfL antes de publicarlo.

### Naturaleza del dato — importante

NUMBAT **no representa observaciones diarias crudas**: es un *día tipo reconciliado* construido a partir de fuentes múltiples. Esto es una **ventaja** para entrenar un modelo (datos limpios, sin huecos, sin valores atípicos por incidencias puntuales) y una **limitación** si se quisiera capturar variabilidad real día a día. Para el alcance de este proyecto, la ventaja pesa más.

---

## Dataset de metadata: PTSP Oasis for NUMBAT definitions

Archivo descargado junto a NUMBAT 2024 (`data/raw/2024/PTSP Oasis for NUMBAT definitions.xlsx`, 6.2 MB). Es el **diccionario oficial** del dataset y nos da el contexto estructural de cada estación que no está en los archivos NUMBAT principales. Tiene 24 hojas; usamos tres:

### Hoja `Stations` (970 estaciones)

Catálogo maestro con metadata por estación, incluyendo:

- `MasterNLC`, `MasterASC`, `UniqueStationName` — identificadores.
- `InnerFareZone`, `OuterFareZone` — zonas tarifarias (1 = centro, 9 = extrarradio; algunas estaciones son frontera y aparecen como `2/3`, `3/4`, etc.).
- `Latitude`, `Longitude` — **geolocalización exacta**, clave para el frontend con mapa (Nivel 3).
- `FullyGated` — indica si la estación tiene torniquetes completos (importante para calidad del dato).
- `Hub`, `Active`, `TfL` — flags adicionales.

### Hoja `Stn-Line` (970 × 48)

Matriz booleana **estación × línea**. Una columna por cada una de las 44 líneas catalogadas (Tube, Overground, DLR, EZL, Tram, National Rail…). Permite calcular `num_lines` como suma de columnas True para las líneas TfL.

### Hoja `Stn-Mode` (970 × 11)

Matriz booleana **estación × modo**. Permite calcular `num_modes` de forma análoga (cuántos modos TfL rail sirven la estación).

### Otras hojas relevantes (no usadas en MVP)

- `Modes` (9 modos catalogados), `Lines` (44 líneas), `OSIs` (161 *Out of Station Interchanges*, complejos de transbordo como Bank–Monument), `Stn-Naptan` (mapeo a NAPTAN ID nacional).

### Detalle de calidad

`Stn-Mode` tiene un duplicado conocido: NLC 866 (*West India Quay*) aparece dos veces. El script de preprocesado lo deduplica automáticamente para no inflar el join.

---

## Dataset procesado: `data/processed/numbat_long.parquet`

Salida del pipeline `src/preprocesado.py`. Es el archivo de entrada del modelo.

- **Filas:** 414.720 (= 432 estaciones × 96 franjas × 5 día-tipo × 2 años).
- **Columnas:** 23.
- **Tamaño:** 3.5 MB (parquet con compresión snappy, vs ~57 MB en CSV).
- **Carga:** instantánea con `pd.read_parquet`.

### Columnas del parquet

| Columna | Tipo | Origen | Significado |
|---------|------|--------|-------------|
| `NLC` | int32 | NUMBAT | National Location Code (identificador numérico). |
| `ASC` | str | NUMBAT | Código interno TfL (sufijo indica modo: `u`=Underground, `d`=DLR, `r`=Rail). |
| `station_name_numbat` | str | NUMBAT | Nombre de estación según NUMBAT. |
| `fare_zone_str` | str | NUMBAT | Zona tarifaria como string (`"1"`, `"2"`, `"2/3"`...). |
| `quarter_hour_slot` | str | NUMBAT | Franja de 15 min (`"0500-0515"`, ...). |
| `passengers` | float | NUMBAT | **Target**: pasajeros entrando en esa franja. |
| `year` | int16 | derivado | 2023 o 2024. |
| `day_type` | str | derivado | MON / TWT / FRI / SAT / SUN. |
| `UniqueStationName` | str | PTSP Oasis | Nombre canónico de estación. |
| `InnerFareZone`, `OuterFareZone` | int | PTSP Oasis | Zonas numéricas limpias. |
| `FullyGated` | str | PTSP Oasis | Estación con torniquetes completos. |
| `Hub`, `Active`, `TfL` | bool/str | PTSP Oasis | Flags de metadata. |
| `Latitude`, `Longitude` | float | PTSP Oasis | Geolocalización. |
| `num_lines` | int | derivado | Número de líneas TfL que cruzan la estación. |
| `num_modes` | int | derivado | Número de modos TfL rail que sirven la estación. |
| `hour`, `minute` | int8 | derivado | Hora y minuto del inicio de la franja. |
| `is_peak` | bool | derivado | True si 07:00-09:30 ó 17:00-19:30 en día laborable (MON/TWT/FRI). |
| `is_night` | bool | derivado | True si hour < 5 (horario de cierre del Metro). |

---

## Datasets adicionales (opcionales, no integrados aún)

- **TfL Unified API — endpoint `/Crowding/{NaptanId}/Live`:** datos casi en tiempo real. Útil **solo para la demo** (comparar predicción del modelo frente a estado real durante la presentación). Requiere registro gratuito con `app_id` y `app_key`.
- **Open-Meteo (API de clima):** integración planificada para el Nivel 4. Permite añadir lluvia y temperatura como features. Sin API key.
- **NUMBAT 2017 y 2019:** descargados pero **fuera del pipeline de entrenamiento**. Se conservan para análisis comparativo pre/post-COVID en la presentación (cambio del patrón de aglomeración por el teletrabajo).

---

## Stack técnico

| Capa | Tecnología |
|------|------------|
| Lenguaje | Python 3.11+ |
| API | Flask 3.x |
| Servidor de producción | gunicorn |
| Manipulación de datos | pandas, numpy, pyarrow |
| Modelado | scikit-learn, XGBoost |
| Serialización del modelo | joblib |
| Cliente HTTP | requests |
| Variables de entorno | python-dotenv |
| Notebooks | jupyterlab, matplotlib, seaborn |
| Control de versiones | Git + GitHub |
| Despliegue principal | Render (plan gratuito) |
| Despliegue opcional | AWS EC2 (con nginx + gunicorn + systemd) |

El modelo principal será **XGBoost** por su buen rendimiento sobre datos tabulares con estacionalidad, su ligereza (el `.pkl` pesa pocos MB) y su compatibilidad con los entornos de despliegue gratuitos.

---

## Arquitectura de la API

### Las cuatro rutas

1. **`GET /health`** — Devuelve el estado del servicio. Confirma que la API está viva y que el modelo se ha cargado correctamente.
2. **`GET /crowding/<estacion>`** (parámetro en path) — Predicción de aglomeración para una estación concreta a la hora actual.
3. **`GET /crowding?estacion=...&dia=...&hora=...`** (parámetros en query) — Versión con control fino: el cliente especifica estación, día de la semana y franja horaria.
4. **`POST /crowding`** (body JSON) — Versión avanzada que recibe un payload con varias estaciones y condiciones adicionales (por ejemplo, clima esperado) y devuelve un array de predicciones.

### Respuesta tipo

```json
{
  "estacion": "King's Cross St. Pancras",
  "dia": "viernes",
  "hora": "18:00",
  "nivel_aglomeracion": "Alto",
  "score": 0.87,
  "pasajeros_15min_estimados": 1240,
  "modelo_version": "v1.0"
}
```

---

## Estructura del repositorio

```
Proyecto_productivizacion/
├── README.md
├── requirements.txt          # Dependencias de producción
├── requirements-dev.txt      # Dependencias de desarrollo (jupyter, etc.)
├── data/
│   ├── raw/                  # Excels de NUMBAT + definiciones (gitignored)
│   └── processed/
│       └── numbat_long.parquet   # Dataset listo para entrenar
├── notebooks/
│   ├── 01_exploracion_numbat.ipynb   # EDA inicial sobre datos crudos
│   └── 02_eda_procesado.ipynb        # EDA sobre el parquet procesado
├── src/
│   ├── descarga.py           # Bajar Excels de NUMBAT
│   └── preprocesado.py       # Wide → long + join metadata + features
├── models/                   # Modelos entrenados (.pkl)
├── app.py                    # Servidor Flask con las 4 rutas (pendiente)
└── docs/
    ├── contexto_proyecto.md  # Este documento
    └── plan.md               # Plan por niveles con checkboxes
```

---

## Reparto del trabajo

- **Juan Antonio** se encarga de la **API Flask** y del **despliegue**. Esta es la parte que el enunciado evalúa directamente y la más representativa del rol de productivización.
- Un asistente IA (Claude) se encarga de la parte de **datos y modelo**: descarga, limpieza, exploración (EDA), feature engineering y entrenamiento. Produce el archivo `.pkl` del modelo que el equipo integra en la API.
- Asistentes complementarios (ChatGPT, Perplexity, NotebookLM) se utilizan para **investigación puntual** y **decisiones técnicas concretas** (por ejemplo, qué años de NUMBAT seleccionar, cómo justificar decisiones de diseño, qué features añadir).

---

## Filosofía de desarrollo

El proyecto se construye siguiendo el principio **"MVP primero, escalar por niveles"**. Cada nivel debe estar **desplegado y funcionando con URL pública** antes de iniciar el siguiente. Esto garantiza que, ocurra lo que ocurra, siempre haya una versión entregable.

### Niveles previstos

**Nivel 1 — Base entregable (red de seguridad).** Datos NUMBAT descargados y procesados, modelo XGBoost baseline con features básicas, API Flask con las cuatro rutas, despliegue en Render. Hasta que esto no esté vivo en internet, no se toca nada más.

**Nivel 2 — Pulido y métricas.** Mejora del modelo con todas las features disponibles del parquet, endpoint público con métricas (MAE, RMSE, R²), validación robusta de inputs, manejo de errores claro.

**Nivel 3 — Demo visual.** Página HTML servida en la raíz `/` con formulario interactivo y mapa de Londres (Leaflet/Folium) coloreando estaciones por aglomeración predicha. Las coordenadas ya están en el parquet, listas.

**Nivel 4 — Features avanzadas.** Integración del clima mediante Open-Meteo (lluvia, temperatura), lista de festivos UK y eventos relevantes (Wembley, O2 Arena), reentrenamiento con dataset enriquecido.

**Nivel 5 — Bonus tracks.** Despliegue alternativo en AWS EC2 con nginx + gunicorn + systemd, segundo modelo (LSTM con Keras) para comparar enfoques clásicos vs deep learning, dominio propio con HTTPS gestionado por Let's Encrypt, contenedorización con Docker.

---

## Decisiones tomadas

1. **Tema descartado:** predicción de tiempo de viaje. Motivo: competir contra Google Maps no aporta valor diferencial.
2. **Tema descartado:** detección de sarcasmo. Motivo: problema NLP muy difícil, alto riesgo de demo embarazosa, escasa escalabilidad.
3. **Tema descartado:** fake news. Motivo: viable pero genérico, muchos otros equipos lo eligen.
4. **Tema elegido:** crowding en Metro de Londres.
5. **Dataset elegido:** NUMBAT de TfL. Motivo: granularidad de quince minutos, por estación individual, sin API key, múltiples años.
6. **Años a descargar:** 2017, 2019, 2023 y 2024. Se descartan 2020, 2021 y 2022 por distorsión COVID y recuperación parcial. Se omite 2018 por redundancia con 2017 y 2019.
7. **Años para entrenamiento principal:** 2023 y 2024 (post-COVID estabilizados). Tipos de día: MON, TWT, FRI, SAT y SUN.
8. **Uso de 2017 y 2019:** análisis comparativo pre/post-COVID para la narrativa de la presentación. No se usan en entrenamiento principal porque su taxonomía de días (MTT, FRI, SAT, SUN) es distinta a la post-2023 y mezclarlos contaminaría la señal.
9. **Modelo elegido:** XGBoost para Nivel 1. LSTM se contempla solo como Nivel 5 opcional.
10. **Despliegue inicial:** Render. Motivo: simplicidad y red de seguridad antes de aventuras con AWS.
11. **Despliegue secundario:** AWS EC2 como upgrade opcional, no como única opción inicial.
12. **Idioma del código y documentación:** español (variables, comentarios, README).
13. **Variable objetivo del modelo:** regresión sobre número de pasajeros por franja de quince minutos. La discretización en niveles (Bajo/Medio/Alto/Saturado) se aplicará por encima en la respuesta de la API, no en el target del modelo.
14. **Hoja de NUMBAT a usar:** `Station_Entries` (no `Station_Boarders`, porque queremos medir aglomeración en la estación, no en los andenes).
15. **Filtrado de estaciones todas-cero:** se eliminan las 39 estaciones de Tramlink u otras no medidas (Total == 0). Quedan 432 estaciones válidas por archivo.
16. **Dedup de metadata:** la hoja `Stn-Mode` del PTSP Oasis trae NLC 866 (West India Quay) duplicado; el script de preprocesado lo deduplica para no inflar el join.

---

## Decisiones pendientes

- **¿Filtrar estaciones con `num_modes == 0`?** Son 121 estaciones que solo tienen modo National Rail (no TfL rail). NUMBAT sí las mide, pero la feature `num_modes` no las describe bien. Pendiente del EDA.
- **¿Aplicar `log1p` al target?** La distribución de `passengers` tiene cola larga (max ≈ 5961, mediana ≈ 39). Pendiente de confirmar en el EDA si compensa el log.
- **Split train/test:** entrenamiento con 2023 entero y test con 2024 entero (validación temporal) **o** pool 2023+2024 con split aleatorio (más datos pero sin test temporal). Pendiente del EDA: si los patrones 2023 vs 2024 son muy parecidos, ambos enfoques son similares; si difieren, el temporal es más informativo.
- **Umbrales de discretización** Bajo/Medio/Alto/Saturado en la respuesta de la API (probablemente percentiles por estación).
- **¿Modelo único o uno por estación?** En principio uno único con `NLC` como feature; XGBoost lo absorbe bien y es más simple de desplegar.

---

## Reglas operativas

1. Nunca pasar al siguiente nivel sin tener el actual desplegado, probado y commiteado.
2. Cada nivel termina con un *tag* de Git (`v1.0`, `v2.0`, etc.) para poder revertir en segundos.
3. Vídeo de respaldo grabado desde el momento en que el Nivel 1 esté vivo.
4. *Freeze* de funcionalidades dos días antes de la presentación: solo bugs y preparación de la demo.
5. Si se llega al despliegue en AWS, activar alertas de facturación desde el día uno y *terminate* la instancia tras la entrega.
6. Repositorio público en GitHub con README claro desde el primer commit.

---

## Glosario

- **API REST**: interfaz que expone funcionalidades de una aplicación a través de HTTP, siguiendo el estilo REST.
- **Endpoint** o **ruta**: cada URL que la API expone, asociada a una operación.
- **Path parameter**: parámetro que viaja como parte de la URL, por ejemplo `/usuarios/42`.
- **Query string**: parámetros que viajan tras `?` en la URL, por ejemplo `?nombre=ana&edad=30`.
- **Body**: cuerpo de la petición, habitualmente JSON, enviado en peticiones POST.
- **NUMBAT**: modelo de uso de red de TfL que estima flujos de pasajeros por estación y franja horaria de quince minutos.
- **NLC**: *National Location Code*. Identificador numérico nacional de cada estación de raíles en Reino Unido.
- **ASC**: código interno de TfL para cada estación (string corto, sufijo letra indica modo).
- **NAPTAN ID**: identificador estándar nacional de paradas de transporte en Reino Unido.
- **PTSP Oasis**: archivo de definiciones que acompaña a NUMBAT con metadata estructural.
- **OSI**: *Out of Station Interchange*. Transbordo entre estaciones físicamente separadas pero vinculadas (Bank ↔ Monument).
- **TfL**: Transport for London, organismo público responsable del transporte en Londres.
- **MVP**: *Minimum Viable Product*, primera versión funcional y entregable de un producto.
- **gunicorn**: servidor WSGI de producción para aplicaciones Python como Flask.
- **Render**: plataforma de despliegue PaaS con plan gratuito, conexión directa con GitHub.
- **AWS EC2**: servicio de máquinas virtuales de Amazon Web Services.
