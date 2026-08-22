from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class UserRegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(
        ..., min_length=12, max_length=72, description="Password must be 12-72 characters"
    )
    full_name: str | None = Field(default=None, max_length=255)


class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=72)


class UserResponse(BaseModel):
    id: UUID
    email: str
    full_name: str | None = None
    role: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse


class WebSessionResponse(BaseModel):
    user: UserResponse


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(..., min_length=20, max_length=4096)
