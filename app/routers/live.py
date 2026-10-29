from datetime import datetime, timezone
import hashlib
import json

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from pymongo.database import Database

from app.db.client import get_database
from app.dependencies.auth import admin_user

router = APIRouter(prefix="/live", tags=["live"])


def _summary(db: Database, detailed: bool = False) -> dict:
    base = {
        "active_crops": db.crops.count_documents({"active": True}),
        "recommendations_total": db.recommendations.count_documents({"is_synthetic": {"$ne": True}}),
        "recommendations_24h": db.recommendations.count_documents({"created_at": {"$gte": datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)}, "is_synthetic": {"$ne": True}}),
    }
    if detailed:
        base.update({"users_total": db.users.count_documents({"is_synthetic": {"$ne": True}}), "users_active": db.users.count_documents({"status": "active", "is_synthetic": {"$ne": True}}), "gemini_explanations": db.recommendations.count_documents({"explanation_source": "gemini", "is_synthetic": {"$ne": True}}), "fallback_explanations": db.recommendations.count_documents({"explanation_source": "fallback", "is_synthetic": {"$ne": True}}), "synthetic_recommendations": db.recommendations.count_documents({"is_synthetic": True})})
    return base


@router.get("/summary", response_model=None)
def summary(response: Response, db: Database = Depends(get_database), if_none_match: str | None = Header(default=None)):
    payload = _summary(db)
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    etag = '"' + hashlib.sha256(serialized.encode()).hexdigest()[:24] + '"'
    response.headers["ETag"] = etag
    response.headers["Cache-Control"] = "private, max-age=0, must-revalidate"
    response.headers["Vary"] = "Origin"
    if if_none_match and (if_none_match.strip() == "*" or etag in {token.strip() for token in if_none_match.split(",")}):
        response.status_code = 304
        return response
    return payload


@router.get("/activity")
def activity(since: str | None = None, limit: int = Query(30, ge=1, le=100), db: Database = Depends(get_database), admin: dict = Depends(admin_user)) -> dict:
    query = {"is_synthetic": {"$ne": True}}
    if since:
        try:
            cursor = datetime.fromisoformat(since.replace("Z", "+00:00"))
            if cursor.tzinfo is None:
                cursor = cursor.replace(tzinfo=timezone.utc)
            query["timestamp"] = {"$gt": cursor}
        except ValueError:
            raise HTTPException(status_code=422, detail="since must be an ISO 8601 timestamp.") from None
    items = list(db.activity_logs.find(query).sort("timestamp", -1).limit(limit))
    for item in items:
        item["id"] = str(item.pop("_id"))
        item["actor_id"] = str(item["actor_id"]) if item.get("actor_id") else None
        item["timestamp"] = item["timestamp"].isoformat()
    return {"items": items, "limit": limit, "next_since": items[0]["timestamp"] if items else since}
