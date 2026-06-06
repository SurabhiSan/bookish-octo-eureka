import json
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Clone, Message
from app.services.persona.chronicle import get_cached_chronicle, chronicle_to_text, Chronicle
from app.services.retrieval.hybrid_retriever import retrieve
from app.core.config import get_settings


async def stream_conversation_turn(
    clone: Clone,
    user_message: str,
    history: list[Message],
    db: AsyncSession,
) -> AsyncIterator[dict]:
    settings = get_settings()

    # ── Zone 1: Identity Anchor ──────────────────────────────────────────
    cached = get_cached_chronicle(clone.vector_namespace)
    if cached:
        anchor_text = cached.decode() if isinstance(cached, bytes) else cached
    elif clone.identity_anchor:
        from app.services.persona.chronicle import Chronicle
        chronicle = Chronicle(**clone.identity_anchor)
        anchor_text = chronicle_to_text(chronicle)
    else:
        anchor_text = f"You are simulating {clone.name}. {clone.description or ''}"

    # ── Zone 2: Retrieved Context ────────────────────────────────────────
    retrieved = await retrieve(db, clone.id, clone.vector_namespace, user_message)
    chunk_ids = [r.get("chunk_id", "") for r in retrieved if r.get("chunk_id")]

    context_parts = []
    for r in retrieved[:8]:
        content = r.get("content", "")
        source = r.get("source_type", "")
        if content:
            context_parts.append(f"[{source}]: {content}")
    context_block = "\n\n".join(context_parts)

    # ── Zone 3: Conversation History ─────────────────────────────────────
    history_messages = []
    for msg in history[-15:]:  # last 15 turns
        history_messages.append({"role": msg.role, "content": msg.content})

    # Check if anchor re-injection is needed (every 8 turns)
    turn_count = len([m for m in history if m.role == "assistant"])
    needs_reinjection = turn_count > 0 and turn_count % 8 == 0

    # ── Assemble Prompt ──────────────────────────────────────────────────
    system_prompt = (
        f"{anchor_text}\n\n"
        f"## Retrieved Memory\n"
        f"<retrieved_context>\n{context_block}\n</retrieved_context>\n\n"
        f"Respond as {clone.name} based on the above identity and retrieved memory. "
        f"Stay in character. If asked about something not in your memory, acknowledge uncertainty honestly."
    )

    if needs_reinjection:
        system_prompt = f"[Identity anchor re-injection]\n{anchor_text}\n\n" + system_prompt

    if not settings.anthropic_api_key:
        yield {"type": "sources", "chunk_ids": chunk_ids}
        yield {"type": "token", "text": f"[{clone.name}] I don't have an API key configured yet."}
        return

    # ── Stream from Claude ───────────────────────────────────────────────
    import anthropic
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    yield {"type": "sources", "chunk_ids": chunk_ids}

    messages = history_messages + [{"role": "user", "content": user_message}]

    async with client.messages.stream(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        system=system_prompt,
        messages=messages,
    ) as stream:
        async for text in stream.text_stream:
            yield {"type": "token", "text": text}
