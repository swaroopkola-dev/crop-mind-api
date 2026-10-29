from app.core.security import hash_password, verify_password, new_refresh_token, token_hash


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
