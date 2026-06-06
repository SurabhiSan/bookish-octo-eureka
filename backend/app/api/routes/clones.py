import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Clone
from app.api.deps import DB, CurrentUser, get_user_clone

router = APIRouter(prefix="/clones", tags=["clones"])


class CloneCreate(BaseModel):
    name: str
    description: Optional[str] = None
    avatar_url: Optional[str] = None


class CloneUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    avatar_url: Optional[str] = None


class CloneResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    avatar_url: Optional[str]
    vector_namespace: str
    chunk_count: int
    identity_anchor: Optional[dict]
    created_at: str
    updated_at: str

    @classmethod
    def from_orm(cls, c: Clone) -> "CloneResponse":
        return cls(
            id=str(c.id),
            name=c.name,
            description=c.description,
            avatar_url=c.avatar_url,
            vector_namespace=c.vector_namespace,
            chunk_count=c.chunk_count,
            identity_anchor=c.identity_anchor,
            created_at=c.created_at.isoformat(),
            updated_at=c.updated_at.isoformat(),
        )


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_clone(body: CloneCreate, current_user: CurrentUser, db: DB) -> CloneResponse:
    if not body.name.strip():
        raise HTTPException(status_code=422, detail="name cannot be empty")

    ns = f"persona_{uuid.uuid4().hex}"
    clone = Clone(
        user_id=current_user.id,
        name=body.name.strip(),
        description=body.description,
        avatar_url=body.avatar_url,
        vector_namespace=ns,
    )
    db.add(clone)
    await db.flush()
    return CloneResponse.from_orm(clone)


@router.get("")
async def list_clones(current_user: CurrentUser, db: DB) -> list[CloneResponse]:
    result = await db.execute(
        select(Clone).where(Clone.user_id == current_user.id, Clone.deleted_at.is_(None))
    )
    return [CloneResponse.from_orm(c) for c in result.scalars()]


@router.get("/{clone_id}")
async def get_clone(clone_id: uuid.UUID, current_user: CurrentUser, db: DB) -> CloneResponse:
    clone = await get_user_clone(clone_id, current_user, db)
    return CloneResponse.from_orm(clone)


@router.patch("/{clone_id}")
async def update_clone(clone_id: uuid.UUID, body: CloneUpdate, current_user: CurrentUser, db: DB) -> CloneResponse:
    clone = await get_user_clone(clone_id, current_user, db)
    if body.name is not None:
        if not body.name.strip():
            raise HTTPException(status_code=422, detail="name cannot be empty")
        clone.name = body.name.strip()
    if body.description is not None:
        clone.description = body.description
    if body.avatar_url is not None:
        clone.avatar_url = body.avatar_url
    clone.updated_at = datetime.now(timezone.utc)
    return CloneResponse.from_orm(clone)


@router.delete("/{clone_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_clone(clone_id: uuid.UUID, current_user: CurrentUser, db: DB) -> None:
    clone = await get_user_clone(clone_id, current_user, db)
    clone.deleted_at = datetime.now(timezone.utc)
    # Async cleanup is enqueued by the Celery worker
    from app.workers.ingestion_tasks import cleanup_persona_task
    cleanup_persona_task.delay(str(clone.id), str(clone.vector_namespace))
