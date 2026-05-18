# Plan del proyecto

Estrategia: **MVP primero, escalar por niveles**. Cada nivel debe estar desplegado y funcionando antes de empezar el siguiente.

---

## Nivel 1 — Base entregable (red de seguridad)

### Datos y modelo
- [x] Pivotar idea a "predicción de aglomeración en Metro de Londres".
- [x] Confirmar dataset de TfL óptimo → **NUMBAT** (granularidad 15 min, sin API key).
- [x] Cerrar años a descargar: 2017, 2019, 2023, 2024. Entrenamiento con 2023+2024; 2017/2019 como narrativa pre/post-COVID.
- [x] Cerrar variable objetivo: regresión sobre pasajeros por franja de 15 min; discretización a etiquetas se hará en la respuesta de la API.
- [x] Script de descarga (`src/descarga.py`) → 17 archivos NUMBAT + 2 de definiciones.
- [x] EDA inicial sobre datos crudos (`notebooks/01_exploracion_numbat.ipynb`): 471 estaciones, 432 válidas, 96 franjas, estructura de 3 filas de cabecera entendida.
- [x] Investigación de la metadata del PTSP Oasis: hojas Stations, Stn-Line, Stn-Mode, lat/lon, OSIs.
- [x] Script de preprocesado (`src/preprocesado.py`): wide → long, filtrado, join de metadata, features temporales. Salida: `data/processed/numbat_long.parquet` (414.720 × 23, 3.5 MB).
- [ ] EDA sobre el parquet procesado (`notebooks/02_eda_procesado.ipynb`): en curso. Pendiente: cerrar decisiones sobre log1p, filtrado num_modes==0 y split.
- [ ] Entrenar modelo XGBoost baseline. Features: NLC, day_type, hour, minute, num_lines, num_modes, fare_zone, lat/lon, is_peak, is_night. Métricas: MAE, RMSE, R² sobre 2024.
- [ ] Guardar modelo en `models/xgboost_v1.pkl` + métricas en `docs/metricas_v1.json`.
- [ ] Re-entrenar versión final con 2023+2024 para producción → `models/xgboost_prod.pkl`.

### API y despliegue
- [ ] Construir `app.py` con 4 rutas:
  - `GET /health`
  - `GET /crowding/<estacion>` (path)
  - `GET /crowding?estacion=...&dia=...&hora=...` (query)
  - `POST /crowding` (body JSON)
- [ ] Probar las rutas en local con Postman.
- [ ] Subir a GitHub.
- [ ] Desplegar en Render con URL pública.

**Salida esperada:** API funcionando, URL pública, README completo, ejemplos de peticiones.

---

## Nivel 2 — Pulido y métricas

- [ ] Endpoint `/modelo/metricas` con MAE, RMSE y R² del modelo.
- [ ] Mejor manejo de errores y validación de inputs.
- [ ] Búsqueda de nombre de estación tolerante (case-insensitive, partial match, acepta NLC o ASC).
- [ ] Tests unitarios mínimos de las rutas.

---

## Nivel 3 — Demo visual

- [ ] Página HTML servida en `/` con formulario (estación, día, hora).
- [ ] JavaScript que llama a la API y dibuja la predicción con Chart.js.
- [ ] Mini-mapa con las estaciones (Leaflet o Folium) coloreado por aglomeración predicha — el parquet ya trae `Latitude`/`Longitude`.

---

## Nivel 4 — Features avanzadas

- [ ] Integrar clima de Open-Meteo (lluvia, temperatura) como feature.
- [ ] Lista de festivos UK y eventos relevantes (Wembley, O2 Arena).
- [ ] Reentrenamiento del modelo con datos enriquecidos.

---

## Nivel 5 — Bonus tracks (solo si vamos sobrados)

- [ ] Despliegue alternativo en AWS EC2 con nginx + gunicorn + systemd.
- [ ] Segundo modelo (LSTM) para comparar enfoques ML clásico vs DL.
- [ ] Dominio propio + HTTPS con Let's Encrypt.
- [ ] Dockerización del proyecto.

---

## Reglas de oro

1. **Nunca pasar al siguiente nivel hasta que el actual esté desplegado y probado.**
2. **Commits limpios por nivel** (tags `v1.0`, `v2.0`...).
3. **Vídeo de respaldo grabado** desde el Nivel 1 por si la demo falla en vivo.
4. **Freeze de funcionalidades 2 días antes de la entrega**: solo bugs y presentación.
5. **Revisar coste de AWS** si se llega al Nivel 5 (alertas de billing activadas).
