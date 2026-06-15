"""
Memory service for lead and campaign memory with Qdrant RAG.

Provides semantic retrieval combining similarity, recency, and campaign match.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class AgentMemoryService:
    """Manages MongoDB lead/campaign memories and Qdrant semantic search."""

    @staticmethod
    async def initialize_lead_memory(lead_id: str, user_id: str) -> Dict[str, Any]:
        """Create an empty lead memory document in MongoDB if it doesn't exist."""
        from app.config.mongodb_config import get_database

        db = await get_database()
        existing = await db.lead_memories.find_one({"lead_id": lead_id})
        if existing:
            return existing

        memory_doc = {
            "lead_id": lead_id,
            "user_id": user_id,
            "research_history": [],
            "signals": [],
            "emails_sent": [],
            "responses": [],
            "meetings": [],
            "notes": [],
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        await db.lead_memories.insert_one(memory_doc)
        return memory_doc

    @staticmethod
    async def add_email_to_memory(
        lead_id: str,
        user_id: str,
        email_subject: str,
        email_body: str,
    ) -> None:
        """Log a sent email to lead memory and store in Qdrant."""
        from app.config.mongodb_config import get_database
        from app.services.qdrant_service import store_document

        db = await get_database()
        await AgentMemoryService.initialize_lead_memory(lead_id, user_id)

        email_record = {
            "subject": email_subject,
            "body": email_body,
            "timestamp": datetime.now(timezone.utc),
        }

        await db.lead_memories.update_one(
            {"lead_id": lead_id},
            {
                "$push": {"emails_sent": email_record},
                "$set": {"updated_at": datetime.now(timezone.utc)},
            },
        )

        lead_doc = await db.leads.find_one({"id": lead_id})
        campaign_id = lead_doc.get("campaign_id") if lead_doc else ""

        email_summary = f"Subject: {email_subject}\nBody: {email_body}"
        await store_document(
            collection_name="emails",
            doc_id=lead_id,
            text=email_summary,
            metadata={
                "type": "sent_email",
                "lead_id": lead_id,
                "campaign_id": campaign_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        )

    @staticmethod
    async def add_reply_to_memory(
        lead_id: str,
        user_id: str,
        reply_text: str,
        sentiment: str,
    ) -> None:
        """Log a received reply to lead memory and index in Qdrant."""
        from app.config.mongodb_config import get_database
        from app.services.qdrant_service import store_document

        db = await get_database()
        await AgentMemoryService.initialize_lead_memory(lead_id, user_id)

        reply_record = {
            "body": reply_text,
            "sentiment": sentiment,
            "timestamp": datetime.now(timezone.utc),
        }

        await db.lead_memories.update_one(
            {"lead_id": lead_id},
            {
                "$push": {"responses": reply_record},
                "$set": {"updated_at": datetime.now(timezone.utc)},
            },
        )

        lead_doc = await db.leads.find_one({"id": lead_id})
        campaign_id = lead_doc.get("campaign_id") if lead_doc else ""

        await store_document(
            collection_name="replies",
            doc_id=lead_id,
            text=reply_text,
            metadata={
                "type": "reply",
                "lead_id": lead_id,
                "sentiment": sentiment,
                "campaign_id": campaign_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        )

    @staticmethod
    async def add_note_to_memory(
        lead_id: str,
        user_id: str,
        note_text: str,
    ) -> None:
        """Append manual notes to lead memory."""
        from app.config.mongodb_config import get_database

        db = await get_database()
        await AgentMemoryService.initialize_lead_memory(lead_id, user_id)

        await db.lead_memories.update_one(
            {"lead_id": lead_id},
            {
                "$push": {"notes": {"text": note_text, "timestamp": datetime.now(timezone.utc)}},
                "$set": {"updated_at": datetime.now(timezone.utc)},
            },
        )

    @staticmethod
    async def retrieve_semantic_context(
        query: str,
        limit: int = 3,
        current_campaign_id: Optional[str] = None,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Query Qdrant for similar emails/replies with ranking."""
        import math

        from app.config.mongodb_config import get_database
        from app.services.qdrant_service import search_similar

        similar_emails = await search_similar(collection_name="emails", query=query, limit=limit * 3)
        similar_replies = await search_similar(collection_name="replies", query=query, limit=limit * 3)

        db = await get_database()

        current_campaign = None
        if current_campaign_id:
            current_campaign = await db.campaigns.find_one({"id": current_campaign_id})

        async def _rank_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
            ranked = []
            now = datetime.now(timezone.utc)

            for item in items:
                metadata = item.get("metadata") or {}
                similarity = item.get("score") or 0.0

                recency_score = 1.0
                created_at_str = metadata.get("created_at")
                if created_at_str:
                    try:
                        created_at = datetime.fromisoformat(created_at_str)
                        days_elapsed = max(0.0, (now - created_at).total_seconds() / 86400.0)
                        recency_score = math.exp(-0.01 * days_elapsed)
                    except Exception:
                        pass

                campaign_match_score = 0.0
                item_campaign_id = metadata.get("campaign_id")
                if current_campaign and item_campaign_id:
                    if item_campaign_id == current_campaign_id:
                        campaign_match_score = 1.0
                    else:
                        item_campaign = await db.campaigns.find_one({"id": item_campaign_id})
                        if item_campaign:
                            current_settings = current_campaign.get("settings") or {}
                            item_settings = item_campaign.get("settings") or {}
                            if current_settings.get("tone") == item_settings.get("tone"):
                                campaign_match_score = 0.5

                final_score = (similarity * 0.5) + (recency_score * 0.3) + (campaign_match_score * 0.2)

                ranked.append({
                    "text": item["text"],
                    "score": round(final_score, 4),
                    "lead_id": item.get("entity_id"),
                    "qdrant_similarity": similarity,
                    "recency_score": recency_score,
                    "campaign_match_score": campaign_match_score,
                })

            ranked.sort(key=lambda x: x["score"], reverse=True)
            return ranked[:limit]

        ranked_emails = await _rank_items(similar_emails)
        ranked_replies = await _rank_items(similar_replies)

        return {
            "successful_emails": ranked_emails,
            "past_replies": ranked_replies,
        }

    @staticmethod
    async def add_campaign_memory(
        campaign_id: str,
        user_id: str,
        name: str,
        strategy: str,
    ) -> None:
        """Log campaign strategy summary."""
        from app.config.mongodb_config import get_database
        from app.services.qdrant_service import store_document

        db = await get_database()
        doc = {
            "campaign_id": campaign_id,
            "user_id": user_id,
            "name": name,
            "strategy": strategy,
            "timestamp": datetime.now(timezone.utc),
        }
        await db.campaign_memories.update_one(
            {"campaign_id": campaign_id},
            {"$set": doc},
            upsert=True,
        )

        await store_document(
            collection_name="campaigns",
            doc_id=campaign_id,
            text=f"Campaign Name: {name}\nStrategy: {strategy}",
            metadata={"user_id": user_id},
        )