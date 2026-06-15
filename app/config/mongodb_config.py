"""
MongoDB configuration and connection management.

Uses Motor async driver with connection pooling.
Auto-creates indexes on startup.
"""

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class MongoDBClient:
    _client: Optional[AsyncIOMotorClient] = None
    _db: Optional[AsyncIOMotorDatabase] = None

    async def connect(self) -> None:
        from app.config.settings import settings

        self._client = AsyncIOMotorClient(
            settings.MONGODB_URL,
            maxPoolSize=50,
            minPoolSize=10,
            serverSelectionTimeoutMS=5000,
        )
        self._db = self._client[settings.MONGODB_DB_NAME]
        logger.info(f"MongoDB connected to {settings.MONGODB_URL}")

    async def disconnect(self) -> None:
        if self._client:
            self._client.close()
            logger.info("MongoDB disconnected")

    async def create_indexes(self) -> None:
        if self._db is None:
            return

        db = self._db
        from pymongo.errors import OperationFailure

        async def safe_create_index(collection, keys, **kwargs):
            try:
                await collection.create_index(keys, **kwargs)
            except OperationFailure as e:
                # Code 85 is IndexOptionsConflict, 86 is IndexKeySpecsConflict.
                # We log a warning and continue to allow startup.
                if e.code in (85, 86) or "already exists" in str(e):
                    logger.warning(
                        f"Index conflict ignored on collection '{collection.name}' "
                        f"for keys {keys}: {e.details.get('errmsg', str(e))}"
                    )
                else:
                    logger.error(
                        f"OperationFailure creating index on '{collection.name}' "
                        f"for keys {keys}: {e}"
                    )
            except Exception as e:
                logger.error(
                    f"Unexpected error creating index on '{collection.name}' "
                    f"for keys {keys}: {e}"
                )

        await safe_create_index(db.users, "email", unique=True)

        await safe_create_index(db.campaigns, "user_id")
        await safe_create_index(db.campaigns, "status")

        await safe_create_index(db.leads, "campaign_id")
        await safe_create_index(db.leads, "user_id")
        await safe_create_index(db.leads, "lead_hash")
        await safe_create_index(db.leads, [("campaign_id", 1), ("user_id", 1)])

        await safe_create_index(db.emails, "tracking_id")
        await safe_create_index(db.emails, "campaign_id")
        await safe_create_index(db.emails, [("campaign_id", 1), ("status", 1)])

        await safe_create_index(db.tracking_events, "tracking_id")
        await safe_create_index(db.tracking_events, [("campaign_id", 1), ("event_type", 1)])

        await safe_create_index(db.followup_tasks, "lead_id")
        await safe_create_index(db.followup_tasks, [("status", 1), ("scheduled_at", 1)])

        await safe_create_index(db.scheduled_tasks, [("status", 1), ("scheduled_at", 1)])

        await safe_create_index(db.replies, "campaign_id")
        await safe_create_index(db.replies, "gmail_message_id", unique=True)
        await safe_create_index(db.replies, "gmail_thread_id")

        await safe_create_index(db.signals, "lead_id")
        await safe_create_index(db.signals, [("lead_id", 1), ("score", -1)])

        await safe_create_index(db.opportunities, "lead_id")

        await safe_create_index(db.gmail_accounts, "user_id")

        await safe_create_index(db.webhooks, "user_id")

        await safe_create_index(db.analytics, "campaign_id", unique=True)

        await safe_create_index(db.analytics_learning_memory, "campaign_id")
        await safe_create_index(db.analytics_learning_memory, [("analyzed_at", -1)])

        await safe_create_index(db.lead_memories, "lead_id", unique=True)

        await safe_create_index(db.campaign_memories, "campaign_id", unique=True)

        await safe_create_index(db.lead_lists, "user_id")

        await safe_create_index(db.block_list, [("user_id", 1), ("value", 1)], unique=True)

        await safe_create_index(db.outreach, "lead_id")
        await safe_create_index(db.outreach, [("status", 1), ("channel", 1)])

        await safe_create_index(db.linkedin_sessions, "user_id", unique=True)
        await safe_create_index(db.linkedin_sessions, "status")

        await safe_create_index(db.linkedin_actions, "user_id")
        await safe_create_index(db.linkedin_actions, "status")
        await safe_create_index(db.linkedin_actions, "action_type")
        await safe_create_index(db.linkedin_actions, [("user_id", 1), ("status", 1)])
        await safe_create_index(db.linkedin_actions, [("user_id", 1), ("action_type", 1), ("status", 1)])

        await safe_create_index(db.linkedin_daily_limits, [("user_id", 1), ("date", 1)], unique=True)

        await safe_create_index(db.linkedin_relationships, [("user_id", 1), ("linkedin_url", 1)], unique=True)
        await safe_create_index(db.linkedin_relationships, "current_stage")
        await safe_create_index(db.linkedin_relationships, "user_id")

        await safe_create_index(db.linkedin_campaigns, "user_id")
        await safe_create_index(db.linkedin_campaigns, "status")
        await safe_create_index(db.linkedin_campaigns, [("user_id", 1), ("status", 1)])

        await safe_create_index(db.linkedin_conversations, "user_id")
        await safe_create_index(db.linkedin_conversations, "contact_linkedin_url")
        await safe_create_index(db.linkedin_conversations, [("user_id", 1), ("last_message_at", -1)])

        await safe_create_index(db.uploaded_files, "user_id")
        await safe_create_index(db.uploaded_files, "id", unique=True)

        await safe_create_index(db.oauth_sessions, "session_id", unique=True)
        await safe_create_index(db.oauth_sessions, [("created_at", 1)], expireAfterSeconds=3600)

        # Chat sessions and messages
        await safe_create_index(db.chat_sessions, "user_id")
        await safe_create_index(db.chat_sessions, [("user_id", 1), ("updated_at", -1)])
        await safe_create_index(db.chat_messages, "session_id")
        await safe_create_index(db.chat_messages, [("session_id", 1), ("created_at", 1)])

        await safe_create_index(db.system_settings, "key", unique=True)

        logger.info("MongoDB indexes checked/created")

    @property
    def db(self) -> AsyncIOMotorDatabase:
        if self._db is None:
            raise RuntimeError("MongoDB not connected. Call connect() first.")
        return self._db


mongodb_client = MongoDBClient()


async def get_database() -> AsyncIOMotorDatabase:
    return mongodb_client.db