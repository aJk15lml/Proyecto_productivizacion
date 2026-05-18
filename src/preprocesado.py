"""
Preprocesado de NUMBAT a formato long con features.

Pipeline:
1. Carga cada archivo NUMBAT (5 día-tipo x 2 años = 10 archivos) -> wide.
2. Filtra estaciones todas-cero (Total == 0): paradas de Tramlink, etc.
3. Convierte wide -> long: 1 fila por (estacion x año x dia_tipo x franja_15min).
4. Carga metadata del PTSP Oasis (Stations + Stn-Line + Stn-Mode), deduplica.
5. Joinea metadata: num_lines, num_modes, lat/lon, fare_zone, hub, etc.
6. Calcula features temporales: hour, minute, is_peak, is_night.
7. Guarda en data/processed/numbat_long.parquet.

Uso:
    python src/preprocesado.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# Configuracion
# ---------------------------------------------------------------------------

RAIZ = Path(__file__).resolve().parent.parent
DATA_RAW = RAIZ / "data" / "raw"
DATA_PROCESSED = RAIZ / "data" / "processed"
SALIDA = DATA_PROCESSED / "numbat_long.parquet"

ANIOS_ENTRENO = [2023, 2024]
TIPOS_DIA = ["MON", "TWT", "FRI", "SAT", "SUN"]

# Sufijo del archivo (TfL cambio la capitalizacion a partir de 2023).
SUFIJO_POR_ANIO = {
    2017: "_Outputs.xlsx",
    2019: "_Outputs.xlsx",
    2023: "_outputs.xlsx",
    2024: "_outputs.xlsx",
}

HOJA = "Station_Entries"
FILA_CABECERA = 2
PATRON_HORA = re.compile(r"^\d{4}-\d{4}$")

ARCHIVO_DEFINICIONES = DATA_RAW / "2024" / "PTSP Oasis for NUMBAT definitions.xlsx"

# Lineas TfL para contar num_lines (excluimos los R* de National Rail).
LINEAS_TFL = [
    "BAK", "CEN", "DIS", "JUB", "HAM", "MET", "NOR", "PIC", "VIC", "WAC",
    "DLR", "EZL", "NLL", "ELL", "WEL", "GOB", "URL", "WAG", "TRM",
]
# Modos rail TfL (TRM = Tramlink no se mide en NUMBAT).
MODOS_RAIL_TFL = ["u", "d", "o", "e"]


# ---------------------------------------------------------------------------
# Carga y transformacion de NUMBAT
# ---------------------------------------------------------------------------

def cargar_un_numbat(anio: int, tipo: str) -> pd.DataFrame:
    nombre = f"NBT{str(anio)[2:]}{tipo}{SUFIJO_POR_ANIO[anio]}"
    ruta = DATA_RAW / str(anio) / nombre
    print(f"  - Leyendo {ruta.name}")
    return pd.read_excel(ruta, sheet_name=HOJA, header=FILA_CABECERA)


def wide_a_long(df_wide: pd.DataFrame, anio: int, tipo_dia: str) -> pd.DataFrame:
    cols_hora = [c for c in df_wide.columns if PATRON_HORA.match(str(c))]
    if len(cols_hora) != 96:
        raise ValueError(
            f"Esperaba 96 franjas de 15 min, encontre {len(cols_hora)} "
            f"en {anio}/{tipo_dia}"
        )

    # Filtrar estaciones todas-cero.
    n_antes = len(df_wide)
    df_wide = df_wide[df_wide["Total"] > 0].copy()
    print(f"    Filtradas {n_antes - len(df_wide)} estaciones todas-cero "
          f"({len(df_wide)} validas).")

    id_vars = ["NLC", "ASC", "Station", "Fare Zone"]
    df_long = df_wide.melt(
        id_vars=id_vars,
        value_vars=cols_hora,
        var_name="quarter_hour_slot",
        value_name="passengers",
    )
    df_long["year"] = anio
    df_long["day_type"] = tipo_dia
    return df_long


# ---------------------------------------------------------------------------
# Carga de metadata
# ---------------------------------------------------------------------------

def cargar_metadata() -> pd.DataFrame:
    print(f"  - Leyendo {ARCHIVO_DEFINICIONES.name}")

    stations = pd.read_excel(ARCHIVO_DEFINICIONES, sheet_name="Stations")
    stn_line = pd.read_excel(ARCHIVO_DEFINICIONES, sheet_name="Stn-Line")
    stn_mode = pd.read_excel(ARCHIVO_DEFINICIONES, sheet_name="Stn-Mode")

    # Defensa: TfL trae duplicados sueltos (ej.: West India Quay = NLC 866
    # aparece dos veces en Stn-Mode). Sin dedup, el merge multiplica filas.
    n_dup = (
        stations["MasterNLC"].duplicated().sum()
        + stn_line["MasterNLC"].duplicated().sum()
        + stn_mode["MasterNLC"].duplicated().sum()
    )
    if n_dup > 0:
        print(f"    Eliminando {n_dup} fila(s) duplicada(s) por NLC en las hojas de metadata.")

    stations = stations.drop_duplicates(subset="MasterNLC", keep="first").reset_index(drop=True)
    stn_line = stn_line.drop_duplicates(subset="MasterNLC", keep="first").reset_index(drop=True)
    stn_mode = stn_mode.drop_duplicates(subset="MasterNLC", keep="first").reset_index(drop=True)

    # Subconjunto util de Stations.
    cols_stations = [
        "MasterNLC", "UniqueStationName",
        "InnerFareZone", "OuterFareZone",
        "FullyGated", "Hub", "Active", "TfL",
        "Latitude", "Longitude",
    ]
    cols_stations = [c for c in cols_stations if c in stations.columns]
    meta = stations[cols_stations].rename(columns={"MasterNLC": "NLC"})

    # num_lines y num_modes.
    cols_lineas = [c for c in LINEAS_TFL if c in stn_line.columns]
    stn_line = stn_line.assign(num_lines=stn_line[cols_lineas].sum(axis=1))
    cols_modos = [c for c in MODOS_RAIL_TFL if c in stn_mode.columns]
    stn_mode = stn_mode.assign(num_modes=stn_mode[cols_modos].sum(axis=1))

    meta = meta.merge(
        stn_line[["MasterNLC", "num_lines"]].rename(columns={"MasterNLC": "NLC"}),
        on="NLC", how="left",
    )
    meta = meta.merge(
        stn_mode[["MasterNLC", "num_modes"]].rename(columns={"MasterNLC": "NLC"}),
        on="NLC", how="left",
    )
    return meta


# ---------------------------------------------------------------------------
# Features derivadas
# ---------------------------------------------------------------------------

def _parse_franja(s: str) -> tuple[int, int]:
    inicio = s.split("-")[0]
    return int(inicio[:2]), int(inicio[2:])


def anadir_features_temporales(df: pd.DataFrame) -> pd.DataFrame:
    horas_mins = df["quarter_hour_slot"].map(_parse_franja)
    df["hour"] = horas_mins.map(lambda x: x[0])
    df["minute"] = horas_mins.map(lambda x: x[1])

    laborable = df["day_type"].isin(["MON", "TWT", "FRI"])
    minutos_dia = df["hour"] * 60 + df["minute"]
    pico_man = (minutos_dia >= 7 * 60) & (minutos_dia < 9 * 60 + 30)
    pico_tar = (minutos_dia >= 17 * 60) & (minutos_dia < 19 * 60 + 30)
    df["is_peak"] = laborable & (pico_man | pico_tar)
    df["is_night"] = df["hour"] < 5
    return df


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    print(f"Raiz del proyecto: {RAIZ}")
    print(f"Salida:            {SALIDA}")
    print(f"Anios:             {ANIOS_ENTRENO}")
    print(f"Tipos de dia:      {TIPOS_DIA}")

    print(f"\n=== Cargando NUMBAT ({len(ANIOS_ENTRENO) * len(TIPOS_DIA)} archivos) ===")
    bloques = []
    for anio in ANIOS_ENTRENO:
        for tipo in TIPOS_DIA:
            df_wide = cargar_un_numbat(anio, tipo)
            df_long = wide_a_long(df_wide, anio, tipo)
            bloques.append(df_long)
    df = pd.concat(bloques, ignore_index=True)
    print(f"\nTotal de filas tras concat: {len(df):,}")
    print(f"Estaciones unicas:         {df['NLC'].nunique()}")

    print(f"\n=== Cargando metadata del archivo de definiciones ===")
    meta = cargar_metadata()
    print(f"Estaciones en metadata: {len(meta):,} (NLC unicos: {meta['NLC'].nunique()})")

    print(f"\n=== Joineando metadata por NLC ===")
    n_antes = len(df)
    df = df.merge(meta, on="NLC", how="left")
    print(f"Filas tras merge: {len(df):,} (delta {len(df)-n_antes:+,})")
    sin_meta = df["UniqueStationName"].isna().sum()
    print(f"Filas sin metadata (NLC no encontrado): {sin_meta:,}")

    print(f"\n=== Calculando features temporales ===")
    df = anadir_features_temporales(df)

    df = df.rename(columns={
        "Fare Zone": "fare_zone_str",
        "Station": "station_name_numbat",
    })

    # Tipos numericos.
    df["passengers"] = df["passengers"].astype(float)
    df["year"] = df["year"].astype("int16")
    df["NLC"] = df["NLC"].astype("int32")
    df["hour"] = df["hour"].astype("int8")
    df["minute"] = df["minute"].astype("int8")

    # Tipos string: parquet no acepta columnas object con tipos mezclados.
    # 'fare_zone_str' tiene valores int (1, 2, 3) y str ("2/3") -> forzar a str.
    # Defensivamente lo hacemos con el resto de columnas categoricas.
    for col in ["fare_zone_str", "ASC", "station_name_numbat",
                "day_type", "UniqueStationName", "Hub", "FullyGated"]:
        if col in df.columns:
            df[col] = df[col].astype(str)

    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    print(f"\n=== Guardando ===")
    df.to_parquet(SALIDA, index=False, compression="snappy")
    tam_mb = SALIDA.stat().st_size / 1_000_000

    print(f"\nGuardado en {SALIDA}")
    print(f"  Filas:    {len(df):,}")
    print(f"  Columnas: {len(df.columns)}")
    print(f"  Tamano:   {tam_mb:.1f} MB")
    print(f"\n  Columnas: {df.columns.tolist()}")
    print(f"\n  Muestra:")
    print(df.head(5).to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
