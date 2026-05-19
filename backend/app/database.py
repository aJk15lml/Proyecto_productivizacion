"""
Conexion a MongoDB (Motor async) para guardar estaciones e historial.
"""

import os
from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("MONGO_DB_NAME", "london_crowding")

client = None
db = None


async def get_db():
    global client, db
    if client is None:
        client = AsyncIOMotorClient(MONGO_URI, serverSelectionTimeoutMS=3000)
    if db is None:
        db = client[DB_NAME]
        try:
            await db.stations.create_index("NLC", unique=True)
            await db.predictions.create_index("created_at", expireAfterSeconds=2592000)
        except Exception:
            pass
    return db


async def close_db():
    global client
    if client:
        client.close()
