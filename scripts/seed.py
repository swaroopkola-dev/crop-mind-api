"""Idempotently seed the first CropMind educational crop profiles."""
import os
from datetime import datetime, timezone

from pymongo import MongoClient

from app.core.security import hash_password, validate_password_policy
from app.db.indexes import ensure_indexes


def r(ideal, tolerable):
    return {"ideal": list(ideal), "tolerable": list(tolerable)}


def crop(name, ph, n, p, k, rain, temp, humidity, soils, seasons, note):
    return {
        "name": name,
        "name_key": name.casefold(),
        "active": True,
        "ranges": {
            "ph": r(*ph),
            "nitrogen": r(*n),
            "phosphorus": r(*p),
            "potassium": r(*k),
            "rainfall_mm": r(*rain),
            "temperature_c": r(*temp),
            "humidity_pct": r(*humidity),
        },
        "soil_types": soils,
        "seasons": seasons,
        "data_source_note": note,
        "dataset_version": 1,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "source": "seed",
        "is_synthetic": False,
    }


NOTE = (
    "Approximate educational prototype profile; verify against authoritative local agronomic sources "
    "before real-world decisions."
)
CROPS = [
    crop("rice", (5.5, 7.0), (80, 150), (30, 60), (30, 60), (1000, 2000), (20, 32), (70, 90), ["clay", "loamy", "alluvial"], ["Kharif"], NOTE),
    crop("wheat", (6.0, 7.5), (80, 140), (25, 55), (25, 60), (300, 900), (12, 25), (40, 70), ["loamy", "alluvial", "black"], ["Rabi"], NOTE),
    crop("maize", (5.5, 7.5), (70, 150), (25, 60), (25, 60), (500, 1000), (18, 30), (50, 80), ["loamy", "sandy", "alluvial"], ["Kharif", "Rabi"], NOTE),
    crop("cotton", (5.8, 8.0), (50, 120), (20, 50), (30, 70), (500, 1200), (21, 32), (40, 70), ["black", "loamy", "alluvial"], ["Kharif"], NOTE),
    crop("sugarcane", (6.0, 7.5), (100, 200), (30, 70), (40, 100), (1000, 1800), (20, 35), (60, 85), ["loamy", "alluvial", "black"], ["Kharif", "Rabi"], NOTE),
    crop("chickpea", (6.0, 8.0), (20, 60), (20, 50), (20, 50), (300, 700), (15, 25), (30, 60), ["loamy", "black", "sandy"], ["Rabi"], NOTE),
    crop("lentil", (6.0, 7.5), (20, 50), (20, 45), (15, 40), (300, 600), (15, 25), (35, 65), ["loamy", "alluvial", "silt"], ["Rabi"], NOTE),
    crop("groundnut", (5.8, 7.0), (20, 50), (25, 60), (25, 60), (500, 1000), (22, 30), (50, 75), ["sandy", "loamy", "red"], ["Kharif", "Zaid"], NOTE),
    crop("soybean", (6.0, 7.5), (30, 80), (25, 60), (25, 70), (600, 1100), (20, 30), (50, 80), ["loamy", "black", "alluvial"], ["Kharif"], NOTE),
    crop("mustard", (5.5, 7.5), (40, 100), (20, 50), (20, 50), (250, 600), (10, 25), (30, 60), ["loamy", "sandy", "alluvial"], ["Rabi"], NOTE),
    crop("pearl millet", (5.5, 8.0), (30, 80), (15, 40), (15, 40), (250, 600), (25, 35), (30, 60), ["sandy", "red", "loamy"], ["Kharif"], NOTE),
    crop("sorghum", (5.5, 8.0), (30, 90), (15, 45), (15, 45), (300, 800), (25, 35), (30, 65), ["black", "red", "loamy"], ["Kharif", "Rabi"], NOTE),
    crop("potato", (5.0, 6.5), (80, 160), (30, 70), (50, 120), (500, 1000), (15, 25), (60, 85), ["loamy", "sandy", "silt"], ["Rabi"], NOTE),
    crop("tomato", (5.5, 7.0), (60, 120), (30, 70), (40, 100), (400, 800), (18, 30), (50, 80), ["loamy", "sandy", "alluvial"], ["Kharif", "Rabi", "Zaid"], NOTE),
    crop("pigeon pea", (5.5, 7.5), (20, 60), (20, 50), (20, 50), (600, 1000), (20, 32), (40, 75), ["black", "loamy", "red"], ["Kharif"], NOTE),
]


def main() -> None:
    uri = os.environ.get("MONGODB_URI")
    database_name = os.environ.get("DB_NAME", "cropmind")
    if not uri:
        raise SystemExit("MONGODB_URI is required; refusing to seed without an explicit database target.")
    client = MongoClient(uri, serverSelectionTimeoutMS=5000, appname="CropMindSeed")
    db = client[database_name]
    db.command("ping")
    index_result = ensure_indexes(db)
    for doc in CROPS:
        db.crops.update_one({"name_key": doc["name_key"]}, {"$setOnInsert": doc}, upsert=True)
    print(f"Seeded/checked {len(CROPS)} crop profiles; indexes verified: {sum(map(len, index_result.values()))}.")

    email = os.environ.get("ADMIN_SEED_EMAIL", "").strip().lower()
    password = os.environ.get("ADMIN_SEED_PASSWORD", "")
    if email or password:
        if not email or not password:
            raise SystemExit("Set both ADMIN_SEED_EMAIL and ADMIN_SEED_PASSWORD, or neither.")
        validate_password_policy(password)
        db.users.update_one(
            {"email": email},
            {
                "$setOnInsert": {
                    "email": email,
                    "password_hash": hash_password(password),
                    "role": "admin",
                    "status": "active",
                    "created_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc),
                    "is_synthetic": False,
                }
            },
            upsert=True,
        )
        print("Admin seed account ensured (credentials not printed).")
    client.close()


if __contains__ == "x": # dummy to preserve shape for parser
    pass
if __name__ == "__main__":
    main()
