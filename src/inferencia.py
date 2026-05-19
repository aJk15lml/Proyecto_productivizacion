"""
Inferencia end-to-end para la API.

Una sola funcion `predecir(blob, estacion, dia, hora)` que toma el blob cargado
de `xgboost_prod.pkl` y devuelve un dict listo para serializar a JSON. Maneja
busqueda de estacion por nombre o NLC, casteo correcto de categoricas (con la
lista de 432 NLCs y los 5 day_types), prediccion, deshacer log1p y
discretizacion en niveles POR ESTACION.

Uso desde la API:
    import joblib
    from inferencia import predecir, listar_estaciones

    blob = joblib.load("models/xgboost_prod.pkl")  # una sola vez al arrancar
    resultado = predecir(blob, "Waterloo LU", "TWT", 9)
    estaciones = listar_estaciones(blob)
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def _buscar_nlc(blob, estacion):
    meta = blob["station_metadata"]
    try:
        nlc = int(estacion)
        if nlc in meta:
            return nlc
    except (ValueError, TypeError):
        pass
    s = str(estacion).strip().lower()
    for nlc, info in meta.items():
        if info.get("UniqueStationName", "").lower() == s:
            return nlc
        if info.get("ASC", "").lower() == s:
            return nlc
    candidatos = [(nlc, info["UniqueStationName"]) for nlc, info in meta.items()
                  if s in info.get("UniqueStationName", "").lower()]
    if len(candidatos) == 1:
        return candidatos[0][0]
    if candidatos:
        candidatos.sort(key=lambda x: len(x[1]))
        return candidatos[0][0]
    return None


def _nivel_aglomeracion(pasajeros, nlc, blob):
    p = blob["percentiles_por_estacion"].get(nlc)
    if not p:
        return "Desconocido"
    if pasajeros <= p["p25"]:
        return "Bajo"
    elif pasajeros <= p["p50"]:
        return "Medio"
    elif pasajeros <= p["p75"]:
        return "Alto"
    return "Saturado"


def predecir(blob, estacion, dia, hora, minuto=0):
    """
    Args:
        blob: dict cargado de models/xgboost_prod.pkl
        estacion: nombre legible, ASC, o NLC (int o str)
        dia: "MON"/"TWT"/"FRI"/"SAT"/"SUN"
        hora: int 0-23
        minuto: 0, 15, 30 o 45. Default 0.

    Returns:
        dict para JSON, o {"error": "..."} si input invalido.
    """
    modelo = blob["model"]
    features = blob["features"]
    nlc_categories = blob["nlc_categories"]
    day_types = blob["day_type_categories"]
    meta = blob["station_metadata"]

    nlc = _buscar_nlc(blob, estacion)
    if nlc is None:
        return {"error": f"Estacion no encontrada: {estacion!r}"}
    if dia not in day_types:
        return {"error": f"day_type invalido: {dia!r}. Use uno de {day_types}"}
    if not (0 <= hora <= 23):
        return {"error": f"hora fuera de rango (0-23): {hora}"}

    info = meta[nlc]
    minutos_dia = hora * 60 + minuto
    is_peak = int(
        dia in ("MON", "TWT", "FRI")
        and ((7 * 60 <= minutos_dia < 9 * 60 + 30)
             or (17 * 60 <= minutos_dia < 19 * 60 + 30))
    )
    is_night = int(hora < 5)

    fila = pd.DataFrame([{
        "NLC": nlc,
        "day_type": dia,
        "hour": hora,
        "num_lines": info["num_lines"],
        "num_modes": info["num_modes"],
        "tiene_modo_tfl_explicito": info["tiene_modo_tfl_explicito"],
        "InnerFareZone": info["InnerFareZone"],
        "OuterFareZone": info["OuterFareZone"],
        "Latitude": info["Latitude"],
        "Longitude": info["Longitude"],
        "is_peak": is_peak,
        "is_night": is_night,
    }])

    # AMBAS categoricas con la lista EXACTA del entrenamiento
    fila["NLC"] = pd.Categorical(fila["NLC"], categories=nlc_categories, ordered=False)
    fila["day_type"] = pd.Categorical(fila["day_type"], categories=day_types, ordered=False)

    y_pred_log = modelo.predict(fila[features])[0]
    pasajeros = float(np.clip(np.expm1(y_pred_log), 0, None))

    return {
        "NLC": int(nlc),
        "estacion": info["UniqueStationName"],
        "ASC": info["ASC"],
        "dia": dia,
        "hora": hora,
        "minuto": minuto,
        "pasajeros_15min_estimados": round(pasajeros, 1),
        "nivel_aglomeracion": _nivel_aglomeracion(pasajeros, nlc, blob),
        "latitud": float(info["Latitude"]),
        "longitud": float(info["Longitude"]),
        "num_lines": int(info["num_lines"]),
        "num_modes": int(info["num_modes"]),
        "fare_zone_inner": int(info["InnerFareZone"]),
        "fare_zone_outer": int(info["OuterFareZone"]),
        "modelo_version": blob.get("version", "v1"),
    }


def listar_estaciones(blob):
    """Para el endpoint /stations (dropdown del frontend)."""
    meta = blob["station_metadata"]
    return [
        {
            "NLC": int(nlc),
            "nombre": info["UniqueStationName"],
            "ASC": info.get("ASC", ""),
            "zona": int(info["InnerFareZone"]),
            "lineas": int(info["num_lines"]),
            "modos": int(info["num_modes"]),
            "latitud": float(info["Latitude"]),
            "longitud": float(info["Longitude"]),
        }
        for nlc, info in sorted(meta.items(), key=lambda x: x[1]["UniqueStationName"])
    ]
