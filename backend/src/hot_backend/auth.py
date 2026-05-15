"""JWT authentication for admin panel."""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

# Try to import jwt, raise clear error if not installed
try:
    import jwt
except ImportError:
    jwt = None  # type: ignore


class TokenPayload(BaseModel):
    """JWT token payload."""

    sub: str
    exp: datetime
    iat: datetime


class TokenResponse(BaseModel):
    """Login response with token."""

    token: str
    expires_at: str


class LoginRequest(BaseModel):
    """Login request with password."""

    password: str


def get_admin_password() -> str:
    """Get admin password from environment variable."""
    password = os.environ.get("ADMIN_PASSWORD", "")
    if not password:
        raise ValueError(
            "ADMIN_PASSWORD environment variable is not set. "
            "Please set it before using admin features."
        )
    return password


def get_jwt_secret() -> str:
    """Get JWT secret from environment or generate one."""
    secret = os.environ.get("JWT_SECRET", "")
    if not secret:
        # Generate a persistent secret based on ADMIN_PASSWORD
        # This ensures token validity across restarts without explicit JWT_SECRET
        import hashlib

        password = get_admin_password()
        secret = hashlib.sha256(f"jwt-{password}".encode()).hexdigest()
    return secret


def create_token(expires_hours: int = 24) -> TokenResponse:
    """Create a new JWT token."""
    if jwt is None:
        raise ImportError("PyJWT is required. Install it with: uv pip install PyJWT")

    now = datetime.now(UTC)
    exp = now + timedelta(hours=expires_hours)

    payload = {
        "sub": "admin",
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }

    token = jwt.encode(payload, get_jwt_secret(), algorithm="HS256")

    return TokenResponse(
        token=token,
        expires_at=exp.isoformat(),
    )


def verify_token(token: str) -> TokenPayload:
    """Verify a JWT token and return its payload."""
    if jwt is None:
        raise ImportError("PyJWT is required. Install it with: uv pip install PyJWT")

    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=["HS256"])
        return TokenPayload(
            sub=payload["sub"],
            exp=datetime.fromtimestamp(payload["exp"], tz=UTC),
            iat=datetime.fromtimestamp(payload["iat"], tz=UTC),
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )


# Security scheme for OpenAPI
security = HTTPBearer()


async def get_current_admin(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> TokenPayload:
    """Dependency to verify admin authentication."""
    return verify_token(credentials.credentials)


def check_admin_password(password: str) -> bool:
    """Check if the provided password matches the admin password."""
    import secrets

    expected = get_admin_password()
    return secrets.compare_digest(password, expected)
