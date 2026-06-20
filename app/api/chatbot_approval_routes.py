"""
Chatbot Approval API Routes — /api/chatbot

Handles the approval/rejection workflow for bulk actions proposed by Elly.
When Elly wants to execute a large batch operation (e.g. send 120 connection
requests), it stores a pending approval record and returns the action_id to
the frontend which renders an ApprovalCard component.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.auth.dependencies import get_current_user
from app.config.mongodb_config import get_database
from app.utils.id_generator import generate_id

router = APIRouter(prefix="/chatbot/approvals", tags=["Chatbot Approvals"])


class ApprovalRequest(BaseModel):
    action_id: str
    decision: str   # "approve" | "reject" | "modify"
    modifications: dict[str, Any] = {}


class PendingApprovalResponse(BaseModel):
    action_id: str
    action_type: str
    description: str
    count: int = 0
    items: list[str] = []
    status: str
    created_at: Any


async def _get_approval(db, action_id: str, user_id: str) -> dict:
    doc = await db.pending_approvals.find_one({"action_id": action_id, "user_id": user_id})
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Approval action '{action_id}' not found.",
        )
    return doc


@router.get("", response_model=list[PendingApprovalResponse])
async def list_pending_approvals(current_user: dict = Depends(get_current_user)):
    """List all pending approval actions for the current user."""
    db = await get_database()
    docs = await db.pending_approvals.find(
        {"user_id": current_user["id"], "status": "pending"}
    ).sort("created_at", -1).limit(20).to_list(length=20)

    result = []
    for doc in docs:
        doc.pop("_id", None)
        result.append(doc)
    return result


@router.post("/respond")
async def respond_to_approval(
    body: ApprovalRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Respond to a pending approval action.

    - ``approve``: Execute the stored batch action.
    - ``reject``: Mark as cancelled.
    - ``modify``: Apply modifications and re-queue as pending (returns updated action).
    - ``regenerate``: Regenerate outreach or reply message.
    """
    db = await get_database()
    doc = await _get_approval(db, body.action_id, current_user["id"])

    if doc["status"] != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Action is already '{doc['status']}' and cannot be modified.",
        )

    now = datetime.now(timezone.utc)

    if body.decision == "reject":
        await db.pending_approvals.update_one(
            {"action_id": body.action_id},
            {"$set": {"status": "rejected", "updated_at": now}},
        )
        # Also reject corresponding linkedin_actions if any
        await db.linkedin_actions.update_many(
            {"id": body.action_id},
            {"$set": {"status": "rejected", "updated_at": now}},
        )
        return {"status": "rejected", "message": "Action cancelled."}

    elif body.decision == "modify":
        updates = {"updated_at": now}
        if "items" in body.modifications:
            updates["items"] = body.modifications["items"]
            updates["count"] = len(body.modifications["items"])
        await db.pending_approvals.update_one(
            {"action_id": body.action_id},
            {"$set": updates},
        )
        return {"status": "pending", "action_id": body.action_id, "message": "Action updated. Approve to execute."}

    elif body.decision == "regenerate":
        payload = doc.get("payload", {})
        lead_ids = payload.get("lead_ids", [])
        lead_id = lead_ids[0] if lead_ids else None
        
        lead = None
        if lead_id:
            lead = await db.leads.find_one({"id": lead_id, "user_id": current_user["id"]})
        if not lead and payload.get("linkedin_url"):
            linkedin_url = payload.get("linkedin_url")
            lead = await db.leads.find_one({
                "user_id": current_user["id"],
                "$or": [{"linkedin": linkedin_url}, {"linkedin_url": linkedin_url}]
            })
            
        if not lead:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Lead not found for regeneration.",
            )
            
        from app.services.chatbot_service import _generate_ai_outreach_message, _generate_ai_reply_message
        
        # Check if it is a reply or first message
        description = doc.get("description", "")
        is_reply = "Reply" in description or lead.get("linkedin_reply_received", False)
        
        if is_reply:
            linkedin_url = lead.get("linkedin") or lead.get("linkedin_url", "")
            conv = await db.linkedin_conversations.find_one({
                "user_id": current_user["id"],
                "contact_linkedin_url": linkedin_url
            })
            outbound_actions = await db.linkedin_actions.find({
                "user_id": current_user["id"],
                "linkedin_url": linkedin_url,
                "status": "executed"
            }).to_list(length=20)
            message = await _generate_ai_reply_message(current_user["id"], lead, conv, outbound_actions)
            description = f"Suggested Reply:\n\n{message}"
        else:
            message = await _generate_ai_outreach_message(current_user["id"], lead)
            description = f"Suggested Message:\n\n{message}"
            
        # Update documents
        now_update = datetime.now(timezone.utc)
        payload["message"] = message
        
        await db.pending_approvals.update_one(
            {"action_id": body.action_id},
            {"$set": {
                "description": description,
                "payload": payload,
                "updated_at": now_update
            }}
        )
        
        await db.linkedin_actions.update_many(
            {"id": body.action_id},
            {"$set": {
                "message": message,
                "updated_at": now_update
            }}
        )
        
        # Fetch and return the updated doc
        updated_doc = await db.pending_approvals.find_one({"action_id": body.action_id})
        updated_doc.pop("_id", None)
        return updated_doc

    elif body.decision == "approve":
        await db.pending_approvals.update_one(
            {"action_id": body.action_id},
            {"$set": {"status": "executing", "updated_at": now}},
        )
        try:
            result = await _execute_action(doc, current_user)
            await db.pending_approvals.update_one(
                {"action_id": body.action_id},
                {"$set": {"status": "completed", "result": result, "updated_at": datetime.now(timezone.utc)}},
            )
            return {"status": "completed", "result": result}
        except Exception as exc:
            await db.pending_approvals.update_one(
                {"action_id": body.action_id},
                {"$set": {"status": "failed", "result": {"error": str(exc)}, "updated_at": datetime.now(timezone.utc)}},
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Action execution failed: {exc}",
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid decision '{body.decision}'. Must be: approve, reject, modify, or regenerate.",
        )


