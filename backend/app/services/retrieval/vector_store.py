from typing import Optional
import uuid
from sqlalchemy import select, delete, text
from sqlalchemy.ext.asyncio import AsyncSession
from pgvector.sqlalchemy import Vector

from app.db.models import Chunk


async def upsert_chunks(db: AsyncSession, chunks: list[dict]) -> None:
    for c in chunks:
        existing = await db.execute(
            select(Chunk).where(Chunk.id == uuid.UUID(c["id"]))
        )
        row = existing.scalar_one_or_none()
        if row:
            row.embedding = c.get("embedding")
            row.micro_summary = c.get("micro_summary")
            row.keywords = c.get("keywords")
        else:
            db.add(Chunk(**{k: v for k, v in c.items()}))
    await db.flush()


async def similarity_search(
    db: AsyncSession,
    clone_id: uuid.UUID,
    query_embedding: list[float],
    top_k: int = 100,
) -> list[dict]:
    # Use pgvector cosine similarity
    result = await db.execute(
        select(Chunk, (1 - Chunk.embedding.cosine_distance(query_embedding)).label("score"))
        .where(Chunk.clone_id == clone_id, Chunk.embedding.isnot(None))
        .order_by(Chunk.embedding.cosine_distance(query_embedding))
        .limit(top_k)
    )
    return [
        {"chunk_id": str(row.Chunk.id), "content": row.Chunk.content, "score": float(row.score),
         "source_type": row.Chunk.source_type, "document_id": str(row.Chunk.document_id)}
        for row in result.all()
    ]


async def delete_namespace(db: AsyncSession, clone_id: uuid.UUID) -> None:
    await db.execute(delete(Chunk).where(Chunk.clone_id == clone_id))
    await db.flush()
