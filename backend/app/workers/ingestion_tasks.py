import uuid
from celery import Celery
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings

settings = get_settings()
celery_app = Celery("ai_clone", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.task_serializer = "json"

# Sync engine for Celery workers
_sync_url = settings.database_url.replace("+asyncpg", "+psycopg2")
_engine = create_engine(_sync_url, pool_pre_ping=True)
SyncSession = sessionmaker(_engine)


def _get_clone_sync(session, clone_id_str: str):
    from app.db.models import Clone
    return session.query(Clone).filter_by(id=uuid.UUID(clone_id_str)).first()


def _get_doc_sync(session, doc_id_str: str):
    from app.db.models import Document
    return session.query(Document).filter_by(id=uuid.UUID(doc_id_str)).first()


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def ingest_document_task(self, document_id: str):
    from app.db.models import Document, Chunk, Clone
    from app.services.ingestion.storage import download_from_r2
    from app.services.ingestion.parser import parse_document
    from app.services.ingestion.chunker import chunk_document
    from app.services.ingestion.embedder import enrich_chunks, embed_texts
    from app.services.retrieval.bm25_index import rebuild_bm25_index
    import asyncio

    with SyncSession() as session:
        doc = session.query(Document).filter_by(id=uuid.UUID(document_id)).first()
        if not doc:
            return
        clone = session.query(Clone).filter_by(id=doc.clone_id).first()
        if not clone:
            return

        try:
            doc.status = "processing"
            doc.progress_detail = "Downloading"
            session.commit()

            # Parse
            content = download_from_r2(doc.r2_key)
            text = parse_document(doc.filename, content)
            doc.progress_detail = "Chunking"
            session.commit()

            # Chunk
            raw_chunks = chunk_document(text, doc.source_type)

            # Build chunk dicts
            chunk_dicts = [
                {
                    "id": str(uuid.uuid4()),
                    "document_id": str(doc.id),
                    "clone_id": str(clone.id),
                    "chunk_index": c.chunk_index,
                    "parent_chunk_id": None,
                    "content": c.content,
                    "source_type": doc.source_type,
                }
                for c in raw_chunks
            ]

            doc.progress_detail = "Enriching"
            session.commit()

            # Enrich with micro-summaries (async in sync context)
            enriched = asyncio.run(enrich_chunks(chunk_dicts))

            doc.progress_detail = "Embedding"
            session.commit()

            # Embed
            texts = [c.get("micro_summary") or c["content"] for c in enriched]
            embeddings = asyncio.run(embed_texts(texts))

            # Store chunks
            db_chunks = []
            for i, (c, emb) in enumerate(zip(enriched, embeddings)):
                db_chunk = Chunk(
                    id=uuid.UUID(c["id"]),
                    document_id=uuid.UUID(c["document_id"]),
                    clone_id=uuid.UUID(c["clone_id"]),
                    chunk_index=c["chunk_index"],
                    content=c["content"],
                    micro_summary=c.get("micro_summary"),
                    keywords=c.get("keywords"),
                    embedding=emb,
                    source_type=c["source_type"],
                )
                session.add(db_chunk)
                db_chunks.append(c)

            session.flush()

            # Rebuild BM25
            doc.progress_detail = "Indexing"
            session.commit()
            all_chunks = session.query(Chunk).filter_by(clone_id=clone.id).all()
            rebuild_bm25_index(clone.vector_namespace, [
                {"id": str(c.id), "content": c.content} for c in all_chunks
            ])

            # Check Chronicle rebuild (10% growth)
            old_count = clone.chunk_count or 0
            new_count = len(all_chunks)
            clone.chunk_count = new_count

            doc.status = "indexed"
            doc.chunk_count = len(raw_chunks)
            doc.progress_detail = None
            session.commit()

            if old_count == 0 or (new_count - old_count) / old_count >= 0.10:
                rebuild_chronicle_task.delay(str(clone.id))

        except Exception as exc:
            doc.status = "failed"
            doc.error = str(exc)
            session.commit()
            raise self.retry(exc=exc)


@celery_app.task
def rebuild_chronicle_task(clone_id: str):
    from app.db.models import Clone, Chunk
    from app.services.persona.chronicle import build_chronicle, chronicle_to_text, set_cached_chronicle
    import asyncio

    with SyncSession() as session:
        clone = session.query(Clone).filter_by(id=uuid.UUID(clone_id)).first()
        if not clone:
            return

        # Run async build_chronicle in sync context
        from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
        async_engine = create_async_engine(settings.database_url)
        factory = async_sessionmaker(async_engine, expire_on_commit=False)

        async def _build():
            async with factory() as async_db:
                from app.db.models import Clone as AsyncClone
                from sqlalchemy import select
                result = await async_db.execute(select(AsyncClone).where(AsyncClone.id == uuid.UUID(clone_id)))
                async_clone = result.scalar_one_or_none()
                if async_clone:
                    chronicle = await build_chronicle(async_db, async_clone)
                    text = chronicle_to_text(chronicle)
                    set_cached_chronicle(async_clone.vector_namespace, text)
                    async_clone.identity_anchor = chronicle.model_dump()
                    await async_db.commit()

        asyncio.run(_build())


@celery_app.task
def cleanup_persona_task(clone_id: str, vector_namespace: str):
    from app.db.models import Clone, Chunk, Document
    from app.services.retrieval.bm25_index import delete_bm25_index
    from app.services.persona.chronicle import delete_chronicle_cache

    with SyncSession() as session:
        # Delete all chunks (vectors)
        session.query(Chunk).filter_by(clone_id=uuid.UUID(clone_id)).delete()
        # Delete all documents
        session.query(Document).filter_by(clone_id=uuid.UUID(clone_id)).delete()
        session.commit()

    delete_bm25_index(vector_namespace)
    delete_chronicle_cache(vector_namespace)


@celery_app.task
def cleanup_document_task(document_id: str, clone_id: str, r2_key: str):
    from app.db.models import Chunk, Clone
    from app.services.ingestion.storage import delete_from_r2
    from app.services.retrieval.bm25_index import rebuild_bm25_index

    with SyncSession() as session:
        session.query(Chunk).filter_by(document_id=uuid.UUID(document_id)).delete()
        session.commit()

        # Rebuild BM25 after deletion for GDPR erasure completeness
        all_chunks = session.query(Chunk).filter_by(clone_id=uuid.UUID(clone_id)).all()
        clone = session.query(Clone).filter_by(id=uuid.UUID(clone_id)).first()
        if clone:
            rebuild_bm25_index(clone.vector_namespace, [
                {"id": str(c.id), "content": c.content} for c in all_chunks
            ])

    delete_from_r2(r2_key)
