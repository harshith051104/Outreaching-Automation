import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

async def websocket_broadcast(inputs: Dict[str, Any], context: Dict[str, Any]) -> Any:
    try:
        from app.websocket.connection_manager import manager
        user_id = inputs.get("user_id")
        event = inputs.get("event", "notification")
        data = inputs.get("data", {})
        payload = {"type": event, "data": data}
        await manager.send_to_user(user_id, payload)
        return {"delivered": True}
    except Exception as exc:
        logger.warning("WebSocket broadcast failed (non-critical): %s", exc)
        return {"delivered": False, "error": str(exc)}

def register_websocket_tools(dispatcher: Any) -> None:
    dispatcher.register("websocket_broadcast", websocket_broadcast)
