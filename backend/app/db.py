from pymongo import MongoClient
from pymongo.database import Database

from .config import get_settings

_client: MongoClient | None = None


def get_db() -> Database:
    global _client
    settings = get_settings()
    if _client is None:
        _client = MongoClient(settings.mongo_uri, serverSelectionTimeoutMS=5000)
    return _client[settings.mongo_db_name]
