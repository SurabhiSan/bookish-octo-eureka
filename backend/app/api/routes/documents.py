import uuid
from typing import Optional

import magic
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Document, SOURCE_TYPES
from app.api.deps import DB, CurrentUser, get_user_clone
from app.core.config import get_settings

router = APIRouter(prefix="/clones/{clone_id}/documents", tags=["documents"])

ALLOWED_MIME_PREFIXES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
    "text/markdown",
    "text/csv",
    "application/csv",
}

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md", ".csv"}

EXT_TO_EXPECTED_MIME = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument",
    ".txt": "text/",
    ".md": "text/",
    ".csv": "text/",
}


def validate_file_type(filename: str, first_bytes: bytes) -> None:
    import os
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")
    detected = magic.from_buffer(first_bytes, mime=True)
    expected_prefix = EXT_TO_EXPECTED_MIME.get(ext, "")
    if not detected.startswith(expected_prefix):
        raise HTTPException(status_code=400, detail=f"File content does not match extension {ext}")


class DocumentStatus(BaseModel):
    id: str
    filename: str
    source_type: str
    status: str
    progress_detail: Optional[str]
    chunk_count: int
    error: Optional[str]
    created_at: str

    @classmethod
    def from_orm(cls, d: Document) -> "DocumentStatus":
        return cls(
            id=str(d.id),
            filename=d.filename,
            source_type=d.source_type,
            status=d.status,
            progress_detail=d.progress_detail,
            chunk_count=d.chunk_count,
            error=d.error,
            created_at=d.created_at.isoformat(),
        )


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def upload_document(
    clone_id: uuid.UUID,
    source_type: str = Form(...),
    file: UploadFile = File(...),
    current_user: CurrentUser = None,
    db: DB = None,
) -> dict:
    if source_type not in SOURCE_TYPES:
        raise HTTPException(status_code=422, detail=f"source_type must be one of {SOURCE_TYPES}")

    settings = get_settings()
    max_bytes = settings.max_upload_size_mb * 1024 * 1024

    clone = await get_user_clone(clone_id, current_user, db)

    content = await file.read()
    if len(content) > max_bytes:
        raise HTTPException(status_code=413, detail=f"File exceeds {settings.max_upload_size_mb}MB limit")

    validate_file_type(file.filename or "upload.bin", content[:512])

    # Store to R2
    r2_key = f"{clone.vector_namespace}/{uuid.uuid4().hex}/{file.filename}"
    from app.services.ingestion.storage import upload_to_r2
    await upload_to_r2(r2_key, content)

    doc = Document(
        clone_id=clone.id,
        filename=file.filename or "upload",
        source_type=source_type,
        r2_key=r2_key,
        status="queued",
    )
    db.add(doc)
    await db.flush()

    from app.workers.ingestion_tasks import ingest_document_task
    doc_id = str(doc.id)
    try:
        task = ingest_document_task.delay(doc_id)
        doc.celery_task_id = task.id
    except Exception:
        # Redis/Celery unavailable — run ingestion in a background thread
        import threading
        threading.Thread(
            target=lambda: ingest_document_task.apply(args=[doc_id]),
            daemon=True,
        ).start()

    return {"document_id": doc_id, "status": "queued"}


@router.get("/{document_id}")
async def get_document_status(clone_id: uuid.UUID, document_id: uuid.UUID, current_user: CurrentUser, db: DB) -> DocumentStatus:
    await get_user_clone(clone_id, current_user, db)
    result = await db.execute(
        select(Document).where(Document.id == document_id, Document.deleted_at.is_(None))
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return DocumentStatus.from_orm(doc)


@router.get("")
async def list_documents(clone_id: uuid.UUID, current_user: CurrentUser, db: DB) -> list[DocumentStatus]:
    await get_user_clone(clone_id, current_user, db)
    result = await db.execute(
        select(Document).where(Document.clone_id == clone_id, Document.deleted_at.is_(None))
    )
    return [DocumentStatus.from_orm(d) for d in result.scalars()]


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(clone_id: uuid.UUID, document_id: uuid.UUID, current_user: CurrentUser, db: DB) -> None:
    clone = await get_user_clone(clone_id, current_user, db)
    result = await db.execute(
        select(Document).where(Document.id == document_id, Document.clone_id == clone.id, Document.deleted_at.is_(None))
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    from datetime import datetime, timezone
    doc.deleted_at = datetime.now(timezone.utc)

    from app.workers.ingestion_tasks import cleanup_document_task
    cleanup_document_task.delay(str(doc.id), str(clone.id), doc.r2_key)
