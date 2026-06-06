"""Cross-session episodic memory via Mem0 (self-hosted)."""
from typing import Optional
from app.core.config import get_settings

_mem0_client = None


def _get_client():
    global _mem0_client
    if _mem0_client is None:
        try:
            from mem0 import MemoryClient
            _mem0_client = MemoryClient()
        except Exception:
            _mem0_client = None
    return _mem0_client


async def load_episodic_memories(persona_id: str, user_id: str, query: str) -> list[str]:
    client = _get_client()
    if not client:
        return []
    try:
        results = client.search(query=query, user_id=f"{persona_id}:{user_id}", limit=5)
        return [r["memory"] for r in results if r.get("memory")]
    except Exception:
        return []


async def store_episodic_memory(persona_id: str, user_id: str, content: str) -> None:
    client = _get_client()
    if not client:
        return
    try:
        client.add(content, user_id=f"{persona_id}:{user_id}")
    except Exception:
        pass


async def delete_episodic_memories(persona_id: str) -> None:
    client = _get_client()
    if not client:
        return
    try:
        client.delete_all(user_id=persona_id)
    except Exception:
        pass
