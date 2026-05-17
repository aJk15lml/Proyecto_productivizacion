# Contexto del Proyecto — Predicción de Aglomeración en el Metro de Londres

> Documento fuente para NotebookLM y otros asistentes.
> Última actualización: mayo de 2026.

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

NUMBAT (*Network Usage Model Briefing And Tracking*) es el modelo de uso de red publicado por Transport for London (TfL) bajo licencia abierta.

### Características

- **URL del portal:** https://crowding.data.tfl.gov.uk/
- **Documentación oficial (PDF):** https://crowding.data.tfl.gov.uk/NUMBAT/Intro_to_NUMBAT.pdf
- **Granularidad temporal:** 15 minutos a lo largo de un día tipo.
- **Granularidad espacial:** estación individual del Metro (Tube), Overground, DLR y Elizabeth Line.
- **Distinción de día:** *weekday*, *Saturday* y *Sunday*.
- **Años disponibles:** desde 2017 hasta 2024 (snapshots por temporada).
- **Formato:** archivos Excel (`.xlsx`) con hojas separadas para Entry (entradas), Exit (salidas), OD (matriz origen-destino) y Link (flujos por tramo de línea).
- **Acceso:** descarga HTTP directa, sin necesidad de API key, registro o scraping.
- **Licencia:** TfL Open Data Licence, compatible con la UK Open Government Licence.

### Naturaleza del dato — importante

NUMBAT **no representa observaciones diarias crudas**: es un *día tipo reconciliado* construido a partir de fuentes múltiples (recuentos manuales, datos de Oyster, validaciones contactless, modelos internos). Esto es una **ventaja** para entrenar un modelo (datos limpios, sin huecos, sin valores atípicos por incidencias puntuales) y una **limitación** si se quisiera capturar variabilidad real día a día. Para el alcance de este proyecto, la ventaja pesa más.

---

## Datasets complementarios

Se contempla el uso opcional de fuentes adicionales:

- **Station Entry & Exit annual figures (2007–2024):** publicadas por TfL y London Datastore. Sirven como *feature de escala* del volumen anual de cada estación para normalizar la predicción.
- **TfL Unified API — endpoint `/Crowding/{NaptanId}/Live`:** datos casi en tiempo real. Útil **únicamente para la demo** (comparar predicción del modelo frente a estado real durante la presentación). Requiere registro gratuito con `app_id` y `app_key`.
- **Open-Meteo (API de clima):** integración planificada para el Nivel 4 del proyecto. Permite añadir lluvia y temperatura como features que modulan la aglomeración. Sin API key.

---

## Stack técnico

| Capa | Tecnología |
|------|------------|
| Lenguaje | Python 3.11+ |
| API | Flask 3.x |
| Servidor de producción | gunicorn |
| Manipulación de datos | pandas, numpy |
| Modelado | scikit-learn, XGBoost |
| Serialización del modelo | joblib |
| Cliente HTTP | requests |
| Variables de entorno | python-dotenv |
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

## Reparto del trabajo

- **Juan Antonio** se encarga de la **API Flask** y del **despliegue**. Esta es la parte que el enunciado evalúa directamente y la más representativa del rol de productivización.
- Un asistente IA (Claude) se encarga de la parte de **datos y modelo**: descarga, limpieza, exploración (EDA), feature engineering y entrenamiento. Produce el archivo `modelo.pkl` que el equipo integra en la API.
- Asistentes complementarios (ChatGPT, Perplexity, NotebookLM) se utilizan para **investigación puntual** y **decisiones técnicas concretas** (por ejemplo, qué años de NUMBAT seleccionar, cómo justificar decisiones de diseño, qué features añadir).

---

## Filosofía de desarrollo

El proyecto se construye siguiendo el principio **"MVP primero, escalar por niveles"**. Cada nivel debe estar **desplegado y funcionando con URL pública** antes de iniciar el siguiente. Esto garantiza que, ocurra lo que ocurra, siempre haya una versión entregable.

### Niveles previstos

**Nivel 1 — Base entregable (red de seguridad).** Descarga de datos NUMBAT, modelo XGBoost simple con features básicas (estación, día de semana, hora, mes), API Flask con las cuatro rutas, despliegue en Render. Hasta que esto no esté vivo en internet, no se toca nada más.

