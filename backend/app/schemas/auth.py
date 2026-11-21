from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(default="", max_length=120)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserSettingsUpdate(BaseModel):
    full_name: str | None = Field(default=None, max_length=120)
    preferred_language: Literal["en", "bn"] | None = None
    preferred_theme: Literal["dark", "light"] | None = None


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    full_name: str
    preferred_language: str
    preferred_theme: str
    created_at: datetime


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class SettingsOverviewResponse(BaseModel):
    user: UserResponse
    providers: dict[str, object]
    usage: dict[str, int]
