"""
Script para poblar MongoDB con los datos de estaciones del parquet.

Uso:
    python scripts/seed_mongodb.py

Requiere:
    - MONGO_URI en .env o variable de entorno
    - data/processed/numbat_long.parquet
"""

import os
import sys
from pathlib import Path

import pandas as pd

# Permitir importar database desde scripts/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.database import get_db

RAIZ = Path(__file__).resolve().parent.parent.parent
RUTA_PARQUET = RAIZ / "data" / "processed" / "numbat_long.parquet"


async def main():
    print(f"Cargando {RUTA_PARQUET}...")
    df = pd.read_parquet(RUTA_PARQUET)

    cols = [
        "NLC", "ASC", "station_name_numbat", "UniqueStationName",
        "fare_zone_str", "InnerFareZone", "OuterFareZone",
        "FullyGated", "Hub", "Active", "TfL",
        "Latitude", "Longitude", "num_lines", "num_modes",
    ]
    cols = [c for c in cols if c in df.columns]
    estaciones = df[cols].drop_duplicates(subset="NLC").copy()
    estaciones["NLC"] = estaciones["NLC"].astype(int)
    estaciones = estaciones.where(pd.notna(estaciones), None).to_dict(orient="records")

    print(f"Estaciones unicas: {len(estaciones)}")

    db = await get_db()
    result = await db.stations.delete_many({})
    print(f"Eliminados {result.deleted_count} documentos previos")

    result = await db.stations.insert_many(estaciones)
    print(f"Insertadas {len(result.inserted_ids)} estaciones en MongoDB")

    print("Listo.")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
