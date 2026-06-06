import hashlib
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import hash_password, verify_password, create_access_token, create_refresh_token
from app.db.models import User, RefreshToken
from app.api.deps import DB, CurrentUser

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, db: DB) -> dict:
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")

    user = User(email=body.email, hashed_password=hash_password(body.password))
    db.add(user)
    await db.flush()
    return {"user_id": str(user.id)}


@router.post("/login")
async def login(body: LoginRequest, db: DB) -> TokenResponse:
    result = await db.execute(select(User).where(User.email == body.email, User.deleted_at.is_(None)))
    user = result.scalar_one_or_none()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    settings = get_settings()
    access = create_access_token(str(user.id))
    refresh = create_refresh_token()

    db.add(RefreshToken(
        user_id=user.id,
        token_hash=_hash_token(refresh),
        family_id=uuid.uuid4(),
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days),
    ))
    return TokenResponse(access_token=access, refresh_token=refresh)


@router.post("/refresh")
async def refresh(body: RefreshRequest, db: DB) -> TokenResponse:
    token_hash = _hash_token(body.refresh_token)
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.used_at.is_(None),
        )
    )
    rt = result.scalar_one_or_none()
    if not rt or rt.expires_at < datetime.now(timezone.utc):
        if rt:
            # Token reuse detected — invalidate entire family
            family_tokens = await db.execute(
                select(RefreshToken).where(RefreshToken.family_id == rt.family_id)
            )
            for t in family_tokens.scalars():
                t.used_at = datetime.now(timezone.utc)
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    rt.used_at = datetime.now(timezone.utc)

    settings = get_settings()
    new_refresh = create_refresh_token()
    db.add(RefreshToken(
        user_id=rt.user_id,
        token_hash=_hash_token(new_refresh),
        family_id=rt.family_id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days),
    ))
    return TokenResponse(access_token=create_access_token(str(rt.user_id)), refresh_token=new_refresh)


@router.get("/me")
async def me(current_user: CurrentUser) -> dict:
    return {"user_id": str(current_user.id), "email": current_user.email}
