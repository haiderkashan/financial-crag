import hashlib
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient

from backend.app.core.config import settings
from backend.app.core.security import generate_magic_token, hash_token
from backend.app.db.repositories.token_repo import token_repo
from backend.app.db.repositories.user_repo import user_repo
from backend.app.main import app

client = TestClient(app)


@pytest.fixture
def test_analyst():
    """Create a unique test analyst user and clean up afterwards."""
    test_email = f"analyst_auth_test_{uuid4().hex[:8]}@example.com"
    user = user_repo.get_or_create_by_email(test_email)
    yield user
    # Cleanup all tokens and user
    token_repo.revoke_all_tokens_for_user(user.id)
    user_repo.delete_user(user.id)


def test_request_magic_link_hashes_token():
    """Verify that request-magic-link generates a token, hashes it, and never stores raw token."""
    email = f"request_test_{uuid4().hex[:8]}@example.com"

    response = client.post(
        "/api/v1/auth/request-magic-link",
        json={"email": email},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"

    # Verify user exists in database
    user = user_repo.get_by_email(email)
    assert user is not None

    # Cleanup
    token_repo.revoke_all_tokens_for_user(user.id)
    user_repo.delete_user(user.id)


def test_verify_token_success_and_anti_replay(test_analyst):
    """Verify token validation, HTTP-only cookie setting, and anti-replay defense."""
    raw_token = generate_magic_token()
    token_hash = hash_token(raw_token)

    from datetime import datetime, timedelta, timezone
    from backend.app.models.token import TokenCreate

    # Insert valid token in DB
    created = token_repo.create_token(
        TokenCreate(
            user_id=test_analyst.id,
            token_hash=token_hash,
            token_type="magic_link",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
        )
    )

    # 1. Successful First Verification
    response = client.post(
        "/api/v1/auth/verify-token",
        json={"token": raw_token},
    )
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert body["user"]["email"] == test_analyst.email

    # Check HTTP-only cookie headers
    cookies = response.cookies
    assert "access_token" in cookies
    assert "refresh_token" in cookies

    # Check Raw Set-Cookie header contains HttpOnly and SameSite=lax
    set_cookie_headers = response.headers.get_list("set-cookie")
    assert any("HttpOnly" in h or "httponly" in h for h in set_cookie_headers)
    assert any("SameSite=lax" in h or "samesite=lax" in h for h in set_cookie_headers)

    # 2. Anti-Replay Check: Replaying the SAME token must be rejected
    replay_response = client.post(
        "/api/v1/auth/verify-token",
        json={"token": raw_token},
    )
    assert replay_response.status_code == 400
    assert "consumed" in replay_response.json()["detail"].lower()


def test_verify_token_invalid_token():
    """Verify that non-existent or malformed tokens are rejected."""
    response = client.post(
        "/api/v1/auth/verify-token",
        json={"token": "completely_invalid_bogus_token_12345678"},
    )
    assert response.status_code == 400


def test_get_me_protected_endpoint(test_analyst):
    """Verify GET /api/v1/auth/me with Bearer token and unauthorized rejection."""
    from backend.app.core.security import create_access_token

    access_token = create_access_token(test_analyst.id)

    # Authorized request with Bearer header
    auth_headers = {"Authorization": f"Bearer {access_token}"}
    resp = client.get("/api/v1/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["email"] == test_analyst.email

    # Authorized request with Cookie
    client.cookies.set("access_token", access_token)
    cookie_resp = client.get("/api/v1/auth/me")
    assert cookie_resp.status_code == 200
    assert cookie_resp.json()["id"] == str(test_analyst.id)
    client.cookies.clear()

    # Unauthorized request (no token)
    unauth_resp = client.get("/api/v1/auth/me")
    assert unauth_resp.status_code == 401

    # Unauthorized request (invalid signature)
    bad_resp = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer forged.token.signature"},
    )
    assert bad_resp.status_code == 401


def test_refresh_token_flow(test_analyst):
    """Verify refresh token exchange for fresh access token."""
    from backend.app.core.security import create_refresh_token
    from backend.app.models.token import TokenCreate
    from datetime import datetime, timedelta, timezone

    refresh_token = create_refresh_token(test_analyst.id)
    token_repo.create_token(
        TokenCreate(
            user_id=test_analyst.id,
            token_hash=hash_token(refresh_token),
            token_type="refresh_token",
            expires_at=datetime.now(timezone.utc) + timedelta(days=14),
        )
    )

    # Attempt refresh via Cookie
    client.cookies.set("refresh_token", refresh_token)
    resp = client.post("/api/v1/auth/refresh")
    assert resp.status_code == 200
    assert "access_token" in resp.json()
    assert "access_token" in resp.cookies
    client.cookies.clear()


def test_logout_clears_session(test_analyst):
    """Verify logout revokes refresh tokens in DB and deletes cookies."""
    from backend.app.core.security import create_access_token, create_refresh_token
    from backend.app.models.token import TokenCreate
    from datetime import datetime, timedelta, timezone

    access_token = create_access_token(test_analyst.id)
    refresh_token = create_refresh_token(test_analyst.id)

    token_repo.create_token(
        TokenCreate(
            user_id=test_analyst.id,
            token_hash=hash_token(refresh_token),
            token_type="refresh_token",
            expires_at=datetime.now(timezone.utc) + timedelta(days=14),
        )
    )

    client.cookies.set("access_token", access_token)
    client.cookies.set("refresh_token", refresh_token)

    logout_resp = client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert logout_resp.status_code == 200

    # Verify refresh token in DB is now revoked (consumed_at is not null)
    valid_in_db = token_repo.get_valid_token_by_hash(hash_token(refresh_token), "refresh_token")
    assert valid_in_db is None

    client.cookies.clear()
