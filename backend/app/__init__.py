"""
London Crowding API — Flask backend para prediccion de aglomeracion
en estaciones del Metro de Londres (NUMBAT dataset + XGBoost).

Rutas:
  GET  /health                  Estado del servicio
  GET  /health/<componente>     Estado de un componente
  GET  /crowding/<estacion>     Prediccion para una estacion (path)
  GET  /crowding                Prediccion con query params
  POST /crowding                Prediccion multiple (body JSON)
  GET  /stations                Listado de estaciones disponibles
  GET  /stations/<id>           Detalle de una estacion
"""

import os
from datetime import datetime, timezone

from flask import Flask, jsonify, request, render_template
from flask_cors import CORS

from .predictor import (
    predecir_estacion,
    predecir_multiples,
    listar_estaciones,
    detalle_estacion,
)
# ---------------------------------------------------------------------------
# Creacion de la app
# ---------------------------------------------------------------------------

app = Flask(__name__)
CORS(app)


# ---------------------------------------------------------------------------
# Rutas
# ---------------------------------------------------------------------------


@app.route("/", methods=["GET"])
def home():
    return render_template("index.html")


@app.route("/health", methods=["GET"])
def health():
    from .predictor import _modelo
    return jsonify({
        "status": "ok",
        "servicio": "London Crowding API",
        "modelo_cargado": _modelo is not None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


@app.route("/health/<componente>", methods=["GET"])
def health_componente(componente: str):
    checks = {
        "api": {"status": "healthy"},
        "modelo": {"status": "healthy", "ruta": os.getenv("RUTA_MODELO", "models/xgboost_prod.pkl")},
        "database": {"status": "healthy"},
    }
    resultado = checks.get(componente, {"status": "unknown"})
    return jsonify({"componente": componente, **resultado})


@app.route("/crowding/<estacion>", methods=["GET"])
def crowding_path(estacion: str):
    """
    GET /crowding/<estacion>
    Predice aglomeracion para la hora actual.
    """
    ahora = datetime.now()
    hora_actual = ahora.hour
    dia_semana = ahora.weekday()
    mapa_dia = {0: "MON", 1: "TWT", 2: "TWT", 3: "TWT", 4: "FRI", 5: "SAT", 6: "SUN"}
    dia = mapa_dia.get(dia_semana, "TWT")

    try:
        resultado = predecir_estacion(estacion, dia, hora_actual)
    except Exception as e:
        return jsonify({"error": f"Error interno del modelo: {str(e)}"}), 500

    if "error" in resultado:
        return jsonify(resultado), 404

    return jsonify(resultado)


@app.route("/crowding", methods=["GET"])
def crowding_query():
    """
    GET /crowding?estacion=...&dia=...&hora=...
    """
    estacion = request.args.get("estacion", "")
    dia = request.args.get("dia", "TWT")
    hora_str = request.args.get("hora", "12")

    if not estacion:
        return jsonify({"error": "Parametro obligatorio: ?estacion=..."}), 400

    try:
        hora = int(hora_str)
        if hora < 0 or hora > 23:
            return jsonify({"error": "La hora debe estar entre 0 y 23"}), 400
    except ValueError:
        return jsonify({"error": f"La hora debe ser un entero, recibido: {hora_str}"}), 400

    dias_validos = ["MON", "TWT", "FRI", "SAT", "SUN",
                    "lunes", "martes", "miercoles", "jueves",
                    "viernes", "sabado", "domingo"]
    if dia not in dias_validos:
        return jsonify({"error": "Dia invalido. Usa: MON/TWT/FRI/SAT/SUN o nombre en espanol"}), 400

    try:
        resultado = predecir_estacion(estacion, dia, hora)
    except Exception as e:
        return jsonify({"error": f"Error interno del modelo: {str(e)}"}), 500

    if "error" in resultado:
        return jsonify(resultado), 404

    return jsonify(resultado)


@app.route("/crowding", methods=["POST"])
def crowding_body():
    """
    POST /crowding
    Body JSON:
      {"estaciones": [{"estacion": "...", "dia": "...", "hora": ...}, ...]}
    """
    datos = request.get_json(silent=True)
    if not datos:
        return jsonify({"error": "Cuerpo JSON requerido"}), 400

    if isinstance(datos, list):
        estaciones = datos
    elif isinstance(datos, dict):
        estaciones = datos.get("estaciones", [datos])
    else:
        return jsonify({"error": "Formato invalido. Envia un array o {'estaciones': [...]}"}), 400

    if not estaciones:
        return jsonify({"error": "Lista de estaciones vacia"}), 400

    try:
        resultados = predecir_multiples(estaciones)
    except Exception as e:
        return jsonify({"error": f"Error interno del modelo: {str(e)}"}), 500

    return jsonify({"resultados": resultados})


@app.route("/stations", methods=["GET"])
def stations():
    try:
        estaciones = listar_estaciones()
        return jsonify({"total": len(estaciones), "estaciones": estaciones})
    except Exception as e:
        return jsonify({"error": f"Error al cargar estaciones: {str(e)}"}), 500


@app.route("/stations/<identificador>", methods=["GET"])
def station_detail(identificador: str):
    try:
        detalle = detalle_estacion(identificador)
        if detalle is None:
            return jsonify({"error": f"Estacion '{identificador}' no encontrada"}), 404
        return jsonify(detalle)
    except Exception as e:
        return jsonify({"error": f"Error: {str(e)}"}), 500


# ---------------------------------------------------------------------------
# Punto de entrada (solo para desarrollo)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
