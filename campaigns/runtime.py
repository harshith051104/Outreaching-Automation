"""
Campaign Runtime — orchestrates the email compilation pipeline.

Responsible only for orchestration: load campaign, load leads, invoke pipeline.
Must NOT generate email content.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from campaigns.pipeline import compile_email
from campaigns.artifacts import EmailArtifact
from campaigns.cache import AICache
from campaigns.compiler import TemplateCompiler
from campaigns.placeholder_engine import PlaceholderEngine
from campaigns.personalization import PersonalizationEngine
from campaigns.prompt_manager import PromptManager
from campaigns.research import ResearchEngine
from campaigns.scorer import PersonalizationScorer
from campaigns.validator import ValidationEngine

logger = logging.getLogger(__name__)


class CampaignRuntime:
    """Orchestrates campaign execution. Never generates email content directly."""

    def __init__(self, db: Any = None, llm_manager: Any = None):
        self._db = db
        self._llm = llm_manager

        # Instantiate engines
        self._research_engine = ResearchEngine()
        self._personalization_engine = PersonalizationEngine(llm_manager)
        self._placeholder_engine = PlaceholderEngine()
        self._validator = ValidationEngine(self._placeholder_engine)
        self._compiler = TemplateCompiler(self._placeholder_engine)
        self._scorer = PersonalizationScorer()
        self._cache = AICache(db)
        self._prompt_manager = PromptManager(db)

    async def compile_lead_email(
        self,
        lead: Dict[str, Any],
        campaign: Dict[str, Any],
        user: Optional[Dict[str, Any]] = None,
        gmail_account: Optional[Dict[str, Any]] = None,
    ) -> EmailArtifact:
        """Compile a single email for a lead through the full pipeline."""
        subject_template = campaign.get("subject_template", "")
        body_template = campaign.get("body_template", "")

        return await compile_email(
            lead=lead,
            campaign=campaign,
            subject_template=subject_template,
            body_template=body_template,
            user=user,
            gmail_account=gmail_account,
            research_engine=self._research_engine,
            personalization_engine=self._personalization_engine,
            placeholder_engine=self._placeholder_engine,
            validator=self._validator,
            compiler=self._compiler,
            scorer=self._scorer,
            cache=self._cache,
            prompt_manager=self._prompt_manager,
        )

    async def process_lead(
        self,
        campaign: Dict[str, Any],
        lead: Dict[str, Any],
    ) -> str:
        """Process a single lead: compile email, validate, send. Returns status string."""
        from app.config.mongodb_config import get_database
        from app.schemas.email import EmailCreate
        from app.services.email_service import create_email, send_campaign_email
        from app.utils.id_generator import generate_tracking_id

        db = self._db or await get_database()
        user_id = campaign["user_id"]
        gmail_account_id = campaign.get("gmail_account", "")

        if not gmail_account_id:
            return "skipped"

        # Fetch related data
        user = await db.users.find_one({"id": user_id})
        gmail_account = await db.gmail_accounts.find_one({"id": gmail_account_id})

        # Check for existing email
        existing = await db.emails.find_one({
            "campaign_id": campaign["id"],
            "lead_id": lead["id"],
            "sequence_number": 1,
        })
        if existing:
            return "already_sent"

        lead_email = lead.get("email", "").strip()
        if not lead_email:
            return "skipped"

        # Compile email through pipeline
        artifact = await self.compile_lead_email(lead, campaign, user, gmail_account)

        # Validate
        if not artifact.validation.get("passed", False):
            logger.warning(
                "Email validation failed for lead %s: %s",
                lead["id"], artifact.validation.get("issues"),
            )
            return "validation_failed"

        if not artifact.subject or not artifact.body:
            return "skipped"

        # Create email record
        tracking_id = generate_tracking_id()
        email_data = EmailCreate(
            campaign_id=campaign["id"],
            lead_id=lead["id"],
            gmail_account_id=gmail_account_id,
            to=lead_email,
            subject=artifact.subject,
            body_html=artifact.body,
            sequence_number=1,
        )

        email_doc = await create_email(user_id, email_data, tracking_id)

        # Send
        await send_campaign_email(email_doc["id"])

        # Update lead status
        await db.leads.update_one(
            {"id": lead["id"]},
            {"$set": {"status": "contacted", "updated_at": datetime.now(timezone.utc)}},
        )

        return "sent"

    async def execute_campaign(self, campaign_id: str) -> Dict[str, Any]:
        """Execute a campaign: process pending leads and send emails."""
        from app.config.mongodb_config import get_database

        db = self._db or await get_database()
        campaign = await db.campaigns.find_one({"id": campaign_id})
        if not campaign:
            return {"status": "error", "message": "Campaign not found"}

        if campaign.get("status") != "active":
            return {"status": "skipped", "message": f"Campaign is {campaign.get('status')}"}

        # Find pending leads
        leads = await db.leads.aggregate([
            {"$match": {"campaign_id": campaign_id, "status": "new"}},
            {"$limit": campaign.get("daily_send_limit", 50)},
        ]).to_list(length=100)

        if not leads:
            return {"status": "complete", "message": "No pending leads"}

        results = []
        for lead in leads:
            try:
                updated = await db.leads.find_one_and_update(
                    {"_id": lead["_id"], "status": "new"},
                    {"$set": {"status": "contacted", "updated_at": datetime.now(timezone.utc)}}
                )
                if not updated:
                    continue

                status = await self.process_lead(campaign, lead)
                results.append({"lead_id": lead.get("id"), "status": status})
            except Exception as exc:
                logger.exception("Failed to process lead %s: %s", lead.get("id"), exc)
                results.append({"lead_id": lead.get("id"), "status": "error", "error": str(exc)})

        return {
            "status": "processed",
            "campaign_id": campaign_id,
            "leads_processed": len(results),
            "results": results,
        }

    def clear_cache(self, campaign_id: str, lead_id: str) -> None:
        """Clear AI cache for a lead+campaign."""
        import asyncio
        asyncio.create_task(self._cache.clear(campaign_id, lead_id))
