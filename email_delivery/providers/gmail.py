"""
Gmail provider implementation. Thin adapter over existing gmail_service.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from email_delivery.providers.base import BaseEmailProvider, ProviderResult


class GmailProvider(BaseEmailProvider):
    """Gmail email provider via Google OAuth."""

    @property
    def name(self) -> str:
        return "gmail"

    async def send(
        self,
        to: str,
        subject: str,
        body_html: str,
        from_email: Optional[str] = None,
        from_name: Optional[str] = None,
        thread_id: Optional[str] = None,
        in_reply_to: Optional[str] = None,
        references: Optional[str] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
    ) -> ProviderResult:
        from app.services.gmail_service import send_email as gmail_send
        try:
            result = await gmail_send(
                gmail_account_id=from_email or "",
                to=to,
                subject=subject,
                body_html=body_html,
                thread_id=thread_id,
                in_reply_to=in_reply_to,
                references=references,
                attachments=attachments,
            )
            return ProviderResult(
                success=True,
                message_id=result.get("gmail_message_id"),
                thread_id=result.get("gmail_thread_id"),
                label_ids=result.get("label_ids", []),
            )
        except Exception as exc:
            return ProviderResult(success=False, error=str(exc))

    async def check_connection(self, account_id: str) -> bool:
        from app.services.gmail_service import _load_gmail_account
        try:
            account = await _load_gmail_account(account_id)
            return account.get("is_active", False)
        except Exception:
            return False

    async def get_inbox(self, account_id: str, max_results: int = 20) -> List[Dict[str, Any]]:
        from app.services.gmail_service import get_inbox_messages
        return await get_inbox_messages(account_id, max_results)

    async def get_thread(self, account_id: str, thread_id: str) -> List[Dict[str, Any]]:
        from app.services.gmail_service import get_thread_messages
        return await get_thread_messages(account_id, thread_id)

    async def check_replies(self, account_id: str, thread_ids: List[str]) -> List[Dict[str, Any]]:
        from app.services.gmail_service import check_for_replies
        return await check_for_replies(account_id, thread_ids)
