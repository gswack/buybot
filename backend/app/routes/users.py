"""
User management routes.

POST /api/users/register  — create account
POST /api/users/login     — get JWT token
GET  /api/users/me        — get current user profile
PUT  /api/users/me        — update profile (age, memberships)
"""

import json

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, field_validator

from app.auth import (
    create_access_token,
    get_current_user,
    hash_password,
    require_current_user,
    verify_password,
)
from app.database import get_pool

router = APIRouter(prefix="/users", tags=["users"])


# ── Request / Response models ──────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    age: int | None = None
    memberships: list[str] = []

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("Password must be at least 6 characters")
        return v


class ProfileUpdate(BaseModel):
    age: int | None = None
    memberships: list[str] | None = None


class UserResponse(BaseModel):
    id: int
    email: str
    age: int | None
    memberships: list[str]


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


# ── Helpers ────────────────────────────────────────────────────────────────────

def _row_to_user(row) -> UserResponse:
    memberships = row["memberships"]
    if isinstance(memberships, str):
        memberships = json.loads(memberships)
    return UserResponse(
        id=row["id"],
        email=row["email"],
        age=row["age"],
        memberships=memberships or [],
    )


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest):
    pool = get_pool()
    async with pool.acquire() as conn:
        existing = await conn.fetchrow("SELECT id FROM users WHERE email = $1", body.email)
        if existing:
            raise HTTPException(status_code=400, detail="Email already registered")

        row = await conn.fetchrow(
            """
            INSERT INTO users (email, password_hash, age, memberships)
            VALUES ($1, $2, $3, $4::jsonb)
            RETURNING id, email, age, memberships
            """,
            body.email,
            hash_password(body.password),
            body.age,
            json.dumps(body.memberships),
        )

    user = _row_to_user(row)
    token = create_access_token(user.id, user.email)
    return TokenResponse(access_token=token, user=user)


@router.post("/login", response_model=TokenResponse)
async def login(form: OAuth2PasswordRequestForm = Depends()):
    """Standard OAuth2 password flow — username field carries the email."""
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, email, password_hash, age, memberships FROM users WHERE email = $1",
            form.username,
        )

    if not row or not verify_password(form.password, row["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    user = _row_to_user(row)
    token = create_access_token(user.id, user.email)
    return TokenResponse(access_token=token, user=user)


@router.get("/me", response_model=UserResponse)
async def get_me(current: dict = Depends(require_current_user)):
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, email, age, memberships FROM users WHERE id = $1",
            int(current["sub"]),
        )
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    return _row_to_user(row)


@router.put("/me", response_model=UserResponse)
async def update_me(body: ProfileUpdate, current: dict = Depends(require_current_user)):
    pool = get_pool()
    user_id = int(current["sub"])

    async with pool.acquire() as conn:
        # Fetch current values to merge
        row = await conn.fetchrow(
            "SELECT id, email, age, memberships FROM users WHERE id = $1", user_id
        )
        if not row:
            raise HTTPException(status_code=404, detail="User not found")

        new_age = body.age if body.age is not None else row["age"]
        existing_memberships = row["memberships"]
        if isinstance(existing_memberships, str):
            existing_memberships = json.loads(existing_memberships)
        new_memberships = body.memberships if body.memberships is not None else existing_memberships

        updated = await conn.fetchrow(
            """
            UPDATE users
            SET age = $1, memberships = $2::jsonb, updated_at = now()
            WHERE id = $3
            RETURNING id, email, age, memberships
            """,
            new_age,
            json.dumps(new_memberships),
            user_id,
        )

    return _row_to_user(updated)
