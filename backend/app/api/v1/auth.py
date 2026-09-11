from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from jose import JWTError

from backend.app.api.deps import get_current_user
from backend.app.core.config import settings
from backend.app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_jwt_token,
    generate_magic_token,
    hash_token,
)
from backend.app.db.repositories.token_repo import TokenRepository, token_repo
from backend.app.db.repositories.user_repo import UserRepository, user_repo
from backend.app.models.token import (
    MagicLinkRequest,
    TokenCreate,
    TokenResponse,
    VerifyTokenRequest,
)
from backend.app.models.user import UserInDB, UserResponse
from backend.app.services.email_service import EmailService, email_service

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/request-magic-link",
    status_code=status.HTTP_200_OK,
    summary="Request a passwordless verification magic link",
    description="Generates a single-use SHA-256 hashed magic token and dispatches an asynchronous verification email.",
)
async def request_magic_link(
    payload: MagicLinkRequest,
    u_repo: UserRepository = Depends(lambda: user_repo),
    t_repo: TokenRepository = Depends(lambda: token_repo),
    e_service: EmailService = Depends(lambda: email_service),
) -> dict:
    """Request a passwordless authentication token."""
    email_clean = payload.email.strip().lower()

    # Retrieve or create user record
    user = u_repo.get_or_create_by_email(email_clean)
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated. Contact system administrator.",
        )

    # Generate raw random token and hash it with SHA-256
    raw_token = generate_magic_token()
    token_hashed = hash_token(raw_token)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.MAGIC_LINK_EXPIRE_MINUTES)

    # Store only the SHA-256 hash in database
    t_repo.create_token(
        TokenCreate(
            user_id=user.id,
            token_hash=token_hashed,
            token_type="magic_link",
            expires_at=expires_at,
        )
    )

    # Dispatch email with raw unhashed token
    await e_service.send_magic_link_email(email=user.email, token=raw_token)

    return {
        "status": "success",
        "message": "If the email is valid, an authentication link has been dispatched.",
    }


@router.post(
    "/verify-token",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Verify magic link token and issue JWT session",
    description="Validates token against SHA-256 hash in DB, enforces anti-replay, and sets HTTP-only cookies.",
)
async def verify_token(
    payload: VerifyTokenRequest,
    response: Response,
    u_repo: UserRepository = Depends(lambda: user_repo),
    t_repo: TokenRepository = Depends(lambda: token_repo),
) -> TokenResponse:
    """Verify raw token string, mark consumed, and return JWT credentials."""
    raw_token = payload.token.strip()
    token_hashed = hash_token(raw_token)

    # Look up token by SHA-256 hash & type, ensuring it is active and unconsumed
    token_record = t_repo.get_valid_token_by_hash(token_hashed, "magic_link")

    # Anti-replay check: Must exist, not expired, and not consumed
    if not token_record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid, expired, or previously consumed verification token.",
        )

    # Enforce Anti-Replay: Mark token as consumed immediately
    t_repo.mark_token_consumed(token_record.id)

    # Retrieve user
    user = u_repo.get_by_id(token_record.user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Associated analyst account is nonexistent or inactive.",
        )

    # Issue JWT Access Token & Refresh Token
    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)

    # Persist Refresh Token hash in database for stateful revocation
    t_repo.create_token(
        TokenCreate(
            user_id=user.id,
            token_hash=hash_token(refresh_token),
            token_type="refresh_token",
            expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
    )

    # Set Secure HTTP-only cookies
    is_secure = settings.ENVIRONMENT.lower() != "development"
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=is_secure,
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=is_secure,
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path="/",
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserResponse.model_validate(user),
    )


@router.post(
    "/refresh",
    status_code=status.HTTP_200_OK,
    summary="Refresh an expired access token using a refresh token",
    description="Validates active refresh token from cookie or payload and returns a fresh access token.",
)
async def refresh_access_token(
    response: Response,
    refresh_token: Optional[str] = Cookie(None),
    t_repo: TokenRepository = Depends(lambda: token_repo),
    u_repo: UserRepository = Depends(lambda: user_repo),
) -> dict:
    """Exchange a valid refresh token for a fresh access token."""
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token cookie missing.",
        )

    try:
        payload = decode_jwt_token(refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Provided token is not a valid refresh token.",
            )
        user_id = payload.get("sub")
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has expired or is cryptographically invalid.",
        )

    # Verify refresh token in DB
    token_hashed = hash_token(refresh_token)
    db_token = t_repo.get_valid_token_by_hash(token_hashed, "refresh_token")
    if not db_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has been revoked or consumed.",
        )

    user = u_repo.get_by_id(user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Analyst account is deactivated or missing.",
        )

    # Issue new access token
    new_access_token = create_access_token(user.id)

    # Set new access token cookie
    is_secure = settings.ENVIRONMENT.lower() != "development"
    response.set_cookie(
        key="access_token",
        value=new_access_token,
        httponly=True,
        secure=is_secure,
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )

    return {
        "access_token": new_access_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }


@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    summary="Terminate analyst session",
    description="Revokes all active refresh tokens in DB and clears authentication cookies.",
)
async def logout(
    response: Response,
    current_user: UserInDB = Depends(get_current_user),
    t_repo: TokenRepository = Depends(lambda: token_repo),
) -> dict:
    """Log out analyst, invalidate stateful tokens in DB, and clear session cookies."""
    # Revoke active refresh tokens
    t_repo.revoke_all_tokens_for_user(current_user.id, token_type="refresh_token")

    # Clear cookies
    is_secure = settings.ENVIRONMENT.lower() != "development"
    response.delete_cookie(key="access_token", path="/", httponly=True, secure=is_secure, samesite="lax")
    response.delete_cookie(key="refresh_token", path="/", httponly=True, secure=is_secure, samesite="lax")

    return {
        "status": "success",
        "message": "Analyst session revoked successfully.",
    }


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve current analyst profile",
    description="Returns profile information for the actively authenticated analyst.",
)
async def get_me(current_user: UserInDB = Depends(get_current_user)) -> UserResponse:
    """Fetch current authenticated user profile."""
    return UserResponse.model_validate(current_user)
