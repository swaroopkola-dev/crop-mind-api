from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from app.core.config import get_settings
from app.core.security import (
    create_access_token,
    hash_password,
    token_hash,
    validate_password_policy,
    verify_password,
)
from app.db.client import get_database
from app.db.repositories import write_audit
from app.dependencies.auth import current_user
from app.services.auth import (
    authenticate,
    issue_refresh_token,
    normalize_email,
    register_user,
    revoke_refresh_token,
    rotate_refresh_token,
)

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterBody(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    display_name: str | None = Field(default=None, max_length=80)

    @field_validator("password")
    @classmethod
    def password_rules(cls, value: str) -> str:
        validate_password_policy(value)
        return value


class LoginBody(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class ChangePasswordBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=10, max_length=128)

    @field_validator("new_password")
    @classmethod
    def password_rules(cls, value: str) -> str:
        validate_password_policy(value)
        return value


def set_refresh_cookie(response: Response, token: str, expires: datetime) -> None:
    response.set_cookie(
        key="cropmind_refresh",
        value=token,
        httponly=True,
        secure=get_settings().environment == "production",
        samesite="lax",
        expires=expires,
        path="/api/auth",
    )


def clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key="cropmind_refresh",
        path="/api/auth",
        secure=get_settings().environment == "production",
        httponly=True,
        samesite="lax",
    )


def public_user(user: dict) -> dict:
    return {
        "id": str(user["_id"]),
        "email": user["email"],
        "display_name": user.get("display_name"),
        "role": user.get("role", "user"),
        "status": user.get("status", "active"),
    }


@router.post("/register", status_code=201)
def register(body: RegisterBody, db: Database = Depends(get_database)) -> dict:
    registration = db.settings.find_one({"key": "registration_enabled"})
    if registration and registration.get("value") is False:
        raise HTTPException(status_code=403, detail="Public registration is currently disabled.")
    try:
        user = register_user(db, normalize_email(str(body.email)), body.password, body.display_name)
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail="An account with this email already exists.") from None
    return {"user": public_user(user)}


@router.post("/login")
def login(body: LoginBody, response: Response, db: Database = Depends(get_database)) -> dict:
    user = authenticate(db, normalize_email(str(body.email)), body.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials or account temporarily unavailable.")
    access, access_expiry = create_access_token(str(user["_id"]), user.get("role", "user"))
    refresh, refresh_expiry, _ = issue_refresh_token(db, user)
    set_refresh_cookie(response, refresh, refresh_expiry)
    return {
        "access_token": access,
        "token_type": "bearer",
        "expires_at": access_expiry.isoformat(),
        "user": public_user(user),
    }


@router.post("/refresh")
def refresh(request: Request, response: Response, db: Database = Depends(get_database)) -> dict:
    raw = request.cookies.get("cropmind_refresh")
    if not raw:
        raise HTTPException(status_code=401, detail="Refresh session is missing or expired.")
    rotated = rotate_refresh_token(db, raw)
    if not rotated:
        clear_refresh_cookie(response)
        raise HTTPException(status_code=401, detail="Refresh session is invalid or expired.")
    user, new_raw, refresh_expiry = rotated
    access, access_expiry = create_access_token(str(user["_id"]), user.get("role", "user"))
    set_refresh_cookie(response, new_raw, refresh_expiry)
    return {
        "access_token": access,
        "token_type": "bearer",
        "expires_at": access_expiry.isoformat(),
        "user": public_user(user),
    }


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response, db: Database = Depends(get_database)) -> Response:
    raw = request.cookies.get("cropmind_refresh")
    record = db.refresh_tokens.find_one({"token_hash": token_hash(raw)}) if raw else None
    revoke_refresh_token(db, raw)
    if raw:
        write_audit(
            db,
            action="auth.logout",
            actor_id=record.get("user_id") if record else None,
            actor_role="user",
            entity_type="session",
        )
    clear_refresh_cookie(response)
    response.status_code = 204
    return response


@router.get("/me")
def me(user: dict = Depends(current_user)) -> dict:
    return {"user": public_user(user)}


@router.post("/change-password")
def change_password(
    body: ChangePasswordBody,
    db: Database = Depends(get_database),
    user: dict = Depends(current_user),
) -> dict:
    if not verify_password(body.current_password, user.get("password_hash", "")):
        raise HTTPException(status_code=400, detail="Current password is incorrect.")
    now = datetime.now(timezone.utc)
    db.users.update_one(
        {"_id": user["_id"]},
        {"$set": {"password_hash": hash_password(body.new_password), "updated_at": now}},
    )
    db.refresh_tokens.update_many(
        {"user_id": user["_id"], "revoked_at": None},
        {"$set": {"revoked_at": now}},
    )
    write_audit(
        db,
        action="auth.password.changed",
        actor_id=user["_id"],
        actor_email=user["email"],
        actor_role=user["role"],
        entity_type="user",
        entity_id=str(user["_id"]),
    )
    return {"message": "Password changed. Sign in again on your other sessions."}
