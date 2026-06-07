import json
import re
from typing import Optional, List

import redis as redis_lib
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import Clone, Chunk

_redis: Optional[redis_lib.Redis] = None


def _get_redis() -> Optional[redis_lib.Redis]:
    global _redis
    if _redis is None:
        try:
            _redis = redis_lib.from_url(get_settings().redis_url)
            _redis.ping()
        except Exception:
            _redis = None
    return _redis


class Chronicle(BaseModel):
    traits: List[str] = []
    beliefs: List[str] = []
    communication_style: dict = {}
    anti_patterns: List[str] = []
    confidence: str = "low"


def _cache_key(persona_namespace: str) -> str:
    return f"chronicle:{persona_namespace}"


def get_cached_chronicle(persona_namespace: str) -> Optional[str]:
    r = _get_redis()
    if r is None:
        return None
    try:
        return r.get(_cache_key(persona_namespace))
    except Exception:
        return None


def set_cached_chronicle(persona_namespace: str, text: str) -> None:
    r = _get_redis()
    if r is None:
        return
    try:
        r.setex(_cache_key(persona_namespace), 86400 * 7, text)
    except Exception:
        pass


def delete_chronicle_cache(persona_namespace: str) -> None:
    r = _get_redis()
    if r is None:
        return
    try:
        r.delete(_cache_key(persona_namespace))
    except Exception:
        pass


def chronicle_to_text(c: Chronicle) -> str:
    lines = ["## Identity Anchor\n"]
    if c.traits:
        lines.append("**Traits:** " + "; ".join(c.traits))
    if c.beliefs:
        lines.append("**Core beliefs:** " + "; ".join(c.beliefs))
    if c.communication_style:
        style_desc = ", ".join(f"{k}: {v}" for k, v in c.communication_style.items())
        lines.append(f"**Communication style:** {style_desc}")
    if c.anti_patterns:
        lines.append("**Does NOT:** " + "; ".join(c.anti_patterns))
    lines.append(f"\n*Corpus confidence: {c.confidence}*")
    return "\n".join(lines)


async def build_chronicle(db: AsyncSession, clone: Clone) -> Chronicle:
    settings = get_settings()

    result = await db.execute(
        select(Chunk).where(Chunk.clone_id == clone.id).order_by(Chunk.created_at.desc()).limit(40)
    )
    chunks = list(result.scalars())

    chunk_count = len(chunks)
    if chunk_count == 0:
        return Chronicle(confidence="low")

    confidence = "high" if chunk_count > 20 else ("medium" if chunk_count >= 5 else "low")

    api_key = settings.openrouter_api_key or settings.anthropic_api_key
    if not api_key:
        return Chronicle(confidence=confidence)

    sample_text = "\n\n---\n\n".join(c.content[:500] for c in chunks[:20])

    from openai import OpenAI
    client = OpenAI(api_key=api_key, base_url=settings.openrouter_base_url)
    response = client.chat.completions.create(
        model="nvidia/nemotron-3-super-120b-a12b:free",
        max_tokens=1000,
        messages=[{
            "role": "user",
            "content": (
                f"Analyze the following writing samples from one person and extract their identity profile.\n"
                f"Return JSON with keys: traits (3-5 strings), beliefs (3-5 strings), "
                f"communication_style (object with keys like vocabulary_level, hedging_register, humor), "
                f"anti_patterns (3-5 strings of things they never do/say).\n\n"
                f"Writing samples:\n{sample_text}"
            ),
        }],
    )

    try:
        text = response.choices[0].message.content or ""
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            data = json.loads(match.group())
            return Chronicle(confidence=confidence, **data)
    except Exception:
        pass

    return Chronicle(confidence=confidence)
