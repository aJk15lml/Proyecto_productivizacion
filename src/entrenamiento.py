"""
Entrenamiento del modelo XGBoost baseline para prediccion de aglomeracion.

Pipeline:
1. Carga data/processed/numbat_long.parquet.
2. Prepara features (categoricas + numericas) y target (log1p).
3. Split temporal: train = 2023, test = 2024.
4. Entrena XGBoost con early stopping sobre un sub-split de train.
5. Evalua en test 2024 con metricas ESTRATIFICADAS (global / diurno / nocturno).
6. Guarda modelo de validacion en models/xgboost_v1.pkl.
7. Re-entrena con 2023+2024 entero para produccion.
8. Guarda modelo de produccion en models/xgboost_prod.pkl.
9. Exporta metricas a docs/metricas_v1.json.

Uso:
    python src/entrenamiento.py
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score


# ---------------------------------------------------------------------------
# Configuracion
# ---------------------------------------------------------------------------

RAIZ = Path(__file__).resolve().parent.parent
RUTA_PARQUET = RAIZ / "data" / "processed" / "numbat_long.parquet"
DIR_MODELOS = RAIZ / "models"
DIR_DOCS = RAIZ / "docs"

RUTA_MODELO_VAL = DIR_MODELOS / "xgboost_v1.pkl"
RUTA_MODELO_PROD = DIR_MODELOS / "xgboost_prod.pkl"
RUTA_METRICAS = DIR_DOCS / "metricas_v1.json"

ANIO_TRAIN = 2023
ANIO_TEST = 2024

DAY_TYPES = ["MON", "TWT", "FRI", "SAT", "SUN"]

FEATURES_NUM = [
    "hour",
    "num_lines",
    "num_modes",
    "tiene_modo_tfl_explicito",
    "InnerFareZone",
    "OuterFareZone",
    "Latitude",
    "Longitude",
    "is_peak",
    "is_night",
]
FEATURES_CAT = ["NLC", "day_type"]
FEATURES = FEATURES_CAT + FEATURES_NUM
TARGET = "passengers"

# Hiperparametros XGBoost (defaults razonables, tuning fino lo dejamos
# para Nivel 2 si hace falta).
PARAMS = {
    "n_estimators": 800,
    "learning_rate": 0.08,
    "max_depth": 8,
    "min_child_weight": 5,
    "subsample": 0.85,
    "colsample_bytree": 0.85,
    "objective": "reg:squarederror",
    "tree_method": "hist",
    "enable_categorical": True,
    "random_state": 42,
    "n_jobs": -1,
}
EARLY_STOPPING = 40
VAL_FRACTION = 0.15  # del train, para early stopping


# ---------------------------------------------------------------------------
# Preparacion de features
# ---------------------------------------------------------------------------

def preparar_features(df: pd.DataFrame) -> pd.DataFrame:
    """Anade features derivadas y castea categoricas para XGBoost."""
    df = df.copy()
    df["tiene_modo_tfl_explicito"] = (df["num_modes"] > 0).astype(np.int8)
    df["is_peak"] = df["is_peak"].astype(np.int8)
    df["is_night"] = df["is_night"].astype(np.int8)
    df["NLC"] = df["NLC"].astype("category")
    df["day_type"] = pd.Categorical(df["day_type"], categories=DAY_TYPES, ordered=False)
    return df


# ---------------------------------------------------------------------------
# Metricas
# ---------------------------------------------------------------------------

def calcular_metricas(y_real: np.ndarray, y_pred: np.ndarray, prefijo: str = "") -> dict:
    """Metricas en escala ORIGINAL (no log). MAE, RMSE, R2 y MAPE sobre no-cero."""
    y_real = np.asarray(y_real, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    metr = {
        f"{prefijo}n": int(len(y_real)),
        f"{prefijo}mae": float(mean_absolute_error(y_real, y_pred)),
        f"{prefijo}rmse": float(np.sqrt(mean_squared_error(y_real, y_pred))),
        f"{prefijo}r2": float(r2_score(y_real, y_pred)) if len(y_real) > 1 else None,
    }
    mask_no_cero = y_real > 1.0   # filtrar valores diminutos del modelo NUMBAT (0.001 etc.) que explotan el MAPE
    if mask_no_cero.any():
        mape = np.mean(np.abs(y_real[mask_no_cero] - y_pred[mask_no_cero]) / y_real[mask_no_cero])
        metr[f"{prefijo}mape_no_cero"] = float(mape)
        metr[f"{prefijo}mape_n"] = int(mask_no_cero.sum())
    else:
        metr[f"{prefijo}mape_no_cero"] = None
        metr[f"{prefijo}mape_n"] = 0
    return metr


def imprimir_metricas(titulo: str, m: dict, prefijo: str = "") -> None:
    print(f"\n  {titulo} (n = {m.get(prefijo + 'n', 'N/A'):,})")
    for k in ("mae", "rmse", "r2", "mape_no_cero"):
        v = m.get(prefijo + k)
        if v is None:
            print(f"    {k:18s}      N/A")
        elif "mape" in k:
            print(f"    {k:18s} {v*100:>9.2f}%")
        else:
            print(f"    {k:18s} {v:>10.4f}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    print(f"Cargando {RUTA_PARQUET.name}...")
    df = pd.read_parquet(RUTA_PARQUET)
    print(f"  {len(df):,} filas x {len(df.columns)} columnas")

    df = preparar_features(df)

    # Split temporal
    df_train_full = df[df["year"] == ANIO_TRAIN].copy()
    df_test = df[df["year"] == ANIO_TEST].copy()
    print(f"\nSplit temporal:")
    print(f"  Train ({ANIO_TRAIN}): {len(df_train_full):,} filas")
    print(f"  Test  ({ANIO_TEST}): {len(df_test):,} filas")

    # Sub-split de train para early stopping
    rng = np.random.default_rng(42)
    idx = np.arange(len(df_train_full))
    rng.shuffle(idx)
    n_val = int(len(idx) * VAL_FRACTION)
    idx_val = idx[:n_val]
    idx_fit = idx[n_val:]
    df_fit = df_train_full.iloc[idx_fit]
    df_val = df_train_full.iloc[idx_val]
    print(f"  Sub-split early stop: fit={len(df_fit):,}, val={len(df_val):,}")

    X_fit = df_fit[FEATURES]
    y_fit = np.log1p(df_fit[TARGET].values)
    X_val = df_val[FEATURES]
    y_val = np.log1p(df_val[TARGET].values)
    X_test = df_test[FEATURES]
    y_test_log = np.log1p(df_test[TARGET].values)
    y_test_real = df_test[TARGET].values

    # Entrenamiento (modelo de validacion)
    print(f"\nEntrenando XGBoost (con early stopping)...")
    t0 = time.time()
    modelo = xgb.XGBRegressor(**PARAMS, early_stopping_rounds=EARLY_STOPPING)
    modelo.fit(
        X_fit, y_fit,
        eval_set=[(X_val, y_val)],
        verbose=False,
    )
    secs = time.time() - t0
    print(f"  Entrenado en {secs:.1f}s.  best_iteration = {modelo.best_iteration}")

    # Predicciones en test (deshacer log)
    y_pred_log = modelo.predict(X_test)
    y_pred_real = np.clip(np.expm1(y_pred_log), 0, None)

    # Metricas estratificadas
    is_night = df_test["is_night"].values.astype(bool)
    m_global = calcular_metricas(y_test_real, y_pred_real, prefijo="global_")
    m_diurno = calcular_metricas(y_test_real[~is_night], y_pred_real[~is_night], prefijo="diurno_")
    m_nocturno = calcular_metricas(y_test_real[is_night], y_pred_real[is_night], prefijo="nocturno_")

    print(f"\n=== Metricas en test ({ANIO_TEST}) ===")
    imprimir_metricas("Global (todas las filas)", m_global, prefijo="global_")
    imprimir_metricas("Operacional / diurno", m_diurno, prefijo="diurno_")
    imprimir_metricas("Nocturno", m_nocturno, prefijo="nocturno_")

    # Importancia de features
    importancia = pd.Series(modelo.feature_importances_, index=FEATURES).sort_values(ascending=False)
    print(f"\n=== Importancia de features ===")
    for nombre, valor in importancia.items():
        print(f"  {nombre:30s} {valor:.4f}")

    # Guardar modelo de validacion
    DIR_MODELOS.mkdir(exist_ok=True)
    blob_val = {
        "model": modelo,
        "features": FEATURES,
        "features_categoricas": FEATURES_CAT,
        "features_numericas": FEATURES_NUM,
        "day_type_categories": DAY_TYPES,
        "version": "v1_validacion",
        "trained_on_year": ANIO_TRAIN,
        "evaluated_on_year": ANIO_TEST,
        "best_iteration": int(modelo.best_iteration),
        "target_transform": "log1p",
    }
    joblib.dump(blob_val, RUTA_MODELO_VAL)
    print(f"\nModelo validacion -> {RUTA_MODELO_VAL}")

    # Exportar metricas
    metricas = {
        **m_global, **m_diurno, **m_nocturno,
        "best_iteration": int(modelo.best_iteration),
        "secs_entrenamiento": round(secs, 1),
        "n_features": len(FEATURES),
        "n_train_total": len(df_train_full),
        "n_test": len(df_test),
        "anio_train": ANIO_TRAIN,
        "anio_test": ANIO_TEST,
        "params": {k: (v if isinstance(v, (int, float, str, bool, type(None))) else str(v))
                   for k, v in PARAMS.items()},
        "top_features": importancia.head(10).to_dict(),
    }
    DIR_DOCS.mkdir(exist_ok=True)
    with open(RUTA_METRICAS, "w", encoding="utf-8") as f:
        json.dump(metricas, f, indent=2, ensure_ascii=False)
    print(f"Metricas         -> {RUTA_METRICAS}")

    # Re-entrenamiento con 2023 + 2024 para produccion
    print(f"\n=== Re-entrenando para produccion (2023 + 2024) ===")
    X_full = df[FEATURES]
    y_full = np.log1p(df[TARGET].values)

    # Usar best_iteration + 10% como n_estimators (con datos extra ayuda).
    params_prod = dict(PARAMS)
    params_prod["n_estimators"] = max(50, int(modelo.best_iteration * 1.1))

    t0 = time.time()
    modelo_prod = xgb.XGBRegressor(**params_prod)
    modelo_prod.fit(X_full, y_full, verbose=False)
    print(f"  Entrenado en {time.time() - t0:.1f}s")

    blob_prod = {
        "model": modelo_prod,
        "features": FEATURES,
        "features_categoricas": FEATURES_CAT,
        "features_numericas": FEATURES_NUM,
        "day_type_categories": DAY_TYPES,
        "version": "v1_produccion",
        "trained_on_years": [ANIO_TRAIN, ANIO_TEST],
        "n_estimators_used": params_prod["n_estimators"],
        "target_transform": "log1p",
    }
    joblib.dump(blob_prod, RUTA_MODELO_PROD)
    print(f"Modelo produccion -> {RUTA_MODELO_PROD}")

    print(f"\nListo.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
