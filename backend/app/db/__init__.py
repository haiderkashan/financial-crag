"""Database package with Supabase client and repositories."""
from backend.app.db.supabase import get_supabase_client

__all__ = ["get_supabase_client"]
