"""
Chatbot API Routes.

Handles natural language prompt queries from the frontend client.
"""

from typing import List, Dict, Optional
from datetime import datetime, timezone
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
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None


@router.post("/chat", summary="Send a message to Elly")
async def chat_with_elly(
    data: ChatRequestSchema,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
):
    """
    Process a prompt from the user. Interprets the request using the active LLM provider
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
            background_tasks=background_tasks,
            llm_provider=data.llm_provider,
            llm_model=data.llm_model
        )
        return result
    except Exception as exc:
        import traceback
        try:
            with open("c:/Users/sriha/My work/Outreach/error_traceback.txt", "a", encoding="utf-8") as f:
                f.write(f"\n--- CHATBOT ERROR AT {datetime.now(timezone.utc).isoformat()} ---\n")
                traceback.print_exc(file=f)
        except Exception:
            pass
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Chatbot failed to process message: {exc}"
        )


@router.get("/models", summary="Get available LLM providers and models")
async def get_available_models():
    """
    Get the configured LLM providers and models.
    """
    from app.config.settings import settings
    providers = {}
    
    # Groq
    if settings.GROQ_API_KEY and settings.GROQ_API_KEY.strip() not in ("", "None", '""', "''"):
        providers["groq"] = {
            "name": "Groq",
            "default_model": settings.GROQ_MODEL or "llama-3.3-70b-versatile",
            "models": [
                {"id": "llama-3.3-70b-versatile", "name": "Llama 3.3 70B Versatile"},
                {"id": "llama-3.1-8b-instant", "name": "Llama 3.1 8B Instant"},
                {"id": "llama3-8b-8192", "name": "Llama 3 8B (8192)"}
            ]
        }
        
    # Nvidia NIM
    if settings.NVIDIA_NIM_API_KEY and settings.NVIDIA_NIM_API_KEY.strip() not in ("", "None", '""', "''"):
        providers["nvidia"] = {
            "name": "Nvidia NIM",
            "default_model": settings.NVIDIA_NIM_MODEL or "moonshotai/kimi-k2.6",
            "models": [
                {"id": "moonshotai/kimi-k2.6", "name": "Kimi K2.6 (NIM)"},
                {"id": "nvidia/nemotron-3-ultra-550b-a55b", "name": "Nemotron 3 Ultra 550B (NIM)"},
                {"id": "meta/llama-3.3-70b-instruct", "name": "Llama 3.3 70B Instruct (NIM)"},
                {"id": "deepseek/deepseek-r1", "name": "DeepSeek R1 (NIM)"}
            ]
        }
        
    # Xiaomi
    if settings.XIAOMI_API_KEY and settings.XIAOMI_API_KEY.strip() not in ("", "None", '""', "''"):
        providers["xiaomi"] = {
            "name": "Xiaomi",
            "default_model": settings.XIAOMI_MODEL or "mimo-v2.5",
            "models": [
                {"id": "mimo-v2.5", "name": "MiMo v2.5"},
                {"id": "mimo-v2.5-pro", "name": "MiMo v2.5 Pro"}
            ]
        }
        
    # Determine default provider
    default_provider = settings.LLM_PROVIDER.lower() if settings.LLM_PROVIDER else "nvidia"
    if default_provider not in providers:
        if "nvidia" in providers:
            default_provider = "nvidia"
        elif "groq" in providers:
            default_provider = "groq"
        elif "xiaomi" in providers:
            default_provider = "xiaomi"
        else:
            default_provider = "nvidia"
            
    default_model = providers.get(default_provider, {}).get("default_model", "")
    
    return {
        "providers": providers,
        "default_provider": default_provider,
        "default_model": default_model
    }