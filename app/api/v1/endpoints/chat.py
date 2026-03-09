"""Chat API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps.auth import get_current_user
from app.db.session import get_db_session
from app.models.chat import Chat, Message
from app.models.user import User
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.llm import generate_assistant_reply

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
def send_chat_message(
    payload: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> ChatResponse:
    """Handle a chat turn and persist both user and assistant messages."""

    if payload.chat_id is None:
        chat = Chat(user_id=current_user.id, assistant_id="default")
        db.add(chat)
        db.flush()
    else:
        chat = db.execute(
            select(Chat).where(Chat.id == payload.chat_id, Chat.user_id == current_user.id)
        ).scalar_one_or_none()
        if chat is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chat not found.",
            )

    user_message = Message(chat_id=chat.id, role="user", content=payload.message.strip())
    db.add(user_message)

    assistant_text = generate_assistant_reply(payload.message)
    assistant_message = Message(chat_id=chat.id, role="assistant", content=assistant_text)
    db.add(assistant_message)

    db.commit()
    db.refresh(user_message)
    db.refresh(assistant_message)

    return ChatResponse(
        chat_id=chat.id,
        user_message_id=user_message.id,
        assistant_message_id=assistant_message.id,
        response=assistant_text,
    )
