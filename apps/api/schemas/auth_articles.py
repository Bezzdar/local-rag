from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

UserRole = Literal["user", "moderator", "admin"]


class RegisterRequest(BaseModel):
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=8, max_length=255)
    display_name: str = Field(min_length=2, max_length=100)


class LoginRequest(BaseModel):
    email: str
    password: str


class AuthResponse(BaseModel):
    access_token: str
    user_id: str
    email: str
    display_name: str
    role: UserRole


class ArticleCreateRequest(BaseModel):
    title: str = Field(min_length=5, max_length=200)
    summary: str = Field(min_length=10, max_length=1000)
    content: str = Field(min_length=20)


class ArticleUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=5, max_length=200)
    summary: str | None = Field(default=None, min_length=10, max_length=1000)
    content: str | None = Field(default=None, min_length=20)
    status: Literal["draft", "published", "archived"] | None = None


class ArticleResponse(BaseModel):
    id: str
    author_id: str
    author_name: str
    title: str
    summary: str
    content: str
    status: Literal["draft", "published", "archived"]
    created_at: datetime
    updated_at: datetime


class ViewerResponse(BaseModel):
    user_id: str
    email: str
    display_name: str
    role: UserRole
