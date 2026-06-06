import json
import pickle
from typing import Optional

import redis as redis_lib
from rank_bm25 import BM25Okapi

from app.core.config import get_settings

_redis: Optional[redis_lib.Redis] = None


def _get_redis() -> redis_lib.Redis:
    global _redis
    if _redis is None:
        settings = get_settings()
        _redis = redis_lib.from_url(settings.redis_url)
    return _redis


def _key(persona_namespace: str) -> str:
    return f"bm25:{persona_namespace}"


def rebuild_bm25_index(persona_namespace: str, chunks: list[dict]) -> None:
    if not chunks:
        return
    corpus = [c["content"].lower().split() for c in chunks]
    chunk_ids = [c["id"] for c in chunks]
    index = BM25Okapi(corpus)
    payload = pickle.dumps({"index": index, "chunk_ids": chunk_ids})
    _get_redis().set(_key(persona_namespace), payload)


def bm25_search(persona_namespace: str, query: str, top_k: int = 100) -> list[dict]:
    raw = _get_redis().get(_key(persona_namespace))
    if not raw:
        return []
    data = pickle.loads(raw)
    index: BM25Okapi = data["index"]
    chunk_ids: list[str] = data["chunk_ids"]
    tokens = query.lower().split()
    scores = index.get_scores(tokens)
    ranked = sorted(zip(scores, chunk_ids), reverse=True)[:top_k]
    return [{"chunk_id": cid, "score": float(score)} for score, cid in ranked if score > 0]


def delete_bm25_index(persona_namespace: str) -> None:
    _get_redis().delete(_key(persona_namespace))
