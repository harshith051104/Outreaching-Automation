"""
Async MongoDB persistence layer for email records and tracking events.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.config.mongodb_config import get_database
from app.utils.id_generator import generate_id, generate_tracking_id

from email_delivery.models import EmailRecord, EmailStatus, TrackingEvent


class EmailPersistence:
    """Async MongoDB operations for emails and tracking events."""

    async def create_email(self, record: EmailRecord) -> EmailRecord:
        db = await get_database()
        now = datetime.now(timezone.utc)
        if not record.id:
            record.id = generate_id()
        if not record.tracking_id:
            record.tracking_id = generate_tracking_id()
        record.created_at = now
        record.updated_at = now
        record.status = EmailStatus.CREATED.value
        doc = record.to_doc()
        await db.emails.insert_one(doc)
        return record

    async def get_email(self, email_id: str) -> Optional[EmailRecord]:
        db = await get_database()
        doc = await db.emails.find_one({"id": email_id})
        if not doc:
            return None
        doc.pop("_id", None)
        return EmailRecord.from_doc(doc)

    async def get_email_by_tracking_id(self, tracking_id: str) -> Optional[EmailRecord]:
        db = await get_database()
        doc = await db.emails.find_one({"tracking_id": tracking_id})
        if not doc:
            return None
        doc.pop("_id", None)
        return EmailRecord.from_doc(doc)

    async def update_status(
        self,
        email_id: str,
        new_status: EmailStatus,
        **set_fields: Any,
    ) -> bool:
        db = await get_database()
        email_doc = await db.emails.find_one({"id": email_id})
        if not email_doc:
            return False
        current = EmailStatus(email_doc.get("status", EmailStatus.CREATED.value))
        if not current.can_transition_to(new_status):
            return False
        update: Dict[str, Any] = {
            "status": new_status.value,
            "updated_at": datetime.now(timezone.utc),
        }
        update.update(set_fields)
        await db.emails.update_one({"id": email_id}, {"$set": update})
        return True

    async def update_email(self, email_id: str, **set_fields: Any) -> bool:
        db = await get_database()
        set_fields["updated_at"] = datetime.now(timezone.utc)
        result = await db.emails.update_one({"id": email_id}, {"$set": set_fields})
        return result.modified_count > 0

    async def list_campaign_emails(
        self,
        campaign_id: str,
        status: Optional[EmailStatus] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[EmailRecord]:
        db = await get_database()
        query: Dict[str, Any] = {"campaign_id": campaign_id}
        if status:
            query["status"] = status.value
        cursor = (
            db.emails.find(query, {"_id": 0})
            .sort("created_at", -1)
            .skip(skip)
            .limit(limit)
        )
        docs = await cursor.to_list(length=limit)
        return [EmailRecord.from_doc(d) for d in docs]

    async def count_recent_sends(
        self,
        campaign_id: Optional[str] = None,
        gmail_account_id: Optional[str] = None,
        user_id: Optional[str] = None,
        since: Optional[datetime] = None,
    ) -> int:
        db = await get_database()
        if since is None:
            since = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
        query: Dict[str, Any] = {
            "status": {"$in": [EmailStatus.SENT.value, EmailStatus.SENDING.value, EmailStatus.PAUSED.value]},
            "created_at": {"$gte": since},
        }
        if gmail_account_id:
            query["gmail_account_id"] = gmail_account_id
        elif user_id:
            query["user_id"] = user_id
        elif campaign_id:
            query["campaign_id"] = campaign_id
        return await db.emails.count_documents(query)

    async def create_tracking_event(self, event: TrackingEvent) -> TrackingEvent:
        db = await get_database()
        if not event.id:
            event.id = generate_id()
        await db.tracking_events.insert_one(event.to_doc())
        return event

    async def get_tracking_events(
        self,
        campaign_id: Optional[str] = None,
        tracking_id: Optional[str] = None,
        limit: int = 500,
    ) -> List[TrackingEvent]:
        db = await get_database()
        query: Dict[str, Any] = {}
        if campaign_id:
            query["campaign_id"] = campaign_id
        if tracking_id:
            query["tracking_id"] = tracking_id
        cursor = (
            db.tracking_events.find(query, {"_id": 0})
            .sort("timestamp", -1)
            .limit(limit)
        )
        docs = await cursor.to_list(length=limit)
        return [TrackingEvent.from_doc(d) for d in docs]

    async def get_tracking_stats(self, campaign_id: str) -> Dict[str, Any]:
        db = await get_database()
        pipeline = [
            {"$match": {"campaign_id": campaign_id}},
            {
                "$group": {
                    "_id": "$event_type",
                    "count": {"$sum": 1},
                    "unique_emails": {"$addToSet": "$email_id"},
                }
            },
        ]
        results = await db.tracking_events.aggregate(pipeline).to_list(length=10)
        stats: Dict[str, Any] = {
            "campaign_id": campaign_id,
            "opens": 0, "unique_opens": 0,
            "clicks": 0, "unique_clicks": 0,
            "replies": 0,
        }
        for r in results:
            t = r["_id"]
            if t == "open":
                stats["opens"] = r["count"]
                stats["unique_opens"] = len(r["unique_emails"])
            elif t == "click":
                stats["clicks"] = r["count"]
                stats["unique_clicks"] = len(r["unique_emails"])
            elif t == "reply":
                stats["replies"] = r["count"]
        return stats
