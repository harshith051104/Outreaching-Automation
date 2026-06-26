"""
Chat session service.

Manages Elly chat sessions with history persistence.
"""

from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import HTTPException, status

from app.config.mongodb_config import get_database
from app.utils.id_generator import generate_id


async def create_session(
    user_id: str,
    title: str = "New Chat",
    llm_provider: Optional[str] = None,
    llm_model: Optional[str] = None,
) -> dict:
    """Create a new chat session."""
    db = await get_database()
    from app.config.settings import settings

    now = datetime.now(timezone.utc)
    
    # Resolve initial default provider and model if not passed
    provider = llm_provider or getattr(settings, "LLM_PROVIDER", "nvidia")
    
    if provider == "nvidia":
        model = llm_model or getattr(settings, "NVIDIA_NIM_MODEL", "moonshotai/kimi-k2.6")
    elif provider == "xiaomi":
        model = llm_model or getattr(settings, "XIAOMI_MODEL", "mimo-v2.5")
    else:
        model = llm_model or getattr(settings, "GROQ_MODEL", "llama-3.3-70b-versatile")

    session_doc = {
        "id": generate_id(),
        "user_id": user_id,
        "title": title,
        "llm_provider": provider,
        "llm_model": model,
        "created_at": now,
        "updated_at": now,
    }

    await db.chat_sessions.insert_one(session_doc)
    session_doc.pop("_id", None)
    return session_doc


async def get_sessions(user_id: str, limit: int = 50) -> list:
    """Get all chat sessions for a user, most recent first."""
    db = await get_database()
    cursor = db.chat_sessions.find({"user_id": user_id}, {"_id": 0}).sort(
        "updated_at", -1
    ).limit(limit)

    sessions = await cursor.to_list(length=limit)

    for session in sessions:
        count = await db.chat_messages.count_documents(
            {"session_id": session["id"]}
        )
        session["message_count"] = count

    return sessions


async def get_session(session_id: str, user_id: str) -> Optional[dict]:
    """Get a single chat session."""
    db = await get_database()
    session = await db.chat_sessions.find_one(
        {"id": session_id, "user_id": user_id}, {"_id": 0}
    )
    if not session:
        return None

    count = await db.chat_messages.count_documents({"session_id": session_id})
    session["message_count"] = count
    return session


async def delete_session(session_id: str, user_id: str) -> bool:
    """Delete a chat session and all its messages."""
    db = await get_database()

    await db.chat_messages.delete_many({"session_id": session_id})

    result = await db.chat_sessions.delete_one(
        {"id": session_id, "user_id": user_id}
    )
    return result.deleted_count > 0


async def get_session_messages(session_id: str, limit: int = 100) -> list:
    """Get all messages for a chat session."""
    db = await get_database()
    cursor = db.chat_messages.find(
        {"session_id": session_id}, {"_id": 0}
    ).sort("created_at", 1).limit(limit)

    messages = await cursor.to_list(length=limit)
    for m in messages:
        if m.get("pending_approval"):
            action_id = m["pending_approval"].get("action_id")
            if action_id:
                latest = await db.pending_approvals.find_one({"action_id": action_id})
                if latest:
                    latest.pop("_id", None)
                    m["pending_approval"] = latest
    return messages


async def add_message(
    session_id: str,
    role: str,
    content: str,
    actions_taken: list[dict] | None = None,
    pending_approval: dict | None = None,
) -> dict:
    """Add a message to a chat session."""
    db = await get_database()

    now = datetime.now(timezone.utc)
    message_doc = {
        "id": generate_id(),
        "session_id": session_id,
        "role": role,
        "content": content,
        "actions_taken": actions_taken or [],
        "pending_approval": pending_approval,
        "created_at": now,
    }

    await db.chat_messages.insert_one(message_doc)

    await db.chat_sessions.update_one(
        {"id": session_id},
        {"$set": {"updated_at": now}},
    )

    message_doc.pop("_id", None)
    return message_doc


async def update_session_title(session_id: str, user_id: str, title: str) -> bool:
    """Update a session's title."""
    db = await get_database()
    result = await db.chat_sessions.update_one(
        {"id": session_id, "user_id": user_id},
        {"$set": {"title": title, "updated_at": datetime.now(timezone.utc)}},
    )
    return result.matched_count > 0


async def update_session_llm(
    session_id: str,
    user_id: str,
    llm_provider: str,
    llm_model: str,
) -> bool:
    """Update a session's selected provider and model."""
    db = await get_database()
    result = await db.chat_sessions.update_one(
        {"id": session_id, "user_id": user_id},
        {"$set": {
            "llm_provider": llm_provider,
            "llm_model": llm_model,
            "updated_at": datetime.now(timezone.utc)
        }},
    )
    return result.matched_count > 0