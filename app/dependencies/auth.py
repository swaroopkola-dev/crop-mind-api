from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWTError
from pymongo.database import Database

from app.core.security import decode_access_token
from app.db.client import get_database
from app.db.repositories import oid

bearer = HTTPBearer(auto_error=False)


def current_user(request: Request, credentials: HTTPAuthorizationCredentials | None = Depends(bearer), db: Database = Depends(get_database)) -> dict:
    token = credentials.credentials if credentials else None
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required.")
    try:
        payload = decode_access_token(token)
        if payload.get("typ") != "access":
            raise HTTPException(status_code=401, detail="Invalid access token.")
        user_id = payload.get("sub")
        user = db.users.find_one({"_id": oid(user_id), "status": "active"})
    except (PyJWTError, ValueError, TypeError):
        raise HTTPException(status_code=401, detail="Invalid or expired access token.") from None
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or inactive account.")
    request.state.user = user
    return user


def optional_user(request: Request, credentials: HTTPAuthorizationCredentials | None = Depends(bearer), db: Database = Depends(get_database)) -> dict | None:
    if credentials is None:
        return None
    return current_user(request, credentials, db)


def admin_user(user: dict = Depends(current_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Administrator access required.")
    return user
