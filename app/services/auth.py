from datetime import datetime, timedelta
import hashlib

from pymongo.database import Database

from app.core.config import get_settings
from app.core.security import hash_password, new_refresh_token, token_hash, validate_password_policy, verify_password
from app.db.repositories import utcnow, write_audit

_DUMMY_PASSWORD_HASH: str | None = None


def normalize_email(email: str) -> str:
    return email.strip().lower()


def register_user(db: Database, email: str, password: str, display_name: str | None = None) -> dict:
    validate_password_policy(password)
    normalized = normalize_email(email)
    now = utcnow()
    doc = {
        "email": normalized,
        "display_name": display_name,
        "password_hash": hash_password(password),
        "role": "user",
        "status": "active",
        "created_at": now,
        "updated_at": now,
        "source": "live",
        "is_synthetic": False,
    }
    result = db.users.insert_one(doc)
    doc["_id"] = result.inserted_id
    write_audit(
        db,
        action="auth.register",
        actor_id=result.inserted_id,
        actor_email=normalized,
        actor_role="user",
        entity_type="user",
        entity_id=str(result.inserted_id),
    )
    return doc


def identifier_hash(email: str) -> str:
    return hashlib.sha256(normalize_email(email).encode("utf-8")).hexdigest()


def login_allowed(db: Database, email: str) -> bool:
    entry = db.login_attempts.find_one({"identifier_hash": identifier_hash(email)})
    return not entry or not entry.get("lockout_until") or entry["lockout_until"] <= utcnow()


def record_failed_login(db: Database, email: str) -> None:
    now = utcnow()
    key = identifier_hash(email)
    current = db.login_attempts.find_one({"identifier_hash": key}) or {"failed_count": 0}
    count = int(current.get("failed_count", 0)) + 1
    update = {
        "$set": {
            "identifier_hash": key,
            "failed_count": count,
            "last_failure_at": now,
            "cleanup_at": now + timedelta(days=2),
        }
    }
    if count >= 5:
        update["$set"]["lockout_until"] = now + timedelta(minutes=15)
    db.login_attempts.update_one({"identifier_hash": key}, update, upsert=True)


def clear_failed_login(db: Database, email: str) -> None:
    db.login_attempts.delete_one({"identifier_hash": identifier_hash(email)})


def authenticate(db: Database, email: str, password: str) -> dict | None:
    normalized = normalize_email(email)
    user = db.users.find_one({"email": normalized})
    if not login_allowed(db, normalized):
        return None
    global _DUMMY_PASSWORD_HASH
    if _DUMMY_PASSWORD_HASH is None:
        _DUMMY_PASSWORD_HASH = hash_password("DummyPass123")
    valid = (
        verify_password(password, user["password_hash"])
        if user and user.get("password_hash")
        else verify_password(password, _DUMMY_PASSWORD_HASH)
    )
    if not user or not valid or user.get("status") != "active":
        record_failed_login(db, normalized)
        write_audit(
            db,
            action="auth.login.failure",
            actor_email=normalized,
            actor_role="anonymous",
            metadata={"reason": "invalid_credentials_or_inactive"},
        )
        return None
    clear_failed_login(db, normalized)
    write_audit(
        db,
        action="auth.login.success",
        actor_id=user["_id"],
        actor_email=normalized,
        actor_role=user.get("role", "user"),
        entity_type="user",
        entity_id=str(user["_id"]),
    )
    return user


def issue_refresh_token(
    db: Database, user: dict, family_id: str | None = None
) -> tuple[str, datetime, str]:
    settings = get_settings()
    raw = new_refresh_token()
    now = utcnow()
    expires = now + timedelta(days=settings.refresh_token_expire_days)
    family = family_id or new_refresh_token()[:24]
    db.refresh_tokens.insert_one(
        {
            "user_id": user["_id"],
            "token_hash": token_hash(raw),
            "family_id": family,
            "issued_at": now,
            "expires_at": expires,
            "revoked_at": None,
            "replaced_by": None,
        }
    )
    return raw, expires, family


def rotate_refresh_token(db: Database, raw_token: str) -> tuple[dict, str, datetime] | None:
    now = utcnow()
    digest = token_hash(raw_token)
    record = db.refresh_tokens.find_one({"token_hash": digest})
    if not record:
        return None
    if record.get("revoked_at"):
        db.refresh_tokens.update_many(
            {"family_id": record["family_id"], "revoked_at": None},
            {"$set": {"revoked_at": now}},
        )
        return None
    if record["expires_at"] <= now:
        db.refresh_tokens.update_one({"_id": record["_id"]}, {"$set": {"revoked_at": now}})
        return None
    user = db.users.find_one({"_id": record["user_id"], "status": "active"})
    if not user:
        db.refresh_tokens.update_many(
            {"family_id": record["family_id"], "revoked_at": None},
            {"$set": {"revoked_at": now}},
        )
        return None
    new_raw, expires, _ = issue_refresh_token(db, user, record["family_id"])
    replaced_hash = token_hash(new_raw)
    updated = db.refresh_tokens.update_one(
        {"_id": record["_id"], "revoked_at": None},
        {"$set": {"revoked_at": now, "replaced_by": replaced_hash}},
    )
    if updated.modified_count != 1:
        db.refresh_tokens.update_many(
            {"family_id": record["family_id"], "revoked_at": None},
            {"$set": {"revoked_at": now}},
        )
        return None
    write_audit(
        db,
        action="auth.token.refresh",
        actor_id=user["_id"],
        actor_email=user["email"],
        actor_role=user["role"],
        entity_type="user",
        entity_id=str(user["_id"]),
    )
    return user, new_raw, expires


def revoke_refresh_token(db: Database, raw_token: str | None) -> None:
    if not raw_token:
        return
    db.refresh_tokens.update_one(
        {"token_hash": token_hash(raw_token), "revoked_at": None},
        {"$set": {"revoked_at": utcnow()}},
    )
