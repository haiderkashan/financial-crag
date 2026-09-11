from typing import Optional
from fastapi import Cookie, Depends, Header, HTTPException, status
from jose import JWTError

from backend.app.core.security import decode_jwt_token
from backend.app.db.repositories.user_repo import UserRepository, user_repo
from backend.app.models.user import UserInDB


async def get_current_user(
    authorization: Optional[str] = Header(None, description="Standard Bearer token header"),
    access_token: Optional[str] = Cookie(None, description="HTTP-only access token cookie"),
    repo: UserRepository = Depends(lambda: user_repo),
) -> UserInDB:
    """FastAPI authentication dependency resolving the current active analyst.

    Extracts JWT from either Authorization Bearer header or HTTP-only access_token cookie.
    Validates cryptographic signature, token type, expiration, and database active status.
    """
    token: Optional[str] = None

    if authorization and authorization.startswith("Bearer "):
        token = authorization[len("Bearer ") :].strip()
    elif access_token:
        token = access_token.strip()

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_jwt_token(token)
        token_type = payload.get("type")
        if token_type != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type for access authentication.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Malformed token payload: missing subject.",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired or signature is invalid.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = repo.get_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Analyst account associated with token was not found.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Analyst account has been suspended or deactivated.",
        )

    return user
