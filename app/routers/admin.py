from datetime import datetime, timedelta, timezone
import csv
import io
import random
import secrets

from bson import ObjectId
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field
from pymongo.database import Database

from app.core.config import get_settings
from app.core.security import hash_password, validate_password_policy
from app.db.client import get_database
from app.db.indexes import ensure_indexes
from app.db.repositories import oid, paginate, safe_doc, utcnow, write_audit
from app.dependencies.auth import admin_user
from app.routers.live import _summary
from app.services.scoring import rank_crops

router = APIRouter(prefix="/admin", tags=["admin"])


class UserPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: str | None = None
    status: str | None = None

    def valid(self):
        if self.role is not None and self.role not in {"user", "admin"}:
            raise ValueError("role must be user or admin")
        if self.status is not None and self.status not in {"active", "disabled"}:
            raise ValueError("status must be active or disabled")


class SeedResult(BaseModel):
    crops_upserted: int
    admin_created: bool
    indexes: dict[str, list[str]]


class SettingsPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    registration_enabled: bool | None = None
    maintenance_banner: str | None = Field(default=None, max_length=200)
    fallback_override: bool | None = None
    poll_interval_ms: int | None = Field(default=None, ge=1000, le=60000)
    simulator_enabled: bool | None = None


@router.post("/seed", response_model=SeedResult, tags=["admin-seed"])
def seed_backend(
    x_seed_token: str | None = Header(default=None, alias="X-Seed-Token"),
    db: Database = Depends(get_database),
) -> dict:
    cfg = get_settings()
    expected = cfg.seed_token.get_secret_value() if cfg.seed_token else ""
    if len(expected) < 32 or not x_seed_token or not secrets.compare_digest(x_seed_token, expected):
        raise HTTPException(status_code=403, detail="Seed authorization failed.")
    email = (cfg.admin_seed_email or "").strip().lower()
    password = cfg.admin_seed_password.get_secret_value() if cfg.admin_seed_password else ""
    if not email or not password:
        raise HTTPException(
            status_code=503,
            detail="ADMIN_SEED_EMAIL and ADMIN_SEED_PASSWORD must be configured.",
        )
    try:
        validate_password_policy(password)
    except ValueError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Configured admin password does not meet policy: {exc}",
        ) from None
    from scripts.seed import CROPS

    index_result = ensure_indexes(db)
    now = utcnow()
    for source in CROPS:
        doc = dict(source)
        doc["updated_at"] = now
        db.crops.update_one({"name_key": doc["name_key"]}, {"$setOnInsert": doc}, upsert=True)
    admin_created = False
    existing = db.users.find_one({"email": email})
    if existing is None:
        db.users.insert_one(
            {
                "email": email,
                "display_name": "CropMind Admin",
                "password_hash": hash_password(password),
                "role": "admin",
                "status": "active",
                "created_at": now,
                "updated_at": now,
                "source": "seed",
                "is_synthetic": False,
            }
        )
        admin_created = True
    elif existing.get("role") != "admin":
        raise HTTPException(
            status_code=409,
            detail="ADMIN_SEED_EMAIL already belongs to a non-admin account; no role was changed.",
        )
    write_audit(
        db,
        action="admin.seed.completed",
        actor_role="system",
        entity_type="seed",
        metadata={"crop_count": len(CROPS), "admin_created": admin_created},
        source="seed",
        is_synthetic=False,
    )
    return {"crops_upserted": len(CROPS), "admin_created": admin_created, "indexes": index_result}


@router.get("/overview")
def overview(db: Database = Depends(get_database), admin: dict = Depends(admin_user)) -> dict:
    summary = _summary(db, detailed=True)
    top_pipeline = [
        {"$match": {"is_synthetic": {"$ne": True}}},
        {"$unwind": "$ranked_results"},
        {"$group": {"_id": "$ranked_results.crop_name", "count": {"$sum": 1}}},
        {"$sort": {"count": -1, "_id": 1}},
        {"$limit": 5},
    ]
    summary["top_crops"] = list(db.recommendations.aggregate(top_pipeline))
    summary["recent_activity"] = [
        {
            "action": item["action"],
            "timestamp": item["timestamp"].isoformat(),
            "actor_role": item.get("actor_role", "system"),
        }
        for item in db.activity_logs.find({"is_synthetic": {"$ne": True}})
        .sort("timestamp", -1)
        .limit(10)
    ]
    return summary


@router.get("/users")
def users(q: str | None = None, limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0), db: Database = Depends(get_database), admin: dict = Depends(admin_user)) -> dict:
    query: dict = {"is_synthetic": {"$ne": True}}
    if q:
        import re
        query["email"] = {"$regex": re.escape(q[:100]), "$options": "i"}
    cursor = db.users.find(query, {"password_hash": 0}).sort("created_at", -1).skip(offset).limit(limit)
    items = [safe_doc(item) for item in cursor]
    return {"items": items, "total": db.users.count_documents(query), "limit": limit, "offset": offset}


