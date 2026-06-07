import json
import uuid
from typing import Optional, AsyncIterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select

from app.db.models import Conversation, Message
from app.api.deps import DB, CurrentUser, get_user_clone

router = APIRouter(prefix="/conversations", tags=["conversations"])


class CreateConversation(BaseModel):
    clone_id: str
    title: Optional[str] = None


class ConversationResponse(BaseModel):
    id: str
    clone_id: str
    title: Optional[str]
    created_at: str

    @classmethod
    def from_orm(cls, c: Conversation) -> "ConversationResponse":
        return cls(
            id=str(c.id),
            clone_id=str(c.clone_id),
            title=c.title,
            created_at=c.created_at.isoformat(),
        )


class SendMessage(BaseModel):
    content: str


@router.post("", status_code=201)
async def create_conversation(body: CreateConversation, current_user: CurrentUser, db: DB) -> ConversationResponse:
    clone = await get_user_clone(uuid.UUID(body.clone_id), current_user, db)
    conv = Conversation(clone_id=clone.id, user_id=current_user.id, title=body.title)
    db.add(conv)
    await db.flush()
    return ConversationResponse.from_orm(conv)


@router.get("")
async def list_conversations(current_user: CurrentUser, db: DB, clone_id: Optional[str] = None) -> list[ConversationResponse]:
    q = select(Conversation).where(Conversation.user_id == current_user.id)
    if clone_id:
        q = q.where(Conversation.clone_id == uuid.UUID(clone_id))
    result = await db.execute(q)
    return [ConversationResponse.from_orm(c) for c in result.scalars()]


@router.get("/{conversation_id}/messages")
async def get_messages(conversation_id: uuid.UUID, current_user: CurrentUser, db: DB) -> list[dict]:
    result = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id, Conversation.user_id == current_user.id)
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    msgs = await db.execute(
        select(Message).where(Message.conversation_id == conversation_id).order_by(Message.created_at)
    )
    return [
        {"id": str(m.id), "role": m.role, "content": m.content, "created_at": m.created_at.isoformat()}
        for m in msgs.scalars()
    ]


@router.post("/{conversation_id}/messages")
async def send_message(
    conversation_id: uuid.UUID,
    body: SendMessage,
    current_user: CurrentUser,
    db: DB,
) -> StreamingResponse:
    result = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id, Conversation.user_id == current_user.id)
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Fetch clone for namespace
    from app.db.models import Clone
    clone_result = await db.execute(select(Clone).where(Clone.id == conv.clone_id))
    clone = clone_result.scalar_one_or_none()

    # Load history
    history_result = await db.execute(
        select(Message).where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
        .limit(30)
    )
    history = list(history_result.scalars())

    async def generate() -> AsyncIterator[str]:
        from app.services.persona.conversation import stream_conversation_turn
        full_response = ""
        retrieved_chunk_ids = []

        async for chunk_data in stream_conversation_turn(
            clone=clone,
            user_message=body.content,
            history=history,
            db=db,
        ):
            if chunk_data["type"] == "token":
                token = chunk_data["text"]
                full_response += token
                yield f"data: {json.dumps({'type': 'token', 'text': token})}\n\n"
            elif chunk_data["type"] == "sources":
                retrieved_chunk_ids = chunk_data["chunk_ids"]
                yield f"data: {json.dumps({'type': 'sources', 'chunk_ids': retrieved_chunk_ids})}\n\n"

        yield "data: [DONE]\n\n"

        # Persist while the session is still open
        await _persist_turn(
            db=db,
            conversation_id=conversation_id,
            clone=clone,
            user_content=body.content,
            assistant_content=full_response,
            retrieved_chunk_ids=retrieved_chunk_ids,
            history=history,
        )

    return StreamingResponse(generate(), media_type="text/event-stream")


async def _persist_turn(db, conversation_id, clone, user_content, assistant_content, retrieved_chunk_ids, history):
    try:
        user_msg = Message(
            conversation_id=conversation_id,
            role="user",
            content=user_content,
        )
        assistant_msg = Message(
            conversation_id=conversation_id,
            role="assistant",
            content=assistant_content,
            retrieved_chunk_ids=retrieved_chunk_ids,
        )
        db.add(user_msg)
        db.add(assistant_msg)
        await db.commit()
    except Exception:
        pass  # Best-effort; stream already completed
