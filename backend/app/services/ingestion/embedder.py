import asyncio
from typing import Optional
import anthropic
import openai
from app.core.config import get_settings


async def enrich_chunks(chunks: list[dict]) -> list[dict]:
    """Add micro_summary and keywords to chunks via Claude Haiku."""
    settings = get_settings()
    if not settings.anthropic_api_key:
        for c in chunks:
            c["micro_summary"] = c["content"][:200]
            c["keywords"] = []
        return chunks

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def enrich_one(chunk: dict) -> dict:
        try:
            response = await client.messages.create(
                model="claude-haiku-4-5-20251001",
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
            import json, re
            text = response.content[0].text
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                parsed = json.loads(match.group())
                chunk["micro_summary"] = parsed.get("summary", chunk["content"][:200])
                chunk["keywords"] = parsed.get("keywords", [])
        except Exception:
            chunk["micro_summary"] = chunk["content"][:200]
            chunk["keywords"] = []
        return chunk

    return await asyncio.gather(*[enrich_one(c) for c in chunks])


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a list of texts using OpenAI text-embedding-3-large at 512d."""
    settings = get_settings()
    if not settings.openai_api_key:
        return [[0.0] * 512 for _ in texts]

    client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
    results = []

    # Batch in groups of 50
    for i in range(0, len(texts), 50):
        batch = texts[i: i + 50]
        response = await client.embeddings.create(
            model="text-embedding-3-large",
            input=batch,
            dimensions=512,
        )
        results.extend([e.embedding for e in response.data])

    return results
