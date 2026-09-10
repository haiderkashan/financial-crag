import hashlib
from datetime import datetime, timedelta, timezone
from uuid import uuid4
import pytest
from backend.app.core.config import settings
from backend.app.models.token import TokenCreate
from backend.app.models.user import UserCreate


@pytest.mark.skipif(
    not (settings.SUPABASE_URL and settings.effective_supabase_key),
    reason="Supabase credentials not configured in environment",
)
def test_supabase_user_and_token_lifecycle():
    """Verify repository CRUD and constraints with live Supabase database."""
    from backend.app.db.repositories.user_repo import user_repo
    from backend.app.db.repositories.token_repo import token_repo

    test_email = f"pytest_{uuid4().hex[:8]}@financialcrag.local"
    user = user_repo.create_user(UserCreate(email=test_email))
    assert user.email == test_email.lower()

    raw_token = "pytest_token_" + uuid4().hex
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    token_in = TokenCreate(
        user_id=user.id,
        token_hash=token_hash,
        token_type="magic_link",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
    )
    token = token_repo.create_token(token_in)
    assert token.user_id == user.id

    # Retrieve valid
    fetched = token_repo.get_valid_token_by_hash(token_hash, "magic_link")
    assert fetched is not None
    assert fetched.id == token.id

    # Mark consumed
    consumed = token_repo.mark_token_consumed(token.id)
    assert consumed.consumed_at is not None

    # Replay check
    assert token_repo.get_valid_token_by_hash(token_hash, "magic_link") is None

    # Cleanup
    token_repo.delete_token(token.id)
    user_repo.delete_user(user.id)
