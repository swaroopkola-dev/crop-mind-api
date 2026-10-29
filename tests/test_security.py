import pytest

from app.core.security import hash_password, new_refresh_token, token_hash, verify_password


def test_password_is_hashed_and_verifiable():
    stored = hash_password("StrongPass123")
    assert stored != "StrongPass123"
    assert verify_password("StrongPass123", stored)
    assert not verify_password("wrong", stored)


def test_refresh_token_is_random_and_only_digest_should_be_stored():
    first = new_refresh_token()
    second = new_refresh_token()
    assert first != second
    assert token_hash(first) != first
    assert len(token_hash(first)) == 64


def test_environment_contract_has_requested_keys_only():
    from app.core.config import Settings

    settings = Settings(_env_file=None)
    assert settings.db_name == "cropmind"
    assert settings.jwt_algorithm == "HS256"
    assert settings.access_token_expire_minutes == 15
    assert settings.refresh_token_expire_days == 7
    assert settings.gemini_model == "gemini-3.8-flash"
    assert settings.frontend_origin == "http://localhost:3000"
