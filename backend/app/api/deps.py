import hashlib
from datetime import datetime, timezone
from typing import Annotated
import uuid

from fastapi import Depends, HTTPException, status, Cookie
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import decode_access_token
from app.db.models import User, Clone
from app.db.session import get_db

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    token = credentials.credentials if credentials else None
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    user_id = decode_access_token(token)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    result = await db.execute(
        select(User).where(User.id == uuid.UUID(user_id), User.deleted_at.is_(None))
    )
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
DB = Annotated[AsyncSession, Depends(get_db)]


async def get_user_clone(
    clone_id: uuid.UUID,
    current_user: CurrentUser,
    db: DB,
) -> Clone:
    result = await db.execute(
        select(Clone).where(
            Clone.id == clone_id,
            Clone.deleted_at.is_(None),
        )
    )
    clone = result.scalar_one_or_none()
    if clone is None or clone.user_id != current_user.id:
        # Return 403 for cross-user, 404 for own deleted — both look the same to prevent enumeration
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN if clone and clone.user_id != current_user.id else status.HTTP_404_NOT_FOUND,
            detail="Clone not found",
        )
    return clone
