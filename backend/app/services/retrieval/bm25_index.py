import pickle
from typing import Optional

from rank_bm25 import BM25Okapi
from app.core.config import get_settings

_redis = None


def _get_redis():
    global _redis
    if _redis is None:
        try:
            import redis as redis_lib
            r = redis_lib.from_url(get_settings().redis_url, socket_connect_timeout=1)
            r.ping()
            _redis = r
        except Exception:
            pass
    return _redis


def _key(persona_namespace: str) -> str:
    return f"bm25:{persona_namespace}"


def rebuild_bm25_index(persona_namespace: str, chunks: list) -> None:
    r = _get_redis()
    if not r or not chunks:
        return
    try:
        corpus = [c["content"].lower().split() for c in chunks]
        chunk_ids = [c["id"] for c in chunks]
        index = BM25Okapi(corpus)
        r.set(_key(persona_namespace), pickle.dumps({"index": index, "chunk_ids": chunk_ids}))
    except Exception:
        pass


def bm25_search(persona_namespace: str, query: str, top_k: int = 100) -> list:
    r = _get_redis()
    if not r:
        return []
    try:
        raw = r.get(_key(persona_namespace))
        if not raw:
            return []
        data = pickle.loads(raw)
        tokens = query.lower().split()
        scores = data["index"].get_scores(tokens)
        ranked = sorted(zip(scores, data["chunk_ids"]), reverse=True)[:top_k]
        return [{"chunk_id": cid, "score": float(s)} for s, cid in ranked if s > 0]
    except Exception:
        return []


def delete_bm25_index(persona_namespace: str) -> None:
    r = _get_redis()
    if not r:
        return
    try:
        r.delete(_key(persona_namespace))
    except Exception:
        pass
