"""
Authentication helpers — password hashing and JWT tokens.
"""

from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.config import settings

# bcrypt password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 bearer token — clients send Authorization: Bearer <token>
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/users/login", auto_error=False)


# ── Password helpers ───────────────────────────────────────────────────────────

# bcrypt has a 72-byte limit — truncate before hashing to avoid the ValueError
def _prepare_password(plain: str) -> bytes:
    return plain.encode("utf-8")[:72]


def hash_password(plain: str) -> str:
    return pwd_context.hash(_prepare_password(plain))


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(_prepare_password(plain), hashed)


# ── JWT helpers ────────────────────────────────────────────────────────────────

def create_access_token(user_id: int, email: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": str(user_id), "email": email, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    """Decode and validate a JWT. Raises HTTPException on failure."""
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ── FastAPI dependency ─────────────────────────────────────────────────────────

async def get_current_user(token: str | None = Depends(oauth2_scheme)) -> dict | None:
    """
    Optional auth dependency — returns the decoded token payload if a valid
    Bearer token is present, or None if no token was sent.
    Use require_current_user() when authentication is mandatory.
    """
    if not token:
        return None
    return decode_token(token)


async def require_current_user(token: str | None = Depends(oauth2_scheme)) -> dict:
    """Strict version — raises 401 if no valid token."""
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return decode_token(token)
