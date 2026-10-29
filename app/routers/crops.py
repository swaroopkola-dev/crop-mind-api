from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from app.db.client import get_database
from app.db.repositories import oid, safe_doc, write_audit
from app.dependencies.auth import admin_user
from app.schemas.recommendation import CropCreate

router = APIRouter(prefix="/crops", tags=["crops"])


@router.get("")
def list_crops(q: str | None = None, limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0), db: Database = Depends(get_database)) -> dict:
    query = {"active": True}
    if q:
        query["name"] = {"$regex": "^" + __import__("re").escape(q[:80]), "$options": "i"}
    cursor = db.crops.find(query, {"ranges": 0}).sort("name", 1).skip(offset).limit(limit)
    items = [safe_doc(item) for item in cursor]
    return {"items": items, "total": db.crops.count_documents(query), "limit": limit, "offset": offset}


@router.get("/{crop_id}")
def get_crop(crop_id: str, db: Database = Depends(get_database)) -> dict:
    try:
        _id = oid(crop_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Crop not found.") from None
    crop = db.crops.find_one({"_id": _id, "active": True})
    if not crop:
        raise HTTPException(status_code=404, detail="Crop not found.")
    return safe_doc(crop)


@router.post("", status_code=201)
def create_crop(payload: CropCreate, db: Database = Depends(get_database), admin: dict = Depends(admin_user)) -> dict:
    now = datetime.now(timezone.utc)
    doc = payload.model_dump(mode="json")
    doc["name_key"] = doc["name"].casefold()
    doc["created_at"] = now
    doc["updated_at"] = now
    doc["source"] = "admin"
    doc["is_synthetic"] = False
    try:
        inserted = db.crops.insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail="Crop name already exists.") from None
    write_audit(db, action="crop.created", actor_id=admin["_id"], actor_email=admin["email"], actor_role="admin", entity_type="crop", entity_id=str(inserted.inserted_id))
    doc["_id"] = inserted.inserted_id
    return safe_doc(doc)


@router.put("/{crop_id}")
def update_crop(crop_id: str, payload: CropCreate, db: Database = Depends(get_database), admin: dict = Depends(admin_user)) -> dict:
    try:
        _id = oid(crop_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Crop not found.") from None
    before = db.crops.find_one({"_id": _id})
    if not before:
        raise HTTPException(status_code=404, detail="Crop not found.")
    update = payload.model_dump(mode="json")
    update["name_key"] = update["name"].casefold()
    update["updated_at"] = datetime.now(timezone.utc)
    update["created_at"] = before.get("created_at", update["updated_at"])
    update["source"] = "admin"
    update["is_synthetic"] = False
    try:
        db.crops.replace_one({"_id": _id}, update)
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail="Crop name already exists.") from None
    write_audit(db, action="crop.updated", actor_id=admin["_id"], actor_email=admin["email"], actor_role="admin", entity_type="crop", entity_id=crop_id)
    update["_id"] = _id
    return safe_doc(update)


@router.delete("/{crop_id}", status_code=204)
def deactivate_crop(crop_id: str, db: Database = Depends(get_database), admin: dict = Depends(admin_user)) -> None:
    try:
        _id = oid(crop_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Crop not found.") from None
    result = db.crops.update_one({"_id": _id, "active": True}, {"$set": {"active": False, "updated_at": datetime.now(timezone.utc)}})
    if not result.modified_count:
        raise HTTPException(status_code=404, detail="Active crop not found.")
    write_audit(db, action="crop.deactivated", actor_id=admin["_id"], actor_email=admin["email"], actor_role="admin", entity_type="crop", entity_id=crop_id)
