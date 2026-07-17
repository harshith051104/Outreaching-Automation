"""
DeliveryManager — orchestrates email send lifecycle.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from email_delivery.models import (
    EmailRecord,
    EmailStatus,
    RetryPolicy,
    SendResult,
)
from email_delivery.persistence import EmailPersistence
from email_delivery.providers.base import BaseEmailProvider
from email_delivery.providers.gmail import GmailProvider
from email_delivery.retry import RetryManager
from email_delivery.tracking.click_tracker import replace_links_with_tracking
from email_delivery.utils import inject_tracking_pixel
from app.config.mongodb_config import get_database

logger = logging.getLogger(__name__)


class DeliveryManager:
    """
    Main entry point for email delivery.

    Usage:
        manager = DeliveryManager()
        result = await manager.send(email_record, body_html_with_tracking)
    """

    def __init__(
        self,
        persistence: EmailPersistence | None = None,
        provider: BaseEmailProvider | None = None,
        retry_policy: RetryPolicy = RetryPolicy.EXPONENTIAL,
    ):
        self.persistence = persistence or EmailPersistence()
        self.provider = provider or GmailProvider()
        self.retry_policy = retry_policy

    async def create_and_send(
        self,
        email_record: EmailRecord,
        body_html: str,
        inject_tracking_flag: bool = True,
    ) -> SendResult:
        """Create email record, inject tracking, and send."""
        email_record = await self.persistence.create_email(email_record)
        if inject_tracking_flag and email_record.tracking_id:
            body_html = replace_links_with_tracking(body_html, email_record.tracking_id)
            body_html = inject_tracking_pixel(body_html, email_record.tracking_id)
        return await self.send(email_record, body_html)

    async def send(
        self,
        email_record: EmailRecord,
        body_html: str,
        in_reply_to: Optional[str] = None,
        references: Optional[str] = None,
    ) -> SendResult:
        """Send an already-created email record."""
        await self.persistence.update_status(email_record.id, EmailStatus.SENDING)

        result = await self.provider.send(
            to=email_record.to,
            subject=email_record.subject,
            body_html=body_html,
            from_email=email_record.gmail_account_id,
            thread_id=email_record.gmail_thread_id,
            in_reply_to=in_reply_to,
            references=references,
            attachments=email_record.attachments or None,
        )

        if result.success:
            await self._handle_send_success(email_record, result)
            return SendResult(
                success=True,
                gmail_message_id=result.message_id,
                gmail_thread_id=result.thread_id,
                label_ids=result.label_ids,
            )
        else:
            return await self._handle_send_failure(email_record, result.error or "Unknown error")

    async def _handle_send_success(self, email: EmailRecord, result) -> None:
        await self.persistence.update_status(
            email.id,
            EmailStatus.SENT,
            gmail_message_id=result.message_id,
            gmail_thread_id=result.thread_id,
            sent_at=datetime.now(timezone.utc),
        )
        if email.campaign_id:
            db = await get_database()
            await db.campaigns.update_one(
                {"id": email.campaign_id},
                {"$inc": {"emails_sent": 1}},
            )
        try:
            from app.services.analytics_service import update_campaign_analytics
            await update_campaign_analytics(email.campaign_id)
        except Exception:
            pass

    async def _handle_send_failure(self, email: EmailRecord, error: str) -> SendResult:
        retry_mgr = RetryManager(policy=self.retry_policy, max_attempts=3)
        if retry_mgr.should_retry(email.retry_count):
            next_at = retry_mgr.next_retry_at(email.retry_count)
            await self.persistence.update_email(
                email.id,
                status=EmailStatus.READY.value,
                error_message=error,
                retry_count=email.retry_count + 1,
                next_retry_at=next_at,
            )
            return SendResult(success=False, error=error, should_retry=True)
        else:
            await self.persistence.update_status(email.id, EmailStatus.FAILED, error_message=error)
            return SendResult(success=False, error=error, should_retry=False)

    def inject_tracking(self, email: EmailRecord, body_html: str) -> str:
        """Inject open pixel + click tracking into email HTML."""
        if not email.tracking_id:
            return body_html
        body_html = replace_links_with_tracking(body_html, email.tracking_id)
        body_html = inject_tracking_pixel(body_html, email.tracking_id)
        return body_html
