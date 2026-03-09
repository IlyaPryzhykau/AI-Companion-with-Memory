"""Chat-related request and response schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ChatRequest(BaseModel):
    """Incoming user message payload."""

    chat_id: int | None = Field(default=None)
    message: str = Field(min_length=1, max_length=8000)


class ChatResponse(BaseModel):
    """Assistant response payload."""

    chat_id: int
    user_message_id: int
    assistant_message_id: int
    response: str


class MessageResponse(BaseModel):
    """Public message payload."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    chat_id: int
    role: str
    content: str
    created_at: datetime
