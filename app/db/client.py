from functools import lru_cache

from pymongo import MongoClient
from pymongo.database import Database

from app.core.config import get_settings


@lru_cache
def get_client() -> MongoClient:
    settings = get_settings()
    return MongoClient(
        settings.mongodb_uri.get_secret_value(),
        serverSelectionTimeoutMS=3000,
        connectTimeoutMS=3000,
        maxPoolSize=20,
        appname="CropMindAPI",
    )


def get_database() -> Database:
    return get_client()[get_settings().db_name]


def close_client() -> None:
    get_client().close()
    get_client.cache_clear()
