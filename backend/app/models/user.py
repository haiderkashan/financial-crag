from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserBase(BaseModel):
    """Base user attributes."""

    email: EmailStr = Field(..., description="Unique email address for analyst identification")


class UserCreate(UserBase):
    """Payload for creating a new user record."""

    is_active: bool = Field(default=True, description="Account active status")


class UserInDB(UserBase):
    """User representation stored in Supabase PostgreSQL."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="Unique user UUID")
    is_active: bool = Field(default=True, description="Account active status")
    created_at: datetime = Field(..., description="Timestamp of creation")
    updated_at: datetime = Field(..., description="Timestamp of last update")


class UserResponse(BaseModel):
    """Public user profile response model."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="Unique user UUID")
    email: EmailStr = Field(..., description="Analyst email address")
    is_active: bool = Field(..., description="Account active status")
    created_at: datetime = Field(..., description="Account creation timestamp")
