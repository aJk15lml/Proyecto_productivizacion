FROM python:3.11-slim

WORKDIR /app

# Dependencias del sistema para pyarrow/numpy
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copiar todo el backend primero, luego instalar desde la ruta correcta
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el resto del backend (app es el paquete Python)
COPY backend/ .

# Copiar modelo y datos (necesarios para prediccion)
COPY models/ ./models/
COPY data/processed/ ./data/processed/

ENV MODEL_DIR=/app/models
ENV RUTA_MODELO=/app/models/xgboost_prod.pkl
ENV RUTA_PARQUET=/app/data/processed/numbat_long.parquet
ENV PORT=8000

EXPOSE 8000

CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "120"]
