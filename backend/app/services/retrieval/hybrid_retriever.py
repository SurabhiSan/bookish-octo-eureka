import uuid
from typing import Optional
import anthropic
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.services.retrieval.bm25_index import bm25_search
from app.services.retrieval.vector_store import similarity_search
from app.services.ingestion.embedder import embed_texts


def _rrf_fuse(bm25_results: list[dict], dense_results: list[dict], k: int = 60) -> list[dict]:
    scores: dict[str, float] = {}
    for rank, r in enumerate(bm25_results):
        cid = r["chunk_id"]
        scores[cid] = scores.get(cid, 0) + 1 / (k + rank + 1)
    for rank, r in enumerate(dense_results):
        cid = r["chunk_id"]
        scores[cid] = scores.get(cid, 0) + 1 / (k + rank + 1)
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [{"chunk_id": cid, "rrf_score": score} for cid, score in ranked]


async def _hyde_expand(query: str) -> Optional[str]:
    """Generate a hypothetical paragraph using Claude Haiku for HyDE."""
    settings = get_settings()
    if not settings.anthropic_api_key or len(query.split()) <= 15:
        return None
    try:
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        response = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=150,
            messages=[{
                "role": "user",
                "content": f"Write a short paragraph (2-3 sentences) that directly addresses: {query}",
            }],
        )
        return response.content[0].text
    except Exception:
        return None


async def _rerank(query: str, chunks: list[dict], top_k: int = 8) -> list[dict]:
    """Rerank with Cohere Rerank 4 Pro; fallback to RRF order."""
    settings = get_settings()
    if not settings.cohere_api_key or not chunks:
        return chunks[:top_k]
    try:
        import cohere, asyncio
        co = cohere.Client(settings.cohere_api_key)
        docs = [c.get("content", "") for c in chunks]
        loop = asyncio.get_event_loop()
        response = await asyncio.wait_for(
            loop.run_in_executor(
                None,
                lambda: co.rerank(model="rerank-english-v3.0", query=query, documents=docs, top_n=top_k),
            ),
            timeout=2.0,
        )
        reranked = []
        for r in response.results:
            chunk = chunks[r.index].copy()
            chunk["rerank_score"] = r.relevance_score
            reranked.append(chunk)
        return reranked
    except Exception:
        return chunks[:top_k]


def _lost_in_middle_order(chunks: list[dict]) -> list[dict]:
    """Position most relevant chunks at start and end."""
    if len(chunks) <= 3:
        return chunks
    top_half = chunks[: len(chunks) // 2]
    bottom_half = chunks[len(chunks) // 2 :]
    return top_half[:2] + bottom_half + top_half[2:]


async def retrieve(
    db: AsyncSession,
    clone_id: uuid.UUID,
    persona_namespace: str,
    query: str,
) -> list[dict]:
    # HyDE query expansion
    hypothetical = await _hyde_expand(query)
    embed_query = hypothetical or query
    embeddings = await embed_texts([embed_query])
    query_vec = embeddings[0]

    # BM25 + dense
    bm25_results = bm25_search(persona_namespace, query, top_k=100)
    dense_results = await similarity_search(db, clone_id, query_vec, top_k=100)

    # Build content map for dense results
    dense_map = {r["chunk_id"]: r for r in dense_results}

    # RRF fusion
    fused = _rrf_fuse(bm25_results, dense_results)

    # Enrich fused results with content from dense map
    enriched = []
    for r in fused:
        if r["chunk_id"] in dense_map:
            item = dense_map[r["chunk_id"]].copy()
            item["rrf_score"] = r["rrf_score"]
            enriched.append(item)
        else:
            enriched.append(r)

    # Rerank top results
    top = await _rerank(query, enriched[:120])

    return _lost_in_middle_order(top)