**Nivel 2 — Pulido y métricas.** Enriquecimiento del modelo con más features (línea de metro, zona tarifaria, número de líneas que cruzan la estación), endpoint público con métricas de evaluación del modelo (MAE, RMSE, R²), mejor manejo de errores y validación de inputs.

**Nivel 3 — Demo visual.** Página HTML servida en la raíz `/` con formulario interactivo, llamadas JavaScript a la propia API, visualización con Chart.js o un mini-mapa (Leaflet/Folium).

**Nivel 4 — Features avanzadas.** Integración del clima mediante Open-Meteo (lluvia, temperatura), lista de festivos del Reino Unido y eventos relevantes (partidos en Wembley, conciertos en O2 Arena), reentrenamiento con dataset enriquecido.

**Nivel 5 — Bonus tracks.** Despliegue alternativo en AWS EC2 con nginx + gunicorn + systemd, segundo modelo (LSTM con Keras) para comparar enfoques clásicos vs deep learning, dominio propio con HTTPS gestionado por Let's Encrypt, contenedorización con Docker.

---

## Decisiones tomadas

1. **Tema descartado:** predicción de tiempo de viaje. Motivo: competir contra Google Maps no aporta valor diferencial.
2. **Tema descartado:** detección de sarcasmo. Motivo: problema NLP muy difícil, alto riesgo de demo embarazosa, escasa escalabilidad.
3. **Tema descartado:** fake news. Motivo: viable pero genérico, muchos otros equipos lo eligen.
4. **Tema elegido:** crowding en Metro de Londres.
5. **Dataset elegido:** NUMBAT de TfL. Motivo: granularidad de quince minutos, por estación individual, sin API key, múltiples años.
6. **Años a descargar:** 2017, 2019, 2023 y 2024. Se descartan 2020, 2021 y 2022 por distorsión COVID y recuperación parcial. Se omite 2018 por redundancia con 2017 y 2019.
7. **Años para entrenamiento principal:** 2023 y 2024 (post-COVID estabilizados). Total de tipos de día: MON, TWT, FRI, SAT y SUN (los cinco que NUMBAT publica desde 2023).
8. **Uso de 2017 y 2019:** validación de robustez del modelo y *narrativa de la presentación* (mostrar cómo el teletrabajo post-COVID ha alterado el patrón de aglomeración del Metro). No se usan en entrenamiento principal porque su taxonomía de días (MTT, FRI, SAT, SUN) es distinta a la post-2023 y mezclarlos contaminaría la señal.
9. **Modelo elegido:** XGBoost para Nivel 1. LSTM se contempla solo como Nivel 5 opcional.
10. **Despliegue inicial:** Render. Motivo: simplicidad y red de seguridad antes de aventuras con AWS.
11. **Despliegue secundario:** AWS EC2 como upgrade opcional, no como única opción inicial.
12. **Idioma del código y documentación:** español (variables, comentarios, README).
13. **Variable objetivo del modelo:** regresión sobre número de pasajeros por franja de quince minutos. La discretización en niveles (Bajo/Medio/Alto/Saturado) se aplicará por encima en la respuesta de la API, no en el target del modelo.

---

## Decisiones pendientes

- Si limitar el alcance al Metro (Tube) o incluir también Overground, DLR y Elizabeth Line.
- Si entrenar un modelo único para todas las estaciones (con `station_id` como feature) o un modelo por estación.
- Cómo manejar la nomenclatura de estaciones (NAPTAN ID vs nombre legible) para los endpoints.
- Qué umbrales aplicar para mapear el número de pasajeros predicho a las etiquetas Bajo/Medio/Alto/Saturado en la respuesta de la API (probablemente percentiles por estación).

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
- **NAPTAN ID**: identificador estándar nacional de paradas de transporte en Reino Unido.
- **TfL**: Transport for London, organismo público responsable del transporte en Londres.
- **MVP**: *Minimum Viable Product*, primera versión funcional y entregable de un producto.
- **gunicorn**: servidor WSGI de producción para aplicaciones Python como Flask.
- **Render**: plataforma de despliegue PaaS con plan gratuito, conexión directa con GitHub.
- **AWS EC2**: servicio de máquinas virtuales de Amazon Web Services.
