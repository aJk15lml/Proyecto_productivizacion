"""
Carga del modelo XGBoost y logica de prediccion.

El modelo se serializo con joblib y contiene un dict con:
  - "model": XGBRegressor entrenado (target = log1p(passengers))
  - "features": lista de 12 nombres de columna
  - "features_categoricas": ["NLC", "day_type"]
  - "day_type_categories": ["MON","TWT","FRI","SAT","SUN"]
"""

import os
import gc
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Rutas (configurables por variable de entorno)
# ---------------------------------------------------------------------------

RAIZ = Path(__file__).resolve().parent.parent.parent
MODEL_DIR = os.getenv("MODEL_DIR", str(RAIZ / "models"))
RUTA_MODELO = os.getenv("RUTA_MODELO", os.path.join(MODEL_DIR, "xgboost_prod.pkl"))
RUTA_PARQUET = os.getenv("RUTA_PARQUET", str(RAIZ / "data" / "processed" / "numbat_long.parquet"))

# ---------------------------------------------------------------------------
# Estado global (carga perezosa)
# ---------------------------------------------------------------------------

_modelo = None
_features = None
_features_cat = None
_day_types = None
_nlc_categories = None  # lista ordenada de los 432 NLCs que vio el modelo

# Lookup eficiente: dict NLC->info + lista para busqueda por nombre
_stations_by_nlc = None
_stations_list = None

# Percentiles de aglomeracion POR ESTACION (calculados del parquet diurno)
_station_percentiles = None  # dict: NLC -> {"p25": ..., "p50": ..., "p75": ...}


# ---------------------------------------------------------------------------
# Carga
# ---------------------------------------------------------------------------

def _cargar_modelo():
    global _modelo, _features, _features_cat, _day_types
    if _modelo is not None:
        return
    if not os.path.exists(RUTA_MODELO):
        raise FileNotFoundError(f"Modelo no encontrado en {RUTA_MODELO}")
    blob = joblib.load(RUTA_MODELO)
    _modelo = blob["model"]
    _features = blob["features"]
    _features_cat = blob.get("features_categoricas", ["NLC", "day_type"])
    _day_types = blob.get("day_type_categories", ["MON", "TWT", "FRI", "SAT", "SUN"])
    del blob  # liberar ~38 MB
    gc.collect()


def _cargar_lookup():
    global _stations_by_nlc, _stations_list, _station_percentiles, _nlc_categories
    if _stations_by_nlc is not None:
        return
    if not os.path.exists(RUTA_PARQUET):
        raise FileNotFoundError(f"Parquet de lookup no encontrado en {RUTA_PARQUET}")
    df = pd.read_parquet(RUTA_PARQUET)
    cols_interes = [
        "NLC", "ASC", "station_name_numbat", "UniqueStationName",
        "fare_zone_str", "InnerFareZone", "OuterFareZone",
        "FullyGated", "Hub", "Active", "TfL",
        "Latitude", "Longitude", "num_lines", "num_modes",
    ]
    cols_interes = [c for c in cols_interes if c in df.columns]
    lookup = df[cols_interes].drop_duplicates(subset="NLC").copy()
    lookup["NLC"] = lookup["NLC"].astype(int)

    _stations_by_nlc = {}
    _stations_list = []
    for _, row in lookup.iterrows():
        rec = row.to_dict()
        nlc = int(rec["NLC"])
        _stations_by_nlc[nlc] = rec
        _stations_list.append(rec)

    # Lista ordenada de NLCs para castear como categorical explicito
    _nlc_categories = sorted(_stations_by_nlc.keys())

    # Percentiles POR ESTACION (solo diurno)
    _station_percentiles = {}
    diurno = df[df["is_night"] == False] if "is_night" in df.columns else df
    if "passengers" in diurno.columns and len(diurno) > 0:
        pcts = diurno.groupby("NLC")["passengers"].quantile([0.25, 0.50, 0.75]).unstack()
        for nlc in _stations_by_nlc:
            if nlc in pcts.index:
                row = pcts.loc[nlc]
                _station_percentiles[nlc] = {
                    "p25": float(row.iloc[0]) if not pd.isna(row.iloc[0]) else 0,
                    "p50": float(row.iloc[1]) if not pd.isna(row.iloc[1]) else 0,
                    "p75": float(row.iloc[2]) if not pd.isna(row.iloc[2]) else 0,
                }
            else:
                _station_percentiles[nlc] = {"p25": 0, "p50": 0, "p75": 0}
    del df, lookup  # liberar memoria
    gc.collect()


