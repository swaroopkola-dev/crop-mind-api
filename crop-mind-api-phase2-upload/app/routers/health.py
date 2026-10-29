from fastapi import APIRouter, Depends, Request, Response
from pymongo.database import Database
from pymongo.errors import PyMongoError

from app.db.client import get_database

router = APIRouter(tags=["health"])


@router.get("/health")
def health(request: Request, response: Response, db: Database = Depends(get_database)) -> dict:
    try:
        db.command("ping")
        response.status_code = 200
        return {"status": "ok", "database": "ok", "request_id": getattr(request.state, "request_id", None)}
    except PyMongoError:
        response.status_code = 503
        return {"status": "degraded", "database": "unavailable", "request_id": getattr(request.state, "request_id", None)}
