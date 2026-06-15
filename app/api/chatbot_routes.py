"""
Chatbot API Routes.

Handles natural language prompt queries from the frontend client.
"""

from typing import List, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from pydantic import BaseModel

from app.auth.dependencies import get_current_user
from app.services.chatbot_service import handle_chatbot_chat

router = APIRouter(prefix="/chatbot", tags=["Chatbot"])


class ChatMessageSchema(BaseModel):
    role: str
    content: str


class ChatRequestSchema(BaseModel):
    message: str
    conversation_history: Optional[List[ChatMessageSchema]] = None


@router.post("/chat", summary="Send a message to Elly")
async def chat_with_elly(
    data: ChatRequestSchema,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
):
    """
    Process a prompt from the user. Interprets the request using Groq
    and invokes corresponding outreach platform automation tools.
    """
    try:
        history = []
        if data.conversation_history:
            history = [{"role": m.role, "content": m.content} for m in data.conversation_history]

        result = await handle_chatbot_chat(
            user_id=current_user["id"],
            message=data.message,
            conversation_history=history,
            background_tasks=background_tasks
        )
        return result
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Chatbot failed to process message: {exc}"
        )