# ---------------------------------------------------------------------------
# Logica de negocio
# ---------------------------------------------------------------------------

MAPEO_DIA = {
    "MON": "lunes", "TWT": "martes-miercoles-jueves", "FRI": "viernes",
    "SAT": "sabado", "SUN": "domingo",
    "lunes": "MON", "martes": "TWT", "miercoles": "TWT", "jueves": "TWT",
    "viernes": "FRI", "sabado": "SAT", "domingo": "SUN",
}


def normalizar_dia(dia: str) -> str:
    d = dia.strip().lower()
    return {
        "mon": "MON", "twt": "TWT", "fri": "FRI", "sat": "SAT", "sun": "SUN",
        "lunes": "MON", "martes": "TWT", "miercoles": "TWT", "jueves": "TWT",
        "viernes": "FRI", "sabado": "SAT", "domingo": "SUN",
    }.get(d, dia.upper())


def nivel_aglomeracion(pasajeros: float, nlc: int) -> str:
    p = _station_percentiles.get(nlc) if _station_percentiles is not None else None
    if p is None or (p["p25"] == 0 and p["p50"] == 0 and p["p75"] == 0):
        # fallback si no hay percentiles para esta estacion
        if pasajeros < 5:
            return "Bajo"
        elif pasajeros < 20:
            return "Medio"
        elif pasajeros < 80:
            return "Alto"
        return "Saturado"
    if pasajeros <= p["p25"]:
        return "Bajo"
    elif pasajeros <= p["p50"]:
        return "Medio"
    elif pasajeros <= p["p75"]:
        return "Alto"
    return "Saturado"


def predecir_estacion(
    estacion_nombre: str,
    dia: str,
    hora: int,
) -> dict:
    """
    Predice aglomeracion para una estacion.

    Parametros:
        estacion_nombre: nombre de la estacion (busqueda flexible)
        dia: dia tipo (MON/TWT/FRI/SAT/SUN o en español)
        hora: hora del dia (0-23)

    Retorna dict con resultado o error.
    """
    _cargar_modelo()
    _cargar_lookup()

    # Buscar estacion
    dia_norm = normalizar_dia(dia)

    lookup_item = None
    posibilidades = []

    # Busqueda exacta por NLC primero
    if estacion_nombre.isdigit():
        nlc_key = int(estacion_nombre)
        if nlc_key in _stations_by_nlc:
            lookup_item = _stations_by_nlc[nlc_key]

    if lookup_item is None:
        for s in _stations_list:
            nombre = str(s.get("UniqueStationName", "")).lower()
            nombre_nbt = str(s.get("station_name_numbat", "")).lower()
            asc = str(s.get("ASC", "")).lower()
            nlc = str(s.get("NLC", ""))

            if nombre == estacion_nombre.lower() or nombre_nbt == estacion_nombre.lower():
                lookup_item = s
                break
            if estacion_nombre.lower() in nombre or estacion_nombre.lower() in nombre_nbt:
                posibilidades.append(s.get("UniqueStationName", s.get("station_name_numbat", "")))
            if estacion_nombre == asc or estacion_nombre == nlc:
                lookup_item = s
                break

    if lookup_item is None:
        if posibilidades:
            return {"error": f"Estacion no encontrada. Quizas quisiste decir: {', '.join(posibilidades[:5])}"}
        return {"error": f"Estacion '{estacion_nombre}' no encontrada. Usa GET /stations para ver el listado completo."}

    # Construir fila de features
    nlc_val = lookup_item["NLC"]
    lat = float(lookup_item.get("Latitude", 0) or 0)
    lon = float(lookup_item.get("Longitude", 0) or 0)
    num_lines = int(lookup_item.get("num_lines", 0) or 0)
    num_modes_val = int(lookup_item.get("num_modes", 0) or 0)
    iz = int(lookup_item.get("InnerFareZone", 0) or 0)
    oz = int(lookup_item.get("OuterFareZone", 0) or 0)
    tiene_modo = 1 if num_modes_val > 0 else 0
    is_peak = 1 if dia_norm in ("MON", "TWT", "FRI") and (7 <= hora < 9.5 or 17 <= hora < 19.5) else 0
    is_night = 1 if hora < 5 else 0

    fila = pd.DataFrame([{
        "NLC": nlc_val,
        "day_type": dia_norm,
        "hour": hora,
        "num_lines": num_lines,
        "num_modes": num_modes_val,
        "tiene_modo_tfl_explicito": tiene_modo,
        "InnerFareZone": iz,
        "OuterFareZone": oz,
        "Latitude": lat,
        "Longitude": lon,
        "is_peak": is_peak,
        "is_night": is_night,
    }])

    # Casteos necesarios para XGBoost (enable_categorical=True)
    fila["NLC"] = pd.Categorical(fila["NLC"], categories=_nlc_categories, ordered=False)
    fila["day_type"] = pd.Categorical(fila["day_type"], categories=_day_types, ordered=False)

    # Predecir y deshacer log1p
    y_pred_log = _modelo.predict(fila[_features])[0]
    pasajeros = float(np.clip(np.expm1(y_pred_log), 0, None))

    nombre_estacion = lookup_item.get("UniqueStationName") or lookup_item.get("station_name_numbat") or str(nlc_val)

    return {
        "estacion": nombre_estacion,
        "NLC": int(nlc_val),
        "dia": dia_norm,
        "hora": hora,
        "pasajeros_15min_estimados": round(pasajeros, 1),
        "nivel_aglomeracion": nivel_aglomeracion(pasajeros, int(nlc_val)),
        "score": round(pasajeros / 6000, 2),  # normalizado aprox sobre maximo
        "latitud": lat,
        "longitud": lon,
    }


