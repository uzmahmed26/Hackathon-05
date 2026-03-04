"""
Authentication router for Customer Success FTE
Provides signup, login, and user-info endpoints using JWT + bcrypt
"""

from fastapi import APIRouter, HTTPException, Depends, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import Optional
import bcrypt
import os
import logging

logger = logging.getLogger(__name__)

# ── Config ─────────────────────────────────────────────────────────────────────

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "changeme-use-a-real-secret-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

bearer_scheme = HTTPBearer(auto_error=False)

router = APIRouter(prefix="/api/auth", tags=["auth"])


# ── Schemas ────────────────────────────────────────────────────────────────────

class SignupRequest(BaseModel):
    name: str
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


# ── Helpers ────────────────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode["exp"] = expire
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None


def get_db(request: Request):
    """Get db_manager from app state via request object."""
    db = request.app.state.db_manager
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    return db


# ── DB helpers ─────────────────────────────────────────────────────────────────

async def get_user_by_email(db, email: str) -> Optional[dict]:
    async with db.pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, email, name, password_hash, is_active, created_at FROM users WHERE email = $1",
            email
        )
        return dict(row) if row else None


async def create_user(db, name: str, email: str, password_hash: str) -> dict:
    async with db.pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO users (name, email, password_hash)
            VALUES ($1, $2, $3)
            RETURNING id, email, name, created_at
            """,
            name, email, password_hash
        )
        return dict(row)


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.post("/signup", response_model=TokenResponse, status_code=201)
async def signup(body: SignupRequest, request: Request):
    """Register a new user account."""
    db = get_db(request)

    if len(body.password) < 8:
        raise HTTPException(status_code=422, detail="Password must be at least 8 characters")

    existing = await get_user_by_email(db, body.email)
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    pw_hash = hash_password(body.password)
    try:
        user = await create_user(db, body.name.strip(), body.email, pw_hash)
    except Exception as e:
        logger.error(f"Signup error: {e}")
        raise HTTPException(status_code=500, detail="Could not create account")

    token = create_access_token({"sub": str(user["id"]), "email": user["email"]})
    return TokenResponse(
        access_token=token,
        user={"id": str(user["id"]), "name": user["name"], "email": user["email"]}
    )


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, request: Request):
    """Authenticate and receive a JWT token."""
    db = get_db(request)

    user = await get_user_by_email(db, body.email)
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not user.get("is_active", True):
        raise HTTPException(status_code=403, detail="Account is disabled")

    token = create_access_token({"sub": str(user["id"]), "email": user["email"]})
    return TokenResponse(
        access_token=token,
        user={"id": str(user["id"]), "name": user["name"], "email": user["email"]}
    )


@router.get("/me")
async def get_me(request: Request, credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    """Return current authenticated user info."""
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")

    payload = decode_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    db = get_db(request)
    user = await get_user_by_email(db, payload["email"])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "id": str(user["id"]),
        "name": user["name"],
        "email": user["email"],
        "created_at": user["created_at"].isoformat() if user.get("created_at") else None
    }
