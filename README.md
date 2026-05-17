# Proyecto Productivización — Predicción de Aglomeración en el Metro de Londres

API en Flask que sirve un modelo de Machine Learning para predecir el nivel de **aglomeración (crowding)** en estaciones del Metro de Londres según el día y la hora.

> **Equipo:** Juan Antonio y Pablo
> **Asignatura:** Productivización
> **Stack:** Python · Flask · XGBoost · TfL Open Data · Render (despliegue)

---

## ¿Por qué este proyecto?

Google Maps y el Journey Planner de TfL ya predicen tiempos de viaje en tiempo real. Nuestro proyecto se enfoca en una pregunta distinta que esas herramientas **no responden**: *"¿Cómo de aglomerada va a estar una estación o línea concreta a una hora futura?"*

Esto es útil para:

- Decidir entre viajar ahora o esperar para ir más cómodo.
- Personas con ansiedad social, claustrofobia o que viajan con niños / sillas de ruedas.
- Planificación de viajes turísticos.

---

## Endpoints de la API

| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET` | `/health` | Estado del servicio. |
| `GET` | `/crowding/<estacion>` | Predicción de aglomeración en `<estacion>` para la hora actual. Parámetro en el **path**. |
| `GET` | `/crowding?estacion=...&dia=...&hora=...` | Predicción con control fino. Parámetros en la **query string**. |
| `POST` | `/crowding` | Predicción avanzada. Acepta JSON en el **body** con varias estaciones y condiciones (clima, eventos). |

Ejemplos de petición y respuesta en `docs/ejemplos.md`.

---

## Estructura del repositorio

```
.
├── app.py                # Servidor Flask y rutas
├── requirements.txt      # Dependencias
├── README.md             # Este archivo
├── data/                 # Datos crudos y limpios (no se sube)
├── models/               # Modelos entrenados (.pkl)
├── notebooks/            # Análisis exploratorio y entrenamiento
├── src/                  # Scripts auxiliares
│   ├── descarga.py       # Bajar datos de TfL Open Data
│   ├── preprocesado.py   # Limpieza y feature engineering
│   └── entrenamiento.py  # Entrenar y guardar el modelo
└── docs/
    └── ejemplos.md       # Ejemplos de peticiones HTTP
```

---

## Cómo ejecutar en local

1. Clonar el repositorio y entrar en la carpeta:
   ```bash
   git clone <url-repo>
   cd Proyecto_p
   ```
2. Crear y activar un entorno virtual:
   ```bash
   python -m venv venv
   source venv/bin/activate     # Linux / Mac
   venv\Scripts\activate        # Windows
   ```
3. Instalar dependencias:
   ```bash
   pip install -r requirements.txt
   ```
4. Arrancar el servidor de desarrollo:
   ```bash
   python app.py
   ```
5. Probar con curl o Postman:
   ```bash
   curl http://localhost:5000/health
   ```

---

## Despliegue

- **Plataforma:** Render (plan gratuito) como red de seguridad.
- **Plataforma de upgrade:** AWS EC2 (si llegamos a tiempo).
- **Servidor de producción:** gunicorn.
- **URL pública:** pendiente.

---

## Fuente de datos

**Dataset principal: NUMBAT** (Network Usage Model Briefing And Tracking) de TfL.

- **URL:** https://crowding.data.tfl.gov.uk/
- **Documentación:** https://crowding.data.tfl.gov.uk/NUMBAT/Intro_to_NUMBAT.pdf
- **Granularidad temporal:** 15 minutos a lo largo de un día tipo.
- **Granularidad espacial:** estación individual del Metro, Overground, DLR y Elizabeth Line.
- **Distinción de día:** weekday / Saturday / Sunday.
- **Años cubiertos:** 2017 a 2024.
- **Formato:** Excel (`.xlsx`) con hojas para Entry, Exit, OD, Link.
- **Acceso:** descarga HTTP directa, sin API key ni scraping.
- **Licencia:** TfL Open Data Licence (compatible con Open Government Licence).

**Datasets de apoyo:**

- *Station Entry & Exit annual figures* (2007-2024) como variable de escala anual por estación.
- *TfL Unified API* (endpoint `/Crowding/{id}/Live`) para comparaciones en tiempo real durante la demo.

---

## Estado del proyecto

Trabajo en curso. Ver el plan completo en `docs/plan.md`.