@router.get("/users/{user_id}")
def user_detail(user_id: str, db: Database = Depends(get_database), admin: dict = Depends(admin_user)) -> dict:
    try:
        record = db.users.find_one({"_id": oid(user_id)}, {"password_hash": 0})
    except ValueError:
        record = None
    if not record:
        raise HTTPException(status_code=404, detail="User not found.")
    record["recommendations_count"] = db.recommendations.count_documents({"owner_id": record["_id"]})
    return safe_doc(record)


@router.patch("/users/{user_id}")
def patch_user(user_id: str, payload: UserPatch, db: Database = Depends(get_database), admin: dict = Depends(admin_user)) -> dict:
    try:
        target_id = oid(user_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="User not found.") from None
    try:
        payload.valid()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    changes = payload.model_dump(exclude_unset=True, exclude_none=True)
    if not changes:
        raise HTTPException(status_code=400, detail="At least one field must be updated.")
    target = db.users.find_one({"_id": target_id})
    if not target:
        raise HTTPException(status_code=404, detail="User not found.")
    if target_id == admin["_id"] and (changes.get("role") == "user" or changes.get("status") == "disabled"):
        raise HTTPException(status_code=409, detail="You cannot demote or disable your own administrator account.")
    if target.get("role") == "admin" and (changes.get("role") == "user" or changes.get("status") == "disabled"):
        active_admins = db.users.count_documents({"role": "admin", "status": "active"})
        if active_admins <= 1:
            raise HTTPException(status_code=409, detail="The last active administrator cannot be demoted or disabled.")
    changes["updated_at"] = datetime.now(timezone.utc)
    db.users.update_one({"_id": target_id}, {"$set": changes})
    if changes.get("status") == "disabled":
        db.refresh_tokens.update_many(
            {"user_id": target_id, "revoked_at": None},
            {"$set": {"revoked_at": datetime.now(timezone.utc)}},
        )
    write_audit(
        db,
        action="admin.user.updated",
        actor_id=admin["_id"],
        actor_email=admin["email"],
        actor_role="admin",
        entity_type="user",
        entity_id=user_id,
        metadata={"changed_fields": sorted(changes.keys())},
    )
    return {"user": safe_doc(db.users.find_one({"_id": target_id}, {"password_hash": 0}))}


@router.post("/users/{user_id}/revoke-sessions")
def revoke_sessions(user_id: str, db: Database = Depends(get_database), admin: dict = Depends(admin_user)) -> dict:
    try:
        target_id = oid(user_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="User not found.") from None
    if not db.users.find_one({"_id": target_id}):
        raise HTTPException(status_code=404, detail="User not found.")
    now = datetime.now(timezone.utc)
    result = db.refresh_tokens.update_many(
        {"user_id": target_id, "revoked_at": None}, {"$set": {"revoked_at": now}}
    )
    write_audit(
        db,
        action="admin.user.sessions_revoked",
        actor_id=admin["_id"],
        actor_email=admin["email"],
        actor_role="admin",
        entity_type="user",
        entity_id=user_id,
        metadata={"revoked_count": result.modified_count},
    )
    return {"revoked_sessions": result.modified_count}


@router.get("/recommendations")
def recommendations(q: str | None = None, synthetic: bool | None = None, limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0), db: Database = Depends(get_database), admin: dict = Depends(admin_user)) -> dict:
    query: dict = {}
    if synthetic is not None:
        query["is_synthetic"] = synthetic
    if q:
        import re
        query["$or"] = [
            {"inputs.season": {"$regex": re.escape(q[:40]), "$options": "i"}},
            {"ranked_results.crop_name": {"$regex": re.escape(q[:80]), "$options": "i"}},
        ]
    return _recommendation_page(db, query, limit, offset)


def _recommendation_page(db: Database, query: dict, limit: int, offset: int) -> dict:
    items = [
        safe_doc(item)
        for item in db.recommendations.find(query).sort("created_at", -1).skip(offset).limit(limit)
    ]
    return {"items": items, "total": db.recommendations.count_documents(query), "limit": limit, "offset": offset}


@router.get("/recommendations/{recommendation_id}")
def recommendation_detail(recommendation_id: str, db: Database = Depends(get_database), admin: dict = Depends(admin_user)) -> dict:
    try:
        item = safe_doc(db.recommendations.find_one({"_id": oid(recommendation_id)}))
    except ValueError:
        item = None
    if not item:
        raise HTTPException(status_code=404, detail="Recommendation not found.")
    return item


