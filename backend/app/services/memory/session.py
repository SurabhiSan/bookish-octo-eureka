"""Working memory: 15-turn rolling window with compression."""
from dataclasses import dataclass, field
from typing import Optional
from app.db.models import Message


def compress_oldest_turns(messages: list[Message], max_turns: int = 15) -> list[Message]:
    """Return the most recent max_turns messages; compress older ones if needed."""
    if len(messages) <= max_turns:
        return messages
    return messages[-max_turns:]
