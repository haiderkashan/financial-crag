import hashlib
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.core.config import settings
from backend.app.db.repositories.token_repo import token_repo
from backend.app.db.repositories.user_repo import user_repo
from backend.app.db.supabase import get_supabase_client
from backend.app.models.token import TokenCreate, TokenInDB
from backend.app.models.user import UserCreate, UserInDB


def run_database_verification() -> bool:
    """End-to-end database verification for Supabase schema and repository layer."""
    print("=" * 60)
    print("SUB-PHASE 1.2: SUPABASE DATABASE VERIFICATION CHECKPOINT")
    print("=" * 60)

    # 1. Inspect environment configuration
    url = settings.SUPABASE_URL
    key = settings.effective_supabase_key

    if not url or not key:
        print("[FAIL] Missing Supabase configuration.")
        print(f"  SUPABASE_URL: {'Configured' if url else 'MISSING'}")
        print(f"  SUPABASE_SERVICE_KEY / ROLE_KEY: {'Configured' if key else 'MISSING'}")
        print("\nPlease ensure your backend/.env file contains:")
        print("  SUPABASE_URL=https://your-project.supabase.co")
        print("  SUPABASE_SERVICE_KEY=your-service-role-key")
        return False

    print(f"[OK] Supabase URL configured: {url}")
    print(f"[OK] Supabase Service Key configured: {key[:8]}...{key[-4:]}")

    # 2. Test Client Initialization
    try:
        client = get_supabase_client()
        print("[OK] Supabase client singleton successfully initialized.")
    except Exception as e:
        print(f"[FAIL] Error initializing Supabase client: {e}")
        return False

    # 3. Test User Creation & Retrieval
    test_email = f"test_analyst_{uuid4().hex[:8]}@example.com"
    created_user: UserInDB | None = None
    created_token: TokenInDB | None = None

    try:
        print(f"\n[TEST 1] Inserting test user: {test_email}")
        created_user = user_repo.create_user(UserCreate(email=test_email))
        print(f"  -> User inserted with ID: {created_user.id}")
        assert created_user.email == test_email.lower()
        assert created_user.is_active is True
        print("[PASS] User creation validated against Pydantic schema UserInDB.")

        print(f"\n[TEST 2] Querying user by email: {test_email}")
        queried_user = user_repo.get_by_email(test_email)
        assert queried_user is not None
        assert queried_user.id == created_user.id
        print("[PASS] User query by email successful.")

        # 4. Test Token Creation & Validation
        raw_secret = "sec_test_secret_token_" + uuid4().hex
        token_hash = hashlib.sha256(raw_secret.encode("utf-8")).hexdigest()
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)

        print("\n[TEST 3] Creating auth token linked via foreign key")
        token_in = TokenCreate(
            user_id=created_user.id,
            token_hash=token_hash,
            token_type="magic_link",
            expires_at=expires_at,
        )
        created_token = token_repo.create_token(token_in)
        assert created_token.user_id == created_user.id
        assert created_token.consumed_at is None
        print(f"  -> Auth token inserted with ID: {created_token.id}")
        print("[PASS] Token creation validated against Pydantic schema TokenInDB.")

        print("\n[TEST 4] Querying active token by hash & type")
        valid_token = token_repo.get_valid_token_by_hash(token_hash, "magic_link")
        assert valid_token is not None
        assert valid_token.id == created_token.id
        print("[PASS] Active token successfully retrieved.")

        print("\n[TEST 5] Marking token as consumed (Anti-Replay Test)")
        consumed_token = token_repo.mark_token_consumed(created_token.id)
        assert consumed_token is not None
        assert consumed_token.consumed_at is not None
        print(f"  -> Consumed at: {consumed_token.consumed_at}")

        second_lookup = token_repo.get_valid_token_by_hash(token_hash, "magic_link")
        assert second_lookup is None, "Consumed token must not be returned by get_valid_token_by_hash!"
        print("[PASS] Consumed token successfully rejected on subsequent query.")

    except Exception as e:
        print(f"\n[FAIL] Database verification encountered an error: {e}")
        return False
    finally:
        # 5. Cleanup test artifacts
        print("\n[CLEANUP] Cleaning up test records...")
        if created_token:
            token_repo.delete_token(created_token.id)
            print(f"  -> Deleted test token: {created_token.id}")
        if created_user:
            user_repo.delete_user(created_user.id)
            print(f"  -> Deleted test user: {created_user.id}")

    print("\n" + "=" * 60)
    print("[ALL PASS] Sub-Phase 1.2 Database & Schema Verification Succeeded!")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = run_database_verification()
    sys.exit(0 if success else 1)