@router.delete("/recommendations/{recommendation_id}", status_code=204)
def delete_recommendation(recommendation_id: str, db: Database = Depends(get_database), admin: dict = Depends(admin_user)) -> None:
    try:
        _id = oid(recommendation_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Recommendation not found.") from None
    result = db.recommendations.delete_one({"_id": _id})
    if not result.deleted_count:
        raise HTTPException(status_code=404, detail="Recommendation not found.")
    write_audit(
        db,
        action="admin.recommendation.deleted",
        actor_id=admin["_id"],
        actor_email=admin["email"],
        actor_role="admin",
        entity_type="recommendation",
        entity_id=recommendation_id,
    )


@router.get("/activity")
def admin_activity(action: str | None = None, limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0), db: Database = Depends(get_database), admin: dict = Depends(admin_user)) -> dict:
    query = {"is_synthetic": {"$ne": True}}
    if action:
        query["action"] = action[:100]
    items, total = paginate(db.activity_logs, query, limit=limit, skip=offset, sort=[("timestamp", -1)])
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/system")
def system_status(db: Database = Depends(get_database), admin: dict = Depends(admin_user)) -> dict:
    settings = list(db.settings.find({}, {"_id": 0, "key": 1, "value": 1, "updated_at": 1}))
    cfg = get_settings()
    key = cfg.gemini_api_key.get_secret_value().strip() if cfg.gemini_api_key else ""
    return {"database": "connected", "gemini_configured": bool(key), "simulator_enabled": bool(cfg.simulator_enabled), "settings": settings}


@router.get("/settings")
def get_settings_route(db: Database = Depends(get_database), admin: dict = Depends(admin_user)) -> dict:
    return {"items": list(db.settings.find({}, {"_id": 0}))}


@router.put("/settings")
def update_settings(payload: SettingsPatch, db: Database = Depends(get_database), admin: dict = Depends(admin_user)) -> dict:
    changes = payload.model_dump(exclude_unset=True, exclude_none=True)
    if not changes:
        raise HTTPException(status_code=400, detail="No settings provided.")
    now = datetime.now(timezone.utc)
    for key, value in changes.items():
        db.settings.update_one(
            {"key": key},
            {"$set": {"key": key, "value": value, "updated_at": now, "updated_by": admin["_id"]}},
            upsert=True,
        )
    write_audit(
        db,
        action="admin.settings.updated",
        actor_id=admin["_id"],
        actor_email=admin["email"],
        actor_role="admin",
        entity_type="settings",
        metadata={"keys": sorted(changes.keys())},
    )
    return {"updated": sorted(changes.keys())}


@router.post("/simulator/tick")
def simulator_tick(db: Database = Depends(get_database), admin: dict = Depends(admin_user)) -> dict:
    cfg = db.settings.find_one({"key": "simulator_enabled"})
    enabled = bool(cfg.get("value")) if cfg else False
    if not enabled:
        raise HTTPException(status_code=409, detail="Simulator is disabled. Enable it first.")
    crops = list(db.crops.find({"active": True}))
    if len(crops) < 2:
        raise HTTPException(status_code=409, detail="Seed at least two active crop profiles before running the simulator.")
    rng = random.SystemRandom()
    now = utcnow()
    soil_types = ["sandy", "loamy", "clay", "silt", "black", "red", "alluvial"]
    seasons = ["Kharif", "Rabi", "Zaid"]
    generated = 0
    for _ in range(3):
        inputs = {
            "soil_type": rng.choice(soil_types),
            "season": rng.choice(seasons),
            "ph": round(rng.uniform(4.5, 8.5), 1),
            "nitrogen": rng.randint(10, 180),
            "phosphorus": rng.randint(5, 90),
            "potassium": rng.randint(10, 120),
            "rainfall_mm": rng.randint(200, 1800),
            "temperature_c": rng.randint(12, 36),
            "humidity_pct": rng.randint(25, 95),
        }
        results = rank_crops(inputs, crops)
        if not results:
            continue
        db.recommendations.insert_one(
            {
                "owner_id": None,
                "inputs": inputs,
                "ranked_results": results,
                "missing_inputs": [],
                "explanation": "Synthetic simulator record for dashboard and pipeline testing; not agronomic advice.",
                "explanation_source": "fallback",
                "source": "simulator",
                "is_synthetic": True,
                "created_at": now - timedelta(seconds=rng.randint(0, 3600)),
            }
        )
        db.activity_logs.insert_one(
            {
                "timestamp": now,
                "actor_id": admin["_id"],
                "actor_email": None,
                "actor_role": "simulator",
                "action": "simulator.recommendation.generated",
                "entity_type": "recommendation",
                "metadata": {"seed": False},
                "source": "simulator",
                "is_synthetic": True,
            }
        )
        generated += 1
    write_audit(db, action="simulator.tick", actor_id=admin["_id"], actor_email=admin["email"], actor_role="admin", entity_type="simulator", metadata={"generated": generated})
    return {"generated": generated, "source": "simulator", "is_synthetic": True}


