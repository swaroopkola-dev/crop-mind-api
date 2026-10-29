from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pymongo.database import Database

from app.db.client import get_database
from app.db.repositories import oid, paginate, safe_doc, write_audit
from app.dependencies.auth import current_user, optional_user
from app.schemas.recommendation import ComparisonInput, RecommendationInput
from app.services.gemini import generate_explanation
from app.services.scoring import rank_crops

router = APIRouter(tags=["recommendations"])


def input_dict(payload: RecommendationInput) -> dict:
    return payload.model_dump(mode="json")


@router.post("/recommendations")
async def recommend(payload: RecommendationInput, db: Database = Depends(get_database), user: dict | None = Depends(optional_user)) -> dict:
    crops = list(db.crops.find({"active": True}))
    if not crops:
        raise HTTPException(status_code=503, detail="No active crop profiles are configured.")
    inputs = input_dict(payload)
    try:
        results = rank_crops(inputs, crops)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    if not results:
        raise HTTPException(status_code=422, detail="Not enough known information to compute a recommendation.")
    missing = sorted({name for result in results for name in result["confidence"]["missing_inputs"] if name in {"nitrogen", "phosphorus", "potassium"}})
    explanation, explanation_source = await generate_explanation(results, missing)
    now = datetime.now(timezone.utc)
    record = {"owner_id": user["_id"] if user else None, "inputs": inputs, "ranked_results": results, "missing_inputs": missing, "explanation": explanation, "explanation_source": explanation_source, "source": "live", "is_synthetic": False, "created_at": now}
    insert = db.recommendations.insert_one(record)
    record["_id"] = insert.inserted_id
    # Audit writes are part of the successful request contract. If this fails, surface an error instead of silently claiming audited success.
    write_audit(db, action="recommendation.created", actor_id=user["_id"] if user else None, actor_email=user.get("email") if user else None, actor_role=user.get("role", "anonymous") if user else "anonymous", entity_type="recommendation", entity_id=str(insert.inserted_id), metadata={"result_count": len(results), "explanation_source": explanation_source})
    return {"id": str(insert.inserted_id), "created_at": now.isoformat(), "inputs": inputs, "results": results, "missing_inputs": missing, "explanation": explanation, "explanation_source": explanation_source, "disclaimer": "Advisory only. Profiles are approximate and do not guarantee crop success or yield."}


@router.get("/recommendations")
def history(limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0), db: Database = Depends(get_database), user: dict = Depends(current_user)) -> dict:
    rows, total = paginate(db.recommendations, {"owner_id": user["_id"]}, limit=limit, skip=offset, sort=[("created_at", -1)])
    # History is explicitly for saved records owned by this user.
    return {"items": rows, "total": total, "limit": limit, "offset": offset}


@router.get("/recommendations/{recommendation_id}")
def get_recommendation(recommendation_id: str, db: Database = Depends(get_database), user: dict = Depends(current_user)) -> dict:
    try:
        _id = oid(recommendation_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Recommendation not found.") from None
    query = {"_id": _id}
    if user.get("role") != "admin":
        query["owner_id"] = user["_id"]
    record = safe_doc(db.recommendations.find_one(query))
    if not record:
        raise HTTPException(status_code=404, detail="Recommendation not found.")
    return record


@router.delete("/recommendations/{recommendation_id}", status_code=204)
def delete_recommendation(recommendation_id: str, response: Response, db: Database = Depends(get_database), user: dict = Depends(current_user)) -> Response:
    try:
        _id = oid(recommendation_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Recommendation not found.") from None
    query = {"_id": _id}
    if user.get("role") != "admin":
        query["owner_id"] = user["_id"]
    record = db.recommendations.find_one(query)
    if not record:
        raise HTTPException(status_code=404, detail="Recommendation not found.")
    db.recommendations.delete_one({"_id": _id})
    write_audit(db, action="recommendation.deleted", actor_id=user["_id"], actor_email=user["email"], actor_role=user["role"], entity_type="recommendation", entity_id=recommendation_id)
    response.status_code = 204
    return response


@router.post("/recommendations/{recommendation_id}/save")
def save_recommendation(recommendation_id: str, db: Database = Depends(get_database), user: dict = Depends(current_user)) -> dict:
    try:
        _id = oid(recommendation_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Recommendation not found.") from None
    record = db.recommendations.find_one({"_id": _id, "owner_id": None, "is_synthetic": False})
    if not record:
        raise HTTPException(status_code=404, detail="Anonymous recommendation not found or already saved.")
    db.recommendations.update_one({"_id": _id, "owner_id": None}, {"$set": {"owner_id": user["_id"], "saved_at": datetime.now(timezone.utc)}})
    write_audit(db, action="recommendation.saved", actor_id=user["_id"], actor_email=user["email"], actor_role=user["role"], entity_type="recommendation", entity_id=recommendation_id)
    return {"id": recommendation_id, "saved": True}


@router.post("/compare")
def compare(payload: ComparisonInput, db: Database = Depends(get_database), user: dict | None = Depends(optional_user)) -> dict:
    ids = []
    try:
        ids = [oid(value) for value in payload.crop_ids]
    except ValueError:
        raise HTTPException(status_code=422, detail="One or more crop IDs are invalid.") from None
    crops = list(db.crops.find({"_id": {"$in": ids}, "active": True}))
    if len(crops) != len(ids):
        raise HTTPException(status_code=404, detail="One or more selected crop profiles were not found.")
    ranked = rank_crops(input_dict(payload.inputs), crops)
    comparison_id = db.comparisons.insert_one({"owner_id": user["_id"] if user else None, "crop_ids": ids, "inputs": input_dict(payload.inputs), "results": ranked, "created_at": datetime.now(timezone.utc), "source": "live", "is_synthetic": False}).inserted_id
    write_audit(db, action="comparison.executed", actor_id=user["_id"] if user else None, actor_email=user.get("email") if user else None, actor_role=user.get("role", "anonymous") if user else "anonymous", entity_type="comparison", entity_id=str(comparison_id), metadata={"crop_count": len(ids)})
    return {"id": str(comparison_id), "results": ranked, "disclaimer": "Comparison is advisory and uses approximate profiles."}
