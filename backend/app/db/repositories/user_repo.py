from typing import Optional, Union
from uuid import UUID
from supabase import Client
from backend.app.db.supabase import get_supabase_client
from backend.app.models.user import UserCreate, UserInDB


class UserRepository:
    """Repository handling persistence operations for the users table in Supabase."""

    def __init__(self, client: Optional[Client] = None) -> None:
        self._client = client

    @property
    def client(self) -> Client:
        if self._client is None:
            self._client = get_supabase_client()
        return self._client

    def get_by_email(self, email: str) -> Optional[UserInDB]:
        """Fetch an active user by their email address."""
        clean_email = email.strip().lower()
        res = (
            self.client.table("users")
            .select("*")
            .eq("email", clean_email)
            .limit(1)
            .execute()
        )
        if res.data and len(res.data) > 0:
            return UserInDB.model_validate(res.data[0])
        return None

    def get_by_id(self, user_id: Union[UUID, str]) -> Optional[UserInDB]:
        """Fetch a user by their unique primary key UUID."""
        uid_str = str(user_id)
        res = (
            self.client.table("users")
            .select("*")
            .eq("id", uid_str)
            .limit(1)
            .execute()
        )
        if res.data and len(res.data) > 0:
            return UserInDB.model_validate(res.data[0])
        return None

    def create_user(self, user_in: UserCreate) -> UserInDB:
        """Insert a new user record into the users table."""
        payload = {
            "email": user_in.email.strip().lower(),
            "is_active": user_in.is_active,
        }
        res = self.client.table("users").insert(payload).execute()
        if not res.data:
            raise RuntimeError(f"Failed to create user with email: {user_in.email}")
        return UserInDB.model_validate(res.data[0])

    def get_or_create_by_email(self, email: str) -> UserInDB:
        """Fetch user by email if exists, otherwise create a new active user."""
        existing = self.get_by_email(email)
        if existing:
            return existing
        return self.create_user(UserCreate(email=email))

    def delete_user(self, user_id: Union[UUID, str]) -> bool:
        """Delete a user record by UUID (primarily for test cleanup)."""
        uid_str = str(user_id)
        res = self.client.table("users").delete().eq("id", uid_str).execute()
        return bool(res.data)


user_repo = UserRepository()
