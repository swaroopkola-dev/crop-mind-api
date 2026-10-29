from pymongo import ASCENDING, DESCENDING
from pymongo.database import Database


def ensure_indexes(db: Database) -> dict[str, list[str]]:
    definitions = {
        "users": [("users_email_unique", [("email", ASCENDING)], True), ("users_role_status", [("role", ASCENDING), ("status", ASCENDING), ("created_at", DESCENDING)], False)],
        "crops": [("crops_name_unique", [("name_key", ASCENDING)], True), ("crops_active_name", [("active", ASCENDING), ("name", ASCENDING)], False)],
        "recommendations": [("recommendations_owner_created", [("owner_id", ASCENDING), ("created_at", DESCENDING)], False), ("recommendations_created", [("created_at", DESCENDING)], False), ("recommendations_source_synthetic", [("source", ASCENDING), ("is_synthetic", ASCENDING), ("created_at", DESCENDING)], False)],
        "refresh_tokens": [("refresh_token_hash_unique", [("token_hash", ASCENDING)], True), ("refresh_user_family", [("user_id", ASCENDING), ("family_id", ASCENDING), ("revoked_at", ASCENDING)], False), ("refresh_expiry_ttl", [("expires_at", ASCENDING)], False)],
        "activity_logs": [("activity_timestamp", [("timestamp", DESCENDING)], False), ("activity_actor_timestamp", [("actor_id", ASCENDING), ("timestamp", DESCENDING)], False), ("activity_action_timestamp", [("action", ASCENDING), ("timestamp", DESCENDING)], False), ("activity_source_synthetic", [("source", ASCENDING), ("is_synthetic", ASCENDING), ("timestamp", DESCENDING)], False)],
        "settings": [("settings_key_unique", [("key", ASCENDING)], True)],
        "login_attempts": [("login_identifier_unique", [("identifier_hash", ASCENDING)], True), ("login_cleanup_ttl", [("cleanup_at", ASCENDING)], False)],
        "comparisons": [("comparison_owner_created", [("owner_id", ASCENDING), ("created_at", DESCENDING)], False)],
    }
    result: dict[str, list[str]] = {}
    for collection, indexes in definitions.items():
        result[collection] = []
        for name, keys, unique in indexes:
            options: dict = {"name": name}
            if unique:
                options["unique"] = True
            if name in {"refresh_expiry_ttl", "login_cleanup_ttl"}:
                options["expireAfterSeconds"] = 0
                existing = next((item for item in db[collection].list_indexes() if item.get("name") == name), None)
                if existing and existing.get("expireAfterSeconds") != 0:
                    # Atlas connector-created indexes may exist without TTL options.
                    # Recreate them here using PyMongo, which supports expireAfterSeconds.
                    db[collection].drop_index(name)
            db[collection].create_index(keys, **options)
            result[collection].append(name)
    return result
