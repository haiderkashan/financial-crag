from datetime import datetime, timezone
from typing import Optional, Union
from uuid import UUID
from supabase import Client
from backend.app.db.supabase import get_supabase_client
from backend.app.models.token import TokenCreate, TokenInDB, TokenType


class TokenRepository:
    """Repository handling persistence operations for the auth_tokens table in Supabase."""

    def __init__(self, client: Optional[Client] = None) -> None:
        self._client = client

    @property
    def client(self) -> Client:
        if self._client is None:
            self._client = get_supabase_client()
        return self._client

    def create_token(self, token_in: TokenCreate) -> TokenInDB:
        """Store a new hashed token record in Supabase."""
        payload = {
            "user_id": str(token_in.user_id),
            "token_hash": token_in.token_hash,
            "token_type": token_in.token_type,
            "expires_at": token_in.expires_at.isoformat(),
        }
        res = self.client.table("auth_tokens").insert(payload).execute()
        if not res.data:
            raise RuntimeError("Failed to insert auth token record into Supabase.")
        return TokenInDB.model_validate(res.data[0])

    def get_valid_token_by_hash(
        self, token_hash: str, token_type: TokenType
    ) -> Optional[TokenInDB]:
        """Look up a token by its hash and type, ensuring it is unconsumed and unexpired."""
        now_iso = datetime.now(timezone.utc).isoformat()
        res = (
            self.client.table("auth_tokens")
            .select("*")
            .eq("token_hash", token_hash)
            .eq("token_type", token_type)
            .is_("consumed_at", "null")
            .gt("expires_at", now_iso)
            .limit(1)
            .execute()
        )
        if res.data and len(res.data) > 0:
            return TokenInDB.model_validate(res.data[0])
        return None

    def mark_token_consumed(self, token_id: Union[UUID, str]) -> Optional[TokenInDB]:
        """Mark a token as consumed with the current timestamp."""
        now_iso = datetime.now(timezone.utc).isoformat()
        res = (
            self.client.table("auth_tokens")
            .update({"consumed_at": now_iso})
            .eq("id", str(token_id))
            .execute()
        )
        if res.data and len(res.data) > 0:
            return TokenInDB.model_validate(res.data[0])
        return None

    def revoke_all_tokens_for_user(
        self, user_id: Union[UUID, str], token_type: Optional[TokenType] = None
    ) -> int:
        """Revoke active tokens for a user by setting consumed_at to now."""
        now_iso = datetime.now(timezone.utc).isoformat()
        query = (
            self.client.table("auth_tokens")
            .update({"consumed_at": now_iso})
            .eq("user_id", str(user_id))
            .is_("consumed_at", "null")
        )
        if token_type is not None:
            query = query.eq("token_type", token_type)
        res = query.execute()
        return len(res.data) if res.data else 0

    def delete_token(self, token_id: Union[UUID, str]) -> bool:
        """Permanently delete a token record (primarily for test cleanup)."""
        res = (
            self.client.table("auth_tokens")
            .delete()
            .eq("id", str(token_id))
            .execute()
        )
        return bool(res.data)


token_repo = TokenRepository()
