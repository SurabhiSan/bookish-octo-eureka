import asyncio
import json
import re
from typing import List, Dict

from app.core.config import get_settings


async def enrich_chunks(chunks: List[Dict]) -> List[Dict]:
    """Add micro_summary and keywords via OpenRouter (Claude Haiku)."""
    settings = get_settings()
    api_key = settings.openrouter_api_key or settings.anthropic_api_key

    if not api_key:
        for c in chunks:
            c["micro_summary"] = c["content"][:200]
            c["keywords"] = []
        return chunks

    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=api_key, base_url=settings.openrouter_base_url)

    async def enrich_one(chunk: Dict) -> Dict:
        try:
            response = await client.chat.completions.create(
                model="meta-llama/llama-3.2-3b-instruct:free",
                max_tokens=200,
                messages=[{
                    "role": "user",
                    "content": (
                        f"Extract a 2-sentence summary and 3 keywords from this text.\n"
                        f"Return JSON: {{\"summary\": \"...\", \"keywords\": [\"...\", \"...\", \"...\"]}}\n\n"
                        f"Text:\n{chunk['content'][:2000]}"
                    ),
                }],
            )
            text = response.choices[0].message.content or ""
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                parsed = json.loads(match.group())
                chunk["micro_summary"] = parsed.get("summary", chunk["content"][:200])
                chunk["keywords"] = parsed.get("keywords", [])
        except Exception:
            chunk["micro_summary"] = chunk["content"][:200]
            chunk["keywords"] = []
        return chunk

    return list(await asyncio.gather(*[enrich_one(c) for c in chunks]))


async def embed_texts(texts: List[str]) -> List[List[float]]:
    """Zero-vector fallback — real embeddings need an OpenAI key."""
    settings = get_settings()
    if not settings.openai_api_key:
        return [[0.0] * 512 for _ in texts]

    import openai
    client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
    results = []
    for i in range(0, len(texts), 50):
        batch = texts[i: i + 50]
        response = await client.embeddings.create(
            model="text-embedding-3-large",
            input=batch,
            dimensions=512,
        )
        results.extend([e.embedding for e in response.data])
    return results
