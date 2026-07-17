import logging
from typing import Dict, Any
from app.services.gmail_service import send_email, check_for_replies
from app.schemas.gmail import SendEmailRequest

logger = logging.getLogger(__name__)

async def gmail_send(inputs: Dict[str, Any], context: Dict[str, Any]) -> Any:
    request_data = SendEmailRequest(
        gmail_account_id=inputs.get("gmail_account_id"),
        to_email=inputs.get("to"),
        subject=inputs.get("subject"),
        body=inputs.get("body_html"),
    )
    result = await send_email(
        user_id=context.get("user_id", ""),
        data=request_data,
    )
    return result

async def gmail_check_replies(inputs: Dict[str, Any], context: Dict[str, Any]) -> Any:
    replies = await check_for_replies(
        inputs.get("gmail_account_id"),
        inputs.get("thread_ids", []),
    )
    return replies

def register_gmail_tools(dispatcher: Any) -> None:
    dispatcher.register("gmail_send", gmail_send)
    dispatcher.register("gmail_check_replies", gmail_check_replies)
