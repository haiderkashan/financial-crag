from datetime import datetime
from typing import Literal, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from backend.app.models.user import UserResponse

TokenType = Literal["magic_link", "refresh_token"]


class TokenBase(BaseModel):
    """Base token properties."""

    token_type: TokenType = Field(..., description="Classification of token")
    expires_at: datetime = Field(..., description="Expiration timestamp (UTC)")


class TokenCreate(TokenBase):
    """Schema for inserting a new token record."""

    user_id: UUID = Field(..., description="Associated user UUID")
    token_hash: str = Field(..., max_length=64, description="SHA-256 digest of secret token")


class TokenInDB(TokenBase):
    """Token representation stored in Supabase PostgreSQL."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="Token UUID")
    user_id: UUID = Field(..., description="Associated user UUID")
    token_hash: str = Field(..., description="SHA-256 hash")
    consumed_at: Optional[datetime] = Field(default=None, description="Timestamp when consumed")
    created_at: datetime = Field(..., description="Token issuance timestamp")


class MagicLinkRequest(BaseModel):
    """Client request schema for requesting a passwordless magic link."""

    email: EmailStr = Field(..., description="Analyst email address for magic link delivery")


class VerifyTokenRequest(BaseModel):
    """Client request schema for verifying a raw magic link or exchange token."""

    token: str = Field(..., min_length=16, description="Raw unhashed cryptographic token string")


class TokenResponse(BaseModel):
    """Authentication tokens returned upon successful authentication."""

    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token authorization type")
    expires_in: int = Field(..., description="Access token lifetime in seconds")
    user: UserResponse = Field(..., description="Authenticated user profile")