def predecir_multiples(estaciones: list[dict]) -> list[dict]:
    """Recibe una lista de {estacion, dia, hora} y devuelve predicciones."""
    resultados = []
    for item in estaciones:
        nombre = item.get("estacion", "")
        dia = item.get("dia", "TWT")
        hora = item.get("hora", 12)
        res = predecir_estacion(nombre, dia, hora)
        resultados.append(res)
    return resultados


def listar_estaciones() -> list[dict]:
    _cargar_lookup()
    return [
        {
            "NLC": s["NLC"],
            "nombre": s.get("UniqueStationName") or s.get("station_name_numbat"),
            "zona": s.get("fare_zone_str"),
            "lineas": int(s.get("num_lines", 0) or 0),
            "modos": int(s.get("num_modes", 0) or 0),
            "latitud": s.get("Latitude"),
            "longitud": s.get("Longitude"),
        }
        for s in _stations_list
    ]


def detalle_estacion(nlc_o_nombre: str) -> dict | None:
    _cargar_lookup()
    for s in _stations_list:
        if str(s.get("NLC")) == nlc_o_nombre or \
           str(s.get("UniqueStationName", "")).lower() == nlc_o_nombre.lower() or \
           str(s.get("station_name_numbat", "")).lower() == nlc_o_nombre.lower():
            return {
                "NLC": int(s["NLC"]),
                "nombre": s.get("UniqueStationName") or s.get("station_name_numbat"),
                "nombre_numbat": s.get("station_name_numbat"),
                "ASC": s.get("ASC"),
                "zona": s.get("fare_zone_str"),
                "InnerFareZone": int(s.get("InnerFareZone", 0) or 0),
                "OuterFareZone": int(s.get("OuterFareZone", 0) or 0),
                "num_lines": int(s.get("num_lines", 0) or 0),
                "num_modes": int(s.get("num_modes", 0) or 0),
                "FullyGated": s.get("FullyGated"),
                "Hub": s.get("Hub"),
                "Active": s.get("Active"),
                "TfL": s.get("TfL"),
                "latitud": float(s.get("Latitude", 0) or 0),
                "longitud": float(s.get("Longitude", 0) or 0),
            }
    return None
