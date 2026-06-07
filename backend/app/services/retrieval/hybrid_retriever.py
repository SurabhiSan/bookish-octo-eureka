import uuid
from typing import Optional, List, Dict
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.services.retrieval.bm25_index import bm25_search
from app.services.retrieval.vector_store import similarity_search
from app.services.ingestion.embedder import embed_texts


def _rrf_fuse(bm25_results: List[Dict], dense_results: List[Dict], k: int = 60) -> List[Dict]:
    scores: Dict[str, float] = {}
    for rank, r in enumerate(bm25_results):
        cid = r["chunk_id"]
        scores[cid] = scores.get(cid, 0) + 1 / (k + rank + 1)
    for rank, r in enumerate(dense_results):
        cid = r["chunk_id"]
        scores[cid] = scores.get(cid, 0) + 1 / (k + rank + 1)
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [{"chunk_id": cid, "rrf_score": score} for cid, score in ranked]


async def _hyde_expand(query: str) -> Optional[str]:
    settings = get_settings()
    api_key = settings.openrouter_api_key or settings.anthropic_api_key
    if not api_key or len(query.split()) <= 15:
        return None
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=api_key, base_url=settings.openrouter_base_url)
        response = await client.chat.completions.create(
            model="meta-llama/llama-3.2-3b-instruct:free",
            max_tokens=150,
            messages=[{"role": "user", "content": f"Write a short paragraph (2-3 sentences) that directly addresses: {query}"}],
        )
        return response.choices[0].message.content
    except Exception:
        return None


async def _rerank(query: str, chunks: List[Dict], top_k: int = 8) -> List[Dict]:
    settings = get_settings()
    if not settings.cohere_api_key or not chunks:
        return chunks[:top_k]
    try:
        import cohere, asyncio
        co = cohere.Client(settings.cohere_api_key)
        docs = [c.get("content", "") for c in chunks]
        loop = asyncio.get_event_loop()
        response = await asyncio.wait_for(
            loop.run_in_executor(None, lambda: co.rerank(model="rerank-english-v3.0", query=query, documents=docs, top_n=top_k)),
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


def _lost_in_middle_order(chunks: List[Dict]) -> List[Dict]:
    if len(chunks) <= 3:
        return chunks
    top_half = chunks[: len(chunks) // 2]
    bottom_half = chunks[len(chunks) // 2:]
    return top_half[:2] + bottom_half + top_half[2:]


async def retrieve(db: AsyncSession, clone_id: uuid.UUID, persona_namespace: str, query: str) -> List[Dict]:
    try:
        hypothetical = await _hyde_expand(query)
        embed_query = hypothetical or query
        embeddings = await embed_texts([embed_query])
        query_vec = embeddings[0]

        # Skip vector search if embedding is zero (no OpenAI key)
        is_zero = all(v == 0.0 for v in query_vec)

        bm25_results = bm25_search(persona_namespace, query, top_k=100)
        dense_results = [] if is_zero else await similarity_search(db, clone_id, query_vec, top_k=100)

        dense_map = {r["chunk_id"]: r for r in dense_results}
        fused = _rrf_fuse(bm25_results, dense_results)

        enriched = []
        for r in fused:
            if r["chunk_id"] in dense_map:
                item = dense_map[r["chunk_id"]].copy()
                item["rrf_score"] = r["rrf_score"]
                enriched.append(item)
            else:
                enriched.append(r)

        top = await _rerank(query, enriched[:120])
        return _lost_in_middle_order(top)
    except Exception:
        return []
