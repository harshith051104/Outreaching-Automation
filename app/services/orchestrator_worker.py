"""
Deterministic workers for the Orchestration Engine.
Executes platform logic without any independent LLM reasoning.
"""

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from app.config.mongodb_config import get_database
from app.utils.id_generator import generate_id
from app.schemas.campaign import CampaignCreate, CampaignSettings
from app.services.campaign_service import (
    create_campaign as db_create_campaign,
    start_campaign as db_start_campaign,
    pause_campaign as db_pause_campaign,
    update_campaign as db_update_campaign
)

logger = logging.getLogger(__name__)


class CampaignWorker:
    """Worker for executing campaign creation, start, pause, and updates."""

    @classmethod
    async def create_campaign(cls, user_id: str, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new campaign."""
        logger.info(f"CampaignWorker: Creating campaign '{args.get('name')}' for user {user_id}")
        
        raw_steps = args.get("sequence_steps")
        if isinstance(raw_steps, str):
            try:
                raw_steps = json.loads(raw_steps)
            except:
                raw_steps = None

        # LINKEDIN DISABLED: strip any linkedin steps from the LLM-provided sequence
        if raw_steps and isinstance(raw_steps, list):
            email_only_steps = [
                {**s, "channel": "email"}
                for s in raw_steps
                if s.get("channel", "email").lower() != "linkedin"
            ]
            for idx, s in enumerate(email_only_steps):
                s["step_number"] = idx + 1
            raw_steps = email_only_steps or None

        campaign_data = CampaignCreate(
            name=args["name"],
            description=args.get("description", ""),
            subject_template=args.get("subject_template", "Outreach"),
            body_template=args.get("body_template", "Hi {{first_name}}"),
            gmail_account_id=args.get("gmail_account_id", ""),
            sequence_steps=raw_steps,
            settings=CampaignSettings()
        )
        
        campaign = await db_create_campaign(user_id=user_id, data=campaign_data)
        
        # Store attachments if any in context
        attachments = context.get("uploaded_files", [])
        if attachments:
            db = await get_database()
            await db.campaigns.update_one(
                {"id": campaign["id"]},
                {"$set": {"attachments": attachments}}
            )
            campaign["attachments"] = attachments
            
        return {"status": "success", "campaign": campaign}

    @classmethod
    async def start_campaign(cls, user_id: str, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Start an existing campaign."""
        campaign_id = args.get("campaign_id", "")
        db = await get_database()
        
        if not campaign_id:
            # Fallback: select most recent draft/paused campaign
            campaign = await db.campaigns.find_one(
                {"user_id": user_id, "status": {"$in": ["draft", "paused"]}},
                sort=[("created_at", -1)]
            )
            if campaign:
                campaign_id = campaign["id"]
                
        if not campaign_id:
            return {"status": "failed", "error": "No draft or paused campaign found to start."}
            
        campaign = await db_start_campaign(campaign_id=campaign_id, user_id=user_id)
        return {"status": "success", "campaign": campaign}

    @classmethod
    async def pause_campaign(cls, user_id: str, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Pause a running campaign."""
        campaign_id = args.get("campaign_id", "")
        db = await get_database()
        
        if not campaign_id:
            campaign = await db.campaigns.find_one(
                {"user_id": user_id, "status": "active"},
                sort=[("created_at", -1)]
            )
            if campaign:
                campaign_id = campaign["id"]
                
        if not campaign_id:
            return {"status": "failed", "error": "No active campaign found to pause."}
            
        campaign = await db_pause_campaign(campaign_id=campaign_id, user_id=user_id)
        return {"status": "success", "campaign": campaign}

    @classmethod
    async def update_campaign(cls, user_id: str, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Update campaign templates or fields."""
        campaign_id = args.get("campaign_id", "")
        if not campaign_id:
            campaign_id = context.get("campaign_id") or ""
            
        if not campaign_id:
            return {"status": "failed", "error": "campaign_id is required"}
            
        campaign = await db_update_campaign(campaign_id=campaign_id, user_id=user_id, data=args)
        return {"status": "success", "campaign": campaign}


class LeadWorker:
    """Worker for executing bulk lead imports (from Google Sheets or local CSV) and lead creation."""

    @classmethod
    async def import_leads(cls, user_id: str, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Import leads from a CSV / Google Sheets URL."""
        from app.services.linkedin_csv_import_service import import_leads_from_csv
        
        file_url = args.get("file_url", "")
        # Google Sheet URL detection
        if not file_url and args.get("sheet_url"):
            file_url = args["sheet_url"]
            
        if not file_url:
            return {"status": "failed", "error": "No file_url or sheet_url provided for import"}
            
        campaign_id = args.get("campaign_id", "")
        if not campaign_id:
            campaign_id = context.get("campaign_id") or ""
            
        db = await get_database()
        
        # If campaign_id is a name, resolve it to UUID
        if campaign_id and len(campaign_id) != 36:
            camp = await db.campaigns.find_one({
                "name": {"$regex": f"^{re.escape(campaign_id)}$", "$options": "i"},
                "user_id": user_id
            })
            if camp:
                campaign_id = camp["id"]

        file_content = None
        filename = file_url.split("/")[-1]

        # Fast path check for local download
        local_match = re.search(r"/api/files/([^/]+)/download", file_url)
        if local_match:
            file_id = local_match.group(1)
            file_doc = await db.uploaded_files.find_one({"id": file_id})
            if file_doc and file_doc.get("file_path"):
                path = file_doc["file_path"]
                if os.path.exists(path):
                    with open(path, "rb") as f:
                        file_content = f.read()
                    filename = file_doc.get("original_filename", filename)
                else:
                    return {"status": "failed", "error": f"Uploaded file not found on disk: {path}"}
            else:
                return {"status": "failed", "error": f"File record not found for id: {file_id}"}

        # Fallback to fetching URL
        if file_content is None:
            import httpx
            async with httpx.AsyncClient(follow_redirects=True) as client:
                response = await client.get(file_url, timeout=30.0)
                if response.status_code != 200:
                    return {"status": "failed", "error": f"Failed to fetch sheet/file from URL: {response.status_code}"}
                file_content = response.content

        result = await import_leads_from_csv(
            csv_content=file_content,
            user_id=user_id,
            campaign_id=campaign_id if campaign_id else None,
            create_leads=True
        )
        
        # Auto-update the campaign lead count in context/db
        if campaign_id:
            total_leads = await db.leads.count_documents({"campaign_id": campaign_id})
            await db.campaigns.update_one(
                {"id": campaign_id},
                {"$set": {"total_leads": total_leads}}
            )
            
        return {
            "status": "success",
            "filename": filename,
            "total_rows": result["total_rows"],
            "valid_leads": result["valid_leads"],
            "leads_created": result.get("leads_created", 0),
            "leads": result["leads"][:10] if result.get("leads") else []
        }


class SheetsWorker:
    """Worker for executing Google Sheets Sync logic."""

    @classmethod
    async def sync_google_sheet(cls, user_id: str, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Triggers a background synchronization with Google Sheets."""
        from app.services.sheets_sync_service import push_bulk
        
        campaign_id = args.get("campaign_id", "")
        if not campaign_id:
            campaign_id = context.get("campaign_id") or ""
            
        if not campaign_id:
            return {"status": "failed", "error": "campaign_id is required for Sheets synchronization"}
            
        # Execute Google Sheets Sync
        try:
            rows_synced = await push_bulk(campaign_id=campaign_id, user_id=user_id)
            return {"status": "success", "message": f"Google Sheets synchronization completed. Synced {rows_synced} rows."}
        except Exception as e:
            logger.warning(f"SheetsWorker failed: {e}")
            return {"status": "failed", "error": str(e)}


class NotificationWorker:
    """Worker for executing team notifications."""

    @classmethod
    async def notify_team(cls, user_id: str, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatches alerts or updates to workspace team members."""
        from app.services.notification_service import notify
        
        try:
            await notify(
                user_id=user_id,
                type=args.get("type", "info"),
                title=args.get("title", "Orchestration Update"),
                message=args.get("message", "Task execution complete."),
                reference_id=args.get("reference_id") or context.get("campaign_id") or "",
                reference_type=args.get("reference_type", "campaign")
            )
            return {"status": "success", "message": "Notification dispatched."}
        except Exception as e:
            logger.warning(f"NotificationWorker failed: {e}")
            return {"status": "failed", "error": str(e)}


class TimelineWorker:
    """Worker for logging audit events and timeline logs."""

    @classmethod
    async def log_timeline(cls, user_id: str, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Logs action events directly to the database timeline collections."""
        db = await get_database()
        
        event = {
            "id": generate_id(),
            "user_id": user_id,
            "campaign_id": args.get("campaign_id") or context.get("campaign_id") or "",
            "event_type": args.get("event_type", "orchestration_action"),
            "description": args.get("description", "Action executed by AI Orchestration engine."),
            "metadata": args.get("metadata", {}),
            "timestamp": datetime.now(timezone.utc)
        }
        
        await db.timeline_events.insert_one(event)
        event.pop("_id", None)
        return {"status": "success", "event": event}


class BatchContentWorker:
    """Worker for generating all campaign email and LinkedIn templates in a single LLM call."""

    @classmethod
    async def generate_batch_content(cls, user_id: str, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Generate email subject, body, follow-ups, and LinkedIn sequences in one batch."""
        from app.services.llm_manager import LLMManager
        
        campaign_id = args.get("campaign_id", "") or context.get("campaign_id") or ""
        campaign_name = args.get("campaign_name", "") or context.get("campaign_name") or "New Campaign"
        
        logger.info(f"BatchContentWorker: Generating batch templates for campaign '{campaign_name}'")
        
        system_prompt = """You are an expert copywriter and sales assistant.
Your task is to generate a comprehensive email outreach campaign in a single response.

You MUST generate:
1. An initial outreach email subject line.
2. An initial outreach email body template (using {{first_name}}, {{company}}, etc. for personalization).
3. A multi-step sequence containing follow-up EMAIL steps only (no LinkedIn).

Ensure that:
- Tone is professional, persuasive, and customized to the provided business details.
- Templates use double braces like {{first_name}}, {{company}}, {{sender_name}}, {{sender_title}}, {{sender_email}}.
- Each follow-up email builds on the previous one with a different angle.

Return your response strictly as a JSON object matching this structure:
{
  "subject_template": "Initial Email Subject Line",
  "body_template": "Initial Email Body Text...",
  "sequence_steps": [
    {
      "step_number": 1,
      "channel": "email",
      "delay_days": 3,
      "subject_template": "Follow-up Email Subject Line",
      "body_template": "Follow-up Email Body Text..."
    },
    {
      "step_number": 2,
      "channel": "email",
      "delay_days": 10,
      "subject_template": "Second Follow-up Subject",
      "body_template": "Second follow-up body text..."
    },
    {
      "step_number": 3,
      "channel": "email",
      "delay_days": 20,
      "subject_template": "Final Follow-up Subject",
      "body_template": "Final break-up Email body text..."
    }
  ]
}
"""

        user_content = f"""Generate campaign content for:
Campaign Name: {campaign_name}
Description: {args.get("description", "")}
Vision/Mission: {args.get("vision", "")}
Products: {args.get("products", "")}
Market Opportunity: {args.get("opportunity", "")}
Investment Expected Impact: {args.get("impact", "")}
Call To Action: {args.get("cta", "a quick call")}
"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]

        completion = await LLMManager.generate_completion(
            task_type="EMAIL_GENERATION",
            messages=messages,
            user_id=user_id,
            temperature=0.4
        )

        content_text = completion.get("content", "{}")
        
        # Parse JSON
        from orchestrator.engine import Orchestrator
        orchestrator_instance = Orchestrator()
        try:
            parsed_content = orchestrator_instance._extract_json(content_text)
        except Exception as e:
            logger.error(f"BatchContentWorker: Failed to parse batch content JSON: {e}")
            parsed_content = {
                "subject_template": f"Investment Opportunity: {campaign_name}",
                "body_template": "Hi {{first_name}},\n\nI hope this finds you well. I'd love to chat about our next-gen product.\n\nBest,\n{{sender_name}}",
                "sequence_steps": []
            }

        # LINKEDIN DISABLED: filter out any linkedin steps the LLM may have hallucinated
        raw_sequence = parsed_content.get("sequence_steps") or []
        email_only_sequence = [
            {**s, "channel": "email"}
            for s in raw_sequence
            if s.get("channel", "email").lower() != "linkedin"
        ]
        # Re-index step numbers to be contiguous
        for idx, s in enumerate(email_only_sequence):
            s["step_number"] = idx + 1

        # Update campaign in MongoDB if ID exists
        if campaign_id:
            db = await get_database()
            await db.campaigns.update_one(
                {"id": campaign_id},
                {
                    "$set": {
                        "subject_template": parsed_content.get("subject_template"),
                        "body_template": parsed_content.get("body_template"),
                        "sequence_steps": email_only_sequence,
                        "updated_at": datetime.now(timezone.utc)
                    }
                }
            )
            logger.info(f"BatchContentWorker: Campaign templates and sequence (email-only) updated for ID {campaign_id}")

        return {
            "status": "success",
            "subject_template": parsed_content.get("subject_template"),
            "body_template": parsed_content.get("body_template"),
            "sequence_steps": email_only_sequence
        }
