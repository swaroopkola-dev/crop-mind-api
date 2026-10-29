from datetime import datetime, timezone
from typing import Any

from bson import ObjectId
from pymongo.collection import Collection
from pymongo.database import Database


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def oid(value: str) -> ObjectId:
    if not ObjectId.is_valid(value):
        raise ValueError("Invalid identifier")
    return ObjectId(value)


def safe_doc(doc: dict[str, Any] | None) -> dict[str, Any] | None:
    if doc is None:
        return None
    result = dict(doc)
    result["id"] = str(result.pop("_id"))
    for key, value in list(result.items()):
        if isinstance(value, ObjectId):
            result[key] = str(value)
    return result


def write_audit(db: Database, *, action: str, actor_id: ObjectId | None = None, actor_email: str | None = None, actor_role: str = "system", entity_type: str | None = None, entity_id: str | None = None, metadata: dict[str, Any] | None = None, source: str = "live", is_synthetic: bool = False) -> None:
    # Never pass secrets or raw credential material in metadata.
    db.activity_logs.insert_one({"timestamp": utcnow(), "actor_id": actor_id, "actor_email": actor_email, "actor_role": actor_role, "action": action, "entity_type": entity_type, "entity_id": entity_id, "metadata": metadata or {}, "source": source, "is_synthetic": is_synthetic})


def paginate(collection: Collection, query: dict[str, Any], *, limit: int = 20, skip: int = 0, sort: list[tuple[str, int]] | None = None) -> tuple[list[dict[str, Any]], int]:
    limit = max(1, min(limit, 100))
    skip = max(0, skip)
    cursor = collection.find(query).sort(sort or [("created_at", -1)]).skip(skip).limit(limit)
    items = [safe_doc(item) for item in cursor]
    return [item for item in items if item is not None], collection.count_documents(query)
