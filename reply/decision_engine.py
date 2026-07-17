"""
Campaign decision engine — determines campaign actions based on intent.

Deterministic — no AI calls. Reads INTENT_CAMPAIGN_ACTION mapping.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from reply.models import (
    ReplyIntent, LeadStatus, Decision, WorkflowEvent, WorkflowEventType,
    INTENT_CAMPAIGN_ACTION, INTENT_LEAD_STATUS_MAP,
)
from reply.config import reply_config


def decide(
    intent: ReplyIntent,
    campaign_id: str = "",
    lead_id: str = "",
    user_id: str = "",
) -> Decision:
    """
    Determine campaign action based on classified intent.

    Returns a Decision with campaign_action, lead_status, workflow events.
    """
    action_config = INTENT_CAMPAIGN_ACTION.get(intent, {"action": "continue"})
    campaign_action = action_config.get("action", "continue")
    notify = action_config.get("notify", False)
    create_task = action_config.get("create_task", False)
    delay_days = action_config.get("delay_days", reply_config.default_delay_days)

    lead_status = INTENT_LEAD_STATUS_MAP.get(intent, LeadStatus.REPLIED)

    # Determine followup cancellation
    cancel_followups = campaign_action in ("stop", "pause")

    # Build workflow events
    events = _build_workflow_events(
        intent, campaign_id, lead_id, user_id, campaign_action,
    )

    return Decision(
        campaign_action=campaign_action,
        delay_days=delay_days,
        lead_status=lead_status,
        notify_user=notify,
        create_manual_task=create_task,
        cancel_followups=cancel_followups,
        workflow_events=events,
    )


def _build_workflow_events(
    intent: ReplyIntent,
    campaign_id: str,
    lead_id: str,
    user_id: str,
    action: str,
) -> List[WorkflowEvent]:
    """Build list of workflow events to publish."""
    events = []

    # Always emit reply.received
    events.append(WorkflowEvent(
        event_type=WorkflowEventType.REPLY_RECEIVED,
        campaign_id=campaign_id,
        lead_id=lead_id,
        user_id=user_id,
        data={"intent": intent.value},
    ))

    # Intent-specific events
    intent_event_map = {
        ReplyIntent.MEETING_REQUESTED: WorkflowEventType.MEETING_REQUESTED,
        ReplyIntent.PITCH_DECK_REQUESTED: WorkflowEventType.DECK_REQUESTED,
        ReplyIntent.DATA_ROOM_REQUESTED: WorkflowEventType.DATA_ROOM_REQUESTED,
        ReplyIntent.DUE_DILIGENCE_STARTED: WorkflowEventType.DUE_DILIGENCE_STARTED,
        ReplyIntent.UNSUBSCRIBE: WorkflowEventType.UNSUBSCRIBE_RECEIVED,
        ReplyIntent.REFERRAL: WorkflowEventType.REFERRAL_RECEIVED,
    }

    if intent in intent_event_map:
        events.append(WorkflowEvent(
            event_type=intent_event_map[intent],
            campaign_id=campaign_id,
            lead_id=lead_id,
            user_id=user_id,
            data={"intent": intent.value},
        ))

    # Campaign action events
    if action == "pause":
        events.append(WorkflowEvent(
            event_type=WorkflowEventType.CAMPAIGN_PAUSED,
            campaign_id=campaign_id,
            lead_id=lead_id,
            user_id=user_id,
            data={"reason": intent.value},
        ))
    elif action == "stop":
        events.append(WorkflowEvent(
            event_type=WorkflowEventType.CAMPAIGN_STOPPED,
            campaign_id=campaign_id,
            lead_id=lead_id,
            user_id=user_id,
            data={"reason": intent.value},
        ))

    # Lead status update event
    lead_status = INTENT_LEAD_STATUS_MAP.get(intent, LeadStatus.REPLIED)
    events.append(WorkflowEvent(
        event_type=WorkflowEventType.LEAD_UPDATED,
        campaign_id=campaign_id,
        lead_id=lead_id,
        user_id=user_id,
        data={"lead_status": lead_status.value, "intent": intent.value},
    ))

    # Manual task creation
    if action in ("pause",) and intent in (
        ReplyIntent.PITCH_DECK_REQUESTED, ReplyIntent.DATA_ROOM_REQUESTED,
        ReplyIntent.TECHNICAL_QUESTIONS, ReplyIntent.FINANCIAL_QUESTIONS,
        ReplyIntent.PARTNER_INTRO_REQUESTED,
    ):
        events.append(WorkflowEvent(
            event_type=WorkflowEventType.MANUAL_TASK_CREATED,
            campaign_id=campaign_id,
            lead_id=lead_id,
            user_id=user_id,
            data={"task_type": intent.value, "action_required": _get_task_description(intent)},
        ))

    return events


def _get_task_description(intent: ReplyIntent) -> str:
    """Human-readable task description for manual tasks."""
    descriptions = {
        ReplyIntent.PITCH_DECK_REQUESTED: "Send pitch deck to investor",
        ReplyIntent.DATA_ROOM_REQUESTED: "Grant data room access",
        ReplyIntent.TECHNICAL_QUESTIONS: "Prepare technical deep-dive response",
        ReplyIntent.FINANCIAL_QUESTIONS: "Share financial overview",
        ReplyIntent.PARTNER_INTRO_REQUESTED: "Facilitate partner introduction",
        ReplyIntent.REFERRAL: "Process referral",
    }
    return descriptions.get(intent, "Manual review required")