@router.post("/simulator/toggle")
def simulator_toggle(enabled: bool, db: Database = Depends(get_database), admin: dict = Depends(admin_user)) -> dict:
    now = datetime.now(timezone.utc)
    db.settings.update_one({"key": "simulator_enabled"}, {"$set": {"key": "simulator_enabled", "value": enabled, "updated_at": now, "updated_by": admin["_id"]}}, upsert=True)
    write_audit(db, action="simulator.toggled", actor_id=admin["_id"], actor_email=admin["email"], actor_role="admin", entity_type="simulator", metadata={"enabled": enabled})
    return {"enabled": enabled}


@router.post("/synthetic/purge")
def purge_synthetic(db: Database = Depends(get_database), admin: dict = Depends(admin_user)) -> dict:
    counts = {}
    for name in ("recommendations", "comparisons", "users", "activity_logs"):
        counts[name] = db[name].delete_many({"is_synthetic": True}).deleted_count
    write_audit(db, action="synthetic.purge", actor_id=admin["_id"], actor_email=admin["email"], actor_role="admin", entity_type="synthetic_data", metadata={"deleted_counts": counts})
    return {"deleted_counts": counts}


def _csv_response(rows: list[dict], columns: list[str], filename: str) -> Response:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        flattened = {key: row.get(key) for key in columns}
        writer.writerow(flattened)
    return Response(content=buffer.getvalue(), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.get("/export/recommendations.csv")
def export_recommendations(limit: int = Query(100, ge=1, le=5000), db: Database = Depends(get_database), admin: dict = Depends(admin_user)) -> Response:
    rows = list(db.recommendations.find({"is_synthetic": {"$ne": True}}).sort("created_at", -1).limit(limit))
    export = [{"id": str(row["_id"]), "created_at": row.get("created_at"), "owner_id": str(row["owner_id"]) if row.get("owner_id") else "", "season": (row.get("inputs") or {}).get("season"), "soil_type": (row.get("inputs") or {}).get("soil_type"), "top_crop": ((row.get("ranked_results") or [{}])[0]).get("crop_name"), "top_score": ((row.get("ranked_results") or [{}])[0]).get("score"), "explanation_source": row.get("explanation_source")} for row in rows]
    write_audit(db, action="admin.export.recommendations", actor_id=admin["_id"], actor_email=admin["email"], actor_role="admin", entity_type="export", metadata={"count": len(export)})
    return _csv_response(export, ["id", "created_at", "owner_id", "season", "soil_type", "top_crop", "top_score", "explanation_source"], "cropmind-recommendations.csv")


@router.get("/export/activity.csv")
def export_activity(limit: int = Query(100, ge=1, le=5000), db: Database = Depends(get_database), admin: dict = Depends(admin_user)) -> Response:
    rows = list(db.activity_logs.find({"is_synthetic": {"$ne": True}}).sort("timestamp", -1).limit(limit))
    export = [{"timestamp": r.get("timestamp"), "actor_role": r.get("actor_role"), "actor_email": r.get("actor_email"), "action": r.get("action"), "entity_type": r.get("entity_type"), "entity_id": r.get("entity_id")} for r in rows]
    write_audit(db, action="admin.export.activity", actor_id=admin["_id"], actor_email=admin["email"], actor_role="admin", entity_type="export", metadata={"count": len(export)})
    return _csv_response(export, ["timestamp", "actor_role", "actor_email", "action", "entity_type", "entity_id"], "cropmind-activity.csv")


@router.get("/export/users.csv")
def export_users(limit: int = Query(100, ge=1, le=5000), db: Database = Depends(get_database), admin: dict = Depends(admin_user)) -> Response:
    rows = list(db.users.find({"is_synthetic": {"$ne": True}}, {"password_hash": 0}).sort("created_at", -1).limit(limit))
    export = [{"id": str(r["_id"]), "email": r.get("email"), "display_name": r.get("display_name"), "role": r.get("role"), "status": r.get("status"), "created_at": r.get("created_at")} for r in rows]
    write_audit(db, action="admin.export.users", actor_id=admin["_id"], actor_email=admin["email"], actor_role="admin", entity_type="export", metadata={"count": len(export)})
    return _csv_response(export, ["id", "email", "display_name", "role", "status", "created_at"], "cropmind-users.csv")