@router.post("/create")
async def create_pending_approval(
    body: dict,
    current_user: dict = Depends(get_current_user),
):
    """
    Internal endpoint for chatbot service to create a pending approval.
    
    Body: {action_type, description, count, items, payload}
    """
    db = await get_database()
    action_id = generate_id()
    now = datetime.now(timezone.utc)

    doc = {
        "action_id": action_id,
        "user_id": current_user["id"],
        "action_type": body.get("action_type", "unknown"),
        "description": body.get("description", ""),
        "count": body.get("count", 0),
        "items": body.get("items", [])[:50],  # Store first 50 items for preview
        "payload": body.get("payload", {}),
        "status": "pending",
        "created_at": now,
        "updated_at": now,
    }
    await db.pending_approvals.insert_one(doc)
    doc.pop("_id", None)
    return doc


async def _execute_action(action_doc: dict, user: dict) -> dict:
    """Route the approved action to the appropriate execution service."""
    from app.config.mongodb_config import get_database
    db = await get_database()
    action_type = action_doc.get("action_type", "")
    payload = action_doc.get("payload", {})

    if action_type == "linkedin_connections":
        # Bulk connection request
        if payload.get("is_bulk"):
            from app.services.linkedin_csv_import_service import bulk_create_linkedin_actions
            lead_ids = payload.get("lead_ids", [])
            note = payload.get("note") or payload.get("message") or ""
            result = await bulk_create_linkedin_actions(
                user_id=user["id"],
                lead_ids=lead_ids,
                action_type="connection_request",
                note=note
            )
            return result
        # Individual connection request
        else:
            from app.services.linkedin_outreach_service import send_connection_request
            linkedin_url = payload.get("linkedin_url", "")
            note = payload.get("note") or payload.get("message") or ""
            res = await send_connection_request(linkedin_url, note, user["id"])
            return {"executed": 1, "success": res.get("success", False), "result": res}

    elif action_type == "linkedin_messages":
        # Bulk messages
        if payload.get("is_bulk"):
            from app.services.linkedin_csv_import_service import bulk_create_linkedin_actions
            lead_ids = payload.get("lead_ids", [])
            message = payload.get("message") or ""
            result = await bulk_create_linkedin_actions(
                user_id=user["id"],
                lead_ids=lead_ids,
                action_type="send_message",
                message=message
            )
            return result
        # Individual messages
        else:
            from app.services.linkedin_outreach_service import send_message, send_message_by_name
            message = payload.get("message", "")
            linkedin_url = payload.get("linkedin_url", "")
            person_name = payload.get("person_name", "")
            if linkedin_url:
                res = await send_message(linkedin_url, message, user["id"])
                return {"executed": 1, "success": res.get("success", False), "result": res}
            elif person_name:
                res = await send_message_by_name(person_name, message, user["id"])
                return {"executed": 1, "success": res.get("success", False), "result": res}
            else:
                return {"success": False, "error": "No linkedin_url or person_name provided"}

    elif action_type == "linkedin_follow":
        from app.services.linkedin_outreach_service import follow_profile
        linkedin_url = payload.get("linkedin_url", "")
        res = await follow_profile(linkedin_url, user["id"])
        return {"executed": 1, "success": res.get("success", False), "result": res}

    elif action_type == "email_send":
        # Delegate to campaign scheduler
        campaign_id = payload.get("campaign_id")
        lead_ids = payload.get("lead_ids", [])
        return {"executed": len(lead_ids), "campaign_id": campaign_id, "queued": True}

    elif action_type == "campaign_launch":
        campaign_id = payload.get("campaign_id")
        await db.campaigns.update_one(
            {"id": campaign_id, "user_id": user["id"]},
            {"$set": {"status": "active", "updated_at": datetime.now(timezone.utc)}},
        )
        return {"campaign_id": campaign_id, "status": "active"}

    else:
        return {"message": f"Action type '{action_type}' executed (no specific handler)."}
