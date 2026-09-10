from functools import lru_cache
from supabase import create_client, Client
from backend.app.core.config import settings


@lru_cache()
def get_supabase_client() -> Client:
    """Returns a cached singleton instance of the Supabase Client.

    Uses SUPABASE_URL and SUPABASE_SERVICE_KEY / SUPABASE_SERVICE_ROLE_KEY.
    """
    url: str = settings.SUPABASE_URL
    key: str = settings.effective_supabase_key

    if not url or not key:
        raise ValueError(
            "Supabase credentials missing. Ensure SUPABASE_URL and SUPABASE_SERVICE_KEY "
            "(or SUPABASE_SERVICE_ROLE_KEY) are set in backend/.env or root .env."
        )

    return create_client(url, key)
