# Plan del proyecto

Estrategia: **MVP primero, escalar por niveles**. Cada nivel debe estar desplegado y funcionando antes de empezar el siguiente.

---

## Nivel 1 — Base entregable (red de seguridad)

- [x] Pivotar idea a "predicción de aglomeración en Metro de Londres".
- [x] Confirmar dataset de TfL óptimo → **NUMBAT** (granularidad 15 min, sin API key).
- [x] Cerrar años a descargar: 2017, 2019, 2023, 2024. Entrenamiento con 2023+2024; 2017/2019 como validación de robustez y narrativa pre/post-COVID.
- [x] Cerrar variable objetivo: regresión sobre pasajeros por franja de 15 min; discretización a etiquetas se hará en la respuesta de la API.
- [ ] Descargar y limpiar datos NUMBAT.
- [ ] Entrenar modelo XGBoost baseline con features: estación, día de la semana, hora, mes.
- [ ] Guardar modelo en `models/modelo.pkl`.
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

- [ ] Añadir más features al modelo: línea de metro, zona tarifaria, número de líneas que cruzan la estación.
- [ ] Endpoint `/modelo/metricas` con MAE, RMSE y R² del modelo.
- [ ] Mejor manejo de errores y validación de inputs.
- [ ] Tests unitarios mínimos de las rutas.

---

## Nivel 3 — Demo visual

- [ ] Página HTML servida en `/` con formulario (estación, día, hora).
- [ ] JavaScript que llama a la API y dibuja la predicción con Chart.js.
- [ ] Mini-mapa con las estaciones (idealmente con folium o leaflet).

---

## Nivel 4 — Features avanzadas

- [ ] Integrar clima de Open-Meteo (lluvia, temperatura) como feature.
- [ ] Lista de festivos y eventos relevantes (partidos en Wembley, conciertos en O2 Arena).
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
