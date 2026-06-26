"""
Chat session API routes.

Manages Elly chat sessions with history persistence.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from pydantic import BaseModel

from app.auth.dependencies import get_current_user
from app.services.chat_session_service import (
    create_session,
    get_sessions,
    get_session,
    delete_session,
    get_session_messages,
    add_message,
    update_session_llm,
)
from app.services.chatbot_service import handle_chatbot_chat

router = APIRouter(prefix="/chatbot", tags=["Chatbot Sessions"])


class SessionCreateRequest(BaseModel):
    title: str = "New Chat"


class SessionChatRequest(BaseModel):
    message: str
    uploaded_files: list[dict] = []
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None


@router.post("/sessions", summary="Create chat session")
async def create(
    data: SessionCreateRequest,
    current_user: dict = Depends(get_current_user),
):
    """Create a new chat session."""
    return await create_session(current_user["id"], data.title)


@router.get("/sessions", summary="List chat sessions")
async def list_sessions(
    current_user: dict = Depends(get_current_user),
):
    """Get all chat sessions for the current user."""
    return await get_sessions(current_user["id"])


@router.get("/sessions/{session_id}", summary="Get chat session")
async def get_one(
    session_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Get a single chat session."""
    session = await get_session(session_id, current_user["id"])
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )
    return session


@router.delete("/sessions/{session_id}", summary="Delete chat session")
async def delete(
    session_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Delete a chat session and all its messages."""
    deleted = await delete_session(session_id, current_user["id"])
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )
    return {"status": "deleted", "session_id": session_id}


@router.get("/sessions/{session_id}/messages", summary="Get session messages")
async def messages(
    session_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Get all messages for a chat session."""
    session = await get_session(session_id, current_user["id"])
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )
    return await get_session_messages(session_id)


@router.post("/sessions/{session_id}/chat", summary="Send message in session")
async def chat_in_session(
    session_id: str,
    data: SessionChatRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
):
    """
    Send a message in a chat session and get AI response.

    The message and response are saved to the session history.
    """
    import re
    
    session = await get_session(session_id, current_user["id"])
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    # Resolve LLM provider and model, updating session if user specified new ones
    provider = data.llm_provider
    model = data.llm_model
    
    if provider and model:
        await update_session_llm(session_id, current_user["id"], provider, model)
    else:
        provider = provider or session.get("llm_provider")
        model = model or session.get("llm_model")

    uploaded_files = list(data.uploaded_files) if data.uploaded_files else []
    
    if not uploaded_files:
        file_pattern = r'\[Attached files: (.*?)\]'
        file_match = re.search(file_pattern, data.message)
        if file_match:
            file_info_str = file_match.group(1)
            for file_part in file_info_str.split(", "):
                name_url = file_part.rsplit(" (", 1)
                if len(name_url) == 2:
                    name = name_url[0]
                    url = name_url[1].rstrip(")")
                    uploaded_files.append({"name": name, "url": url})
    
    await add_message(session_id, "user", data.message)

    history_messages = await get_session_messages(session_id)
    conversation_history = [
        {"role": msg["role"], "content": msg["content"]}
        for msg in history_messages[:-1]
    ]

    result = await handle_chatbot_chat(
        user_id=current_user["id"],
        message=data.message,
        conversation_history=conversation_history,
        uploaded_files=uploaded_files,
        background_tasks=background_tasks,
        llm_provider=provider,
        llm_model=model,
        chat_session_id=session_id,
    )

    await add_message(
        session_id,
        "assistant",
        result.get("response", ""),
        actions_taken=result.get("actions_taken"),
        pending_approval=result.get("pending_approval"),
    )

    return result


class InjectApprovalRequest(BaseModel):
    action_id: str


@router.post("/sessions/{session_id}/inject-approval", summary="Inject an approval into session")
async def inject_approval(
    session_id: str,
    data: InjectApprovalRequest,
    current_user: dict = Depends(get_current_user),
):
    """Inject a background-generated pending approval into the active chat session."""
    session = await get_session(session_id, current_user["id"])
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )
        
    from app.config.mongodb_config import get_database
    db = await get_database()
    app_doc = await db.pending_approvals.find_one({"action_id": data.action_id, "user_id": current_user["id"]})
    
    if not app_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pending approval not found",
        )
    
    app_doc.pop("_id", None)
    
    msg = await add_message(
        session_id=session_id,
        role="assistant",
        content="I have generated a new draft for your approval:",
        actions_taken=[],
        pending_approval=app_doc,
    )
    
    return msg