"""
Campaign Flow Execution Service.

Manages running flow instances (runs), executing graph steps sequentially,
evaluating conditions, scheduling delays, and handling human approvals.
"""

import logging
import uuid
import re
import asyncio
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional

from app.config.mongodb_config import get_database
from app.services.flow_translator import translate_flow_to_workflow, validate_flow_nodes
from app.services.gmail_service import send_email
from app.services.email_service import create_email, send_campaign_email
from app.schemas.email import EmailCreate
from app.utils.id_generator import generate_tracking_id
from app.services.linkedin_outreach_service import send_connection_request, send_message
from app.models.notification import Notification
from app.models.flow_execution_log import FlowExecutionLog
from app.models.activity_log import ActivityLog

logger = logging.getLogger(__name__)


class FlowExecutionService:
    """Handles visual campaign flow run instantiation, stepping, and log monitoring."""

    @staticmethod
    async def log_to_run(run_id: str, level: str, message: str) -> None:
        """Write execution logs to the specific flow run."""
        db = await get_database()
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "message": message
        }
        await db.flow_runs.update_one(
            {"id": run_id},
            {
                "$push": {"logs": log_entry},
                "$set": {"updated_at": datetime.now(timezone.utc)}
            }
        )
        logger.info(f"[FlowRun {run_id}] {level}: {message}")

    @staticmethod
    async def start_flow(flow_id: str, user_id: str, initial_context: Optional[dict] = None, is_manual: bool = False) -> Dict[str, Any]:
        """
        Starts execution of a visual flow template.
        Triggers lead searches, imports, or spawns individual runs for target leads.
        """
        db = await get_database()
        flow_doc = await db.campaign_flows.find_one({"id": flow_id})
        if not flow_doc:
            raise ValueError(f"Campaign Flow not found: {flow_id}")

        # Translate graph
        translated = translate_flow_to_workflow(flow_doc)
        errors = validate_flow_nodes(translated.get("raw_nodes", []), translated.get("raw_edges", []))
        if errors:
            raise ValueError(f"Flow validation failed: {', '.join(errors)}")

        now = datetime.now(timezone.utc)
        context = initial_context or {}

        # Scan for Trigger / Lead Source nodes to kick off runs
        trigger_nodes = [step for step in translated.get("steps", []) if step["type"] in ("csvUpload", "linkedinSearch", "apolloSearch", "manualLeads", "websiteLeads")]
        
        if not trigger_nodes:
            # General execution flow run without specific trigger
            run_id = str(uuid.uuid4())
            first_non_trigger = None
            for step in translated.get("steps", []):
                if step["type"] not in ("csvUpload", "linkedinSearch", "apolloSearch", "manualLeads", "websiteLeads"):
                    first_non_trigger = step["id"]
                    break

            run_doc = {
                "id": run_id,
                "flow_id": flow_id,
                "flow_name": flow_doc.get("name", "Visual Flow"),
                "user_id": user_id,
                "status": "running",
                "current_step_id": first_non_trigger,
                "context": context,
                "node_states": {},
                "logs": [],
                "created_at": now,
                "updated_at": now
            }
            await db.flow_runs.insert_one(run_doc)
            await FlowExecutionService.log_to_run(run_id, "INFO", f"Flow execution started. First node: {first_non_trigger}")
            
            try:
                user_doc = await db.users.find_one({"id": user_id})
                user_name = user_doc.get("name", "Unknown User") if user_doc else "Unknown User"
                activity = ActivityLog(
                    user_id=user_id,
                    user_name=user_name,
                    action="flow_run_started",
                    reference_id=run_id,
                    reference_type="flow",
                    details=f"Flow execution run '{flow_doc.get('name')}' started"
                )
                await db.activity_logs.insert_one(activity.to_dict())
            except Exception as act_exc:
                logger.error(f"Failed to insert ActivityLog for flow start: {act_exc}")
            
            # Step the execution
            asyncio.create_task(FlowExecutionService.execute_run_step(run_id))
            return {"status": "started", "run_ids": [run_id]}

        # If we have trigger nodes, we execute discovery or query matching leads
        run_ids = []
        for trigger in trigger_nodes:
            node_type = trigger["type"]
            params = trigger.get("parameters", {})
            next_step_id = trigger.get("next_steps", {}).get("default")

            if not next_step_id:
                logger.warning(f"Trigger node {trigger['id']} has no connecting output edge. Skipping.")
                continue

            leads_to_run = []

            if node_type == "linkedinSearch" or node_type == "apolloSearch":
                # Run lead discovery
                from app.services.lead_discovery_service import LeadDiscoveryService
                discovery = LeadDiscoveryService()
                query = params.get("keywords") or params.get("query") or "B2B Outreach"
                
                logger.info(f"Triggering automated lead search for flow: {query}")
                try:
                    leads = await discovery.discover_and_store_leads(
                        user_id=user_id,
                        campaign_id=flow_id, # Link flow id as campaign reference
                        query=query,
                        job_titles=params.get("job_titles") or [],
                        locations=params.get("locations") or [],
                        industry=params.get("industry") or "",
                        limit=int(params.get("limit") or 10)
                    )
                    leads_to_run.extend(leads)
                except Exception as e:
                    logger.error(f"Failed to execute automated discovery trigger: {e}")

            elif node_type == "csvUpload" or node_type == "manualLeads" or node_type == "websiteLeads":
                # Find recent leads for the flow Campaign ID with status new
                leads = await db.leads.find({"campaign_id": flow_id, "status": "new"}).to_list(length=100)
                leads_to_run.extend(leads)

            if not leads_to_run:
                if is_manual:
                    # Add a mock lead for testing/monitoring purposes so the user has immediate visual feedback
                    mock_lead = {
                        "id": f"mock-lead-{uuid.uuid4().hex[:8]}",
                        "name": "Sriharsha (Mock Lead)",
                        "email": "sriha.test@example.com",
                        "company": "OutreachAI",
                        "role": "Founder",
                        "linkedin_url": "https://www.linkedin.com/in/sriha-mock",
                        "status": "new"
                    }
                    leads_to_run.append(mock_lead)
                else:
                    return {"status": "no_new_leads", "run_ids": []}

            # Spawn runs
            for lead in leads_to_run:
                lead_id = lead.get("id") or str(lead.get("_id"))
                run_id = str(uuid.uuid4())
                run_doc = {
                    "id": run_id,
                    "flow_id": flow_id,
                    "flow_name": flow_doc.get("name", "Visual Flow"),
                    "user_id": user_id,
                    "lead_id": lead_id,
                    "lead_name": lead.get("name", "Unknown Lead"),
                    "status": "running",
                    "current_step_id": next_step_id,
                    "context": {**context, "lead": lead, "lead_id": lead_id},
                    "node_states": {
                        trigger["id"]: {"status": "completed", "executed_at": now.isoformat(), "output": {"trigger": node_type}}
                    },
                    "logs": [],
                    "created_at": now,
                    "updated_at": now
                }
                await db.flow_runs.insert_one(run_doc)
                await FlowExecutionService.log_to_run(run_id, "INFO", f"Triggered run for lead {lead.get('name')} ({lead_id}) starting at step: {next_step_id}")
                
                try:
                    user_doc = await db.users.find_one({"id": user_id})
                    user_name = user_doc.get("name", "Unknown User") if user_doc else "Unknown User"
                    activity = ActivityLog(
                        user_id=user_id,
                        user_name=user_name,
                        action="flow_run_started",
                        reference_id=run_id,
                        reference_type="flow",
                        details=f"Flow execution run '{flow_doc.get('name')}' started for lead: {lead.get('name')}"
                    )
                    await db.activity_logs.insert_one(activity.to_dict())
                except Exception as act_exc:
                    logger.error(f"Failed to insert ActivityLog for trigger flow start: {act_exc}")
                
                run_ids.append(run_id)
                
                # Update lead status to contacted/managed under flow
                if not lead_id.startswith("mock-lead"):
                    await db.leads.update_one({"id": lead_id}, {"$set": {"status": "contacted", "updated_at": now}})
                
                # Trigger step execution in background
                asyncio.create_task(FlowExecutionService.execute_run_step(run_id))

        return {"status": "started", "run_ids": run_ids}

    @staticmethod
    async def execute_run_step(run_id: str) -> None:
        """Runs the current node step in a specific flow run trajectory."""
        db = await get_database()
        run = await db.flow_runs.find_one({"id": run_id})
        if not run or run.get("status") not in ("running", "resumed"):
            return

        current_step_id = run.get("current_step_id")
        if not current_step_id:
            await db.flow_runs.update_one(
                {"id": run_id},
                {"$set": {"status": "completed", "updated_at": datetime.now(timezone.utc)}}
            )
            await FlowExecutionService.log_to_run(run_id, "INFO", "Flow reached terminal node. Marked as completed.")
            return

        flow_doc = await db.campaign_flows.find_one({"id": run["flow_id"]})
        if not flow_doc:
            await FlowExecutionService.log_to_run(run_id, "ERROR", "Flow template not found during step execution.")
            return

        translated = translate_flow_to_workflow(flow_doc)
        steps_map = {step["id"]: step for step in translated.get("steps", [])}
        step = steps_map.get(current_step_id)

        if not step:
            await FlowExecutionService.log_to_run(run_id, "ERROR", f"Step config not found for node ID: {current_step_id}")
            return

        # Mark current step as running
        now = datetime.now(timezone.utc)
        await db.flow_runs.update_one(
            {"id": run_id},
            {
                "$set": {
                    f"node_states.{current_step_id}": {
                        "status": "running",
                        "started_at": now.isoformat()
                    },
                    "updated_at": now
                }
            }
        )

        try:
            log_doc = FlowExecutionLog(
                flow_run_id=run_id,
                node_id=current_step_id,
                node_type=step["type"],
                status="running",
                started_at=now,
                message=f"Started execution of step '{step.get('label')}' ({step['type']})"
            )
            await db.flow_execution_logs.insert_one(log_doc.to_dict())
        except Exception as log_exc:
            logger.error(f"Failed to write started execution log: {log_exc}")

        await FlowExecutionService.log_to_run(run_id, "INFO", f"Executing step '{step.get('label')}' ({step['type']})")

        try:
            result = await FlowExecutionService._execute_step_logic(run, step, db)
            
            # Record outcome
            execution_status = result.get("status", "completed")
            node_output = result.get("output", {})
            next_step_branch = result.get("branch", "default")
            
            await db.flow_runs.update_one(
                {"id": run_id},
                {
                    "$set": {
                        f"node_states.{current_step_id}": {
                            "status": execution_status,
                            "completed_at": datetime.now(timezone.utc).isoformat(),
                            "output": node_output
                        },
                        "updated_at": datetime.now(timezone.utc)
                    }
                }
            )

            try:
                comp_now = datetime.now(timezone.utc)
                comp_log_doc = FlowExecutionLog(
                    flow_run_id=run_id,
                    node_id=current_step_id,
                    node_type=step["type"],
                    status=execution_status,
                    started_at=now,
                    completed_at=comp_now,
                    message=f"Completed execution of step '{step.get('label')}' with status '{execution_status}'"
                )
                await db.flow_execution_logs.insert_one(comp_log_doc.to_dict())
            except Exception as log_exc:
                logger.error(f"Failed to write completed execution log: {log_exc}")

            if execution_status == "waiting_for_delay":
                wait_until = result.get("wait_until")
                await db.flow_runs.update_one(
                    {"id": run_id},
                    {"$set": {"status": "waiting_for_delay", "wait_until": wait_until}}
                )
                await FlowExecutionService.log_to_run(run_id, "INFO", f"Step paused for delay. Will resume at: {wait_until.isoformat()}")
                return

            if execution_status == "waiting_for_approval":
                await db.flow_runs.update_one(
                    {"id": run_id},
                    {"$set": {"status": "waiting_for_approval", "approval_requested_at": datetime.now(timezone.utc)}}
                )
                await FlowExecutionService.log_to_run(run_id, "INFO", "Step paused. Waiting for human approval.")
                return

            # Determine next node ID
            next_node_id = step.get("next_steps", {}).get(next_step_branch)
            if not next_node_id and next_step_branch != "default":
                # Fallback to default branch if conditional branch not wired
                next_node_id = step.get("next_steps", {}).get("default")

            await db.flow_runs.update_one(
                {"id": run_id},
                {
                    "$set": {
                        "current_step_id": next_node_id,
                        "status": "running"
                    }
                }
            )

            # Continue execution loop recursively
            # Avoid direct recursion overhead, schedule next step in event loop
            asyncio.create_task(FlowExecutionService.execute_run_step(run_id))

        except Exception as e:
            logger.exception(f"Error executing step {current_step_id} inside run {run_id}")
            await FlowExecutionService.log_to_run(run_id, "ERROR", f"Step failed: {str(e)}")
            await db.flow_runs.update_one(
                {"id": run_id},
                {
                    "$set": {
                        f"node_states.{current_step_id}": {
                            "status": "failed",
                            "completed_at": datetime.now(timezone.utc).isoformat(),
                            "error": str(e)
                        },
                        "status": "failed",
                        "updated_at": datetime.now(timezone.utc)
                    }
                }
            )

            try:
                err_now = datetime.now(timezone.utc)
                fail_log_doc = FlowExecutionLog(
                    flow_run_id=run_id,
                    node_id=current_step_id,
                    node_type=step["type"],
                    status="failed",
                    started_at=now,
                    completed_at=err_now,
                    message=f"Step execution failed: {str(e)}"
                )
                await db.flow_execution_logs.insert_one(fail_log_doc.to_dict())
            except Exception as log_exc:
                logger.error(f"Failed to write failed execution log: {log_exc}")

    @staticmethod
    async def _execute_step_logic(run: Dict[str, Any], step: Dict[str, Any], db) -> Dict[str, Any]:
        """Business logic execution for custom XYFlow node types."""
        node_type = step["type"]
        params = step.get("parameters", {})
        context = run.get("context", {})
        lead_id = context.get("lead_id")
        user_id = run["user_id"]

        lead = None
        if lead_id:
            if lead_id.startswith("mock-lead"):
                lead = context.get("lead")
            else:
                lead = await db.leads.find_one({"id": lead_id})

        # Personalization template renderer
        async def personalize(text: str) -> str:
            if not text:
                return ""
            rendered = text
            
            # Resolve AI draft placeholders from previous steps
            ai_draft = ""
            for node_id, state in run.get("node_states", {}).items():
                if isinstance(state, dict) and state.get("status") == "completed":
                    output = state.get("output", {})
                    if isinstance(output, dict):
                        ai_draft = output.get("result") or output.get("raw_output") or output.get("text") or ""
                        if ai_draft:
                            break
            
            sender_name = ""
            sender_email = ""
            sender_title = "Founder & CEO"
            active_acct = await db.gmail_accounts.find_one({"user_id": user_id, "is_active": True})
            if active_acct:
                sender_name = active_acct.get("name", "")
                sender_email = active_acct.get("email", "")
                sender_title = active_acct.get("title", "Founder & CEO")
                            
            placeholders = {
                "{{ai_draft}}": ai_draft,
                "{{ai_response}}": ai_draft,
                "{{sender_name}}": sender_name,
                "{{sender_email}}": sender_email,
                "{{sender_title}}": sender_title,
            }
            if lead:
                placeholders.update({
                    "{{name}}": lead.get("name", ""),
                    "{{first_name}}": lead.get("name", "").split(" ")[0] if lead.get("name") else "",
                    "{{company}}": lead.get("company", ""),
                    "{{role}}": lead.get("role", ""),
                    "{{email}}": lead.get("email", ""),
                    "{{linkedin_url}}": lead.get("linkedin_url", "")
                })
                
            for k, v in placeholders.items():
                rendered = rendered.replace(k, str(v))
            return rendered

        if node_type == "sendEmail":
            if not lead or not lead.get("email"):
                raise ValueError("Lead does not have a valid email for sendEmail step.")

            subject = await personalize(params.get("template") or params.get("subject_template") or "Outreach")
            body = await personalize(params.get("body_template") or "Hi {{first_name}}")

            campaign = await db.campaigns.find_one({"id": run["flow_id"]})
            gmail_id = campaign.get("gmail_account_id") if campaign else ""

            if not gmail_id:
                active_acct = await db.gmail_accounts.find_one({"user_id": user_id, "is_active": True})
                gmail_id = active_acct["id"] if active_acct else ""

            if not gmail_id and not (lead and "Mock Lead" in lead.get("name", "")):
                raise ValueError("No connected active Gmail account found for sending email.")
            elif not gmail_id:
                gmail_id = "mock-gmail-id"

            tracking_id = generate_tracking_id()
            email_data = EmailCreate(
                campaign_id=run["flow_id"],
                lead_id=lead_id,
                gmail_account_id=gmail_id,
                to=lead["email"],
                subject=subject,
                body_html=body,
                sequence_number=1
            )
            email_doc = await create_email(user_id=user_id, data=email_data, tracking_id=tracking_id)

            if not (lead and "Mock Lead" in lead.get("name", "")):
                await send_campaign_email(email_doc["id"])
                await FlowExecutionService.log_to_run(run["id"], "INFO", f"Gmail Email sent to '{lead.get('email')}' (ID: {email_doc['id']})")
                
                try:
                    user_doc = await db.users.find_one({"id": user_id})
                    user_name = user_doc.get("name", "Unknown User") if user_doc else "Unknown User"
                    activity = ActivityLog(
                        user_id=user_id,
                        user_name=user_name,
                        action="email_sent",
                        reference_id=email_doc["id"],
                        reference_type="email",
                        details=f"Email sent to {lead.get('name')} ({lead.get('email')}) under campaign/flow"
                    )
                    await db.activity_logs.insert_one(activity.to_dict())
                except Exception as act_exc:
                    logger.error(f"Failed to insert ActivityLog for email sent: {act_exc}")
            else:
                from app.utils.id_generator import generate_id
                action_id = generate_id()
                action_doc = {
                    "id": action_id,
                    "user_id": user_id,
                    "lead_id": lead_id,
                    "linkedin_url": lead.get("linkedin_url", ""),
                    "action_type": "email",
                    "status": "pending_approval",
                    "message": body,
                    "email_id": email_doc["id"],
                    "created_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc)
                }
                await db.linkedin_actions.insert_one(action_doc)
                await FlowExecutionService.log_to_run(run["id"], "INFO", f"Gmail Email draft created and shadow action queued in Tasks Approval queue (ID: {action_id}, Email ID: {email_doc['id']})")
                
                try:
                    user_doc = await db.users.find_one({"id": user_id})
                    user_name = user_doc.get("name", "Unknown User") if user_doc else "Unknown User"
                    activity = ActivityLog(
                        user_id=user_id,
                        user_name=user_name,
                        action="email_draft_created",
                        reference_id=email_doc["id"],
                        reference_type="email",
                        details=f"Email draft created for {lead.get('name')} ({lead.get('email')}) under campaign/flow"
                    )
                    await db.activity_logs.insert_one(activity.to_dict())
                except Exception as act_exc:
                    logger.error(f"Failed to insert ActivityLog for email draft: {act_exc}")

            return {
                "status": "completed",
                "output": {"email_id": email_doc["id"], "to": lead["email"], "subject": subject, "body": body},
                "branch": "default"
            }

        elif node_type == "linkedinConnect":
            if not lead or not lead.get("linkedin_url"):
                raise ValueError("Lead does not have a valid LinkedIn URL.")

            note = await personalize(params.get("note") or params.get("body_template") or "")
            from app.utils.id_generator import generate_id
            action_id = generate_id()
            
            # Form action document
            action_doc = {
                "id": action_id,
                "user_id": user_id,
                "lead_id": lead_id,
                "linkedin_url": lead["linkedin_url"],
                "action_type": "connection_request",
                "status": "pending_approval" if (lead and "Mock Lead" in lead.get("name", "")) else "executing",
                "message": note,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            }

            if lead and "Mock Lead" in lead.get("name", ""):
                # Mode 1: Mock Lead - Save to db and return
                await db.linkedin_actions.insert_one(action_doc)
                await FlowExecutionService.log_to_run(run["id"], "INFO", f"LinkedIn Connection Request drafted and queued in Tasks Approval queue (ID: {action_id})")
                
                try:
                    user_doc = await db.users.find_one({"id": user_id})
                    user_name = user_doc.get("name", "Unknown User") if user_doc else "Unknown User"
                    activity = ActivityLog(
                        user_id=user_id,
                        user_name=user_name,
                        action="linkedin_action_queued",
                        reference_id=action_id,
                        reference_type="linkedin_action",
                        details=f"LinkedIn Connection action queued for mock lead {lead.get('name')}"
                    )
                    await db.activity_logs.insert_one(activity.to_dict())
                except Exception as act_exc:
                    logger.error(f"Failed to insert ActivityLog for linkedin action: {act_exc}")

                return {
                    "status": "completed",
                    "output": {"success": True, "action_id": action_id, "note": note, "message": "Connection request drafted and queued for approval"},
                    "branch": "default"
                }
            else:
                # Mode 2: Real Lead - Execute immediately
                await db.linkedin_actions.insert_one(action_doc)
                await FlowExecutionService.log_to_run(run["id"], "INFO", f"LinkedIn Connect: Sending connection request immediately to {lead['linkedin_url']}...")
                
                res = await send_connection_request(
                    linkedin_url=lead["linkedin_url"],
                    note=note,
                    user_id=user_id
                )
                
                new_status = "executed" if res.get("success") else "failed"
                await db.linkedin_actions.update_one(
                    {"id": action_id},
                    {"$set": {
                        "status": new_status,
                        "execution_result": res,
                        "executed_at": datetime.now(timezone.utc),
                        "updated_at": datetime.now(timezone.utc)
                    }}
                )
                
                if not res.get("success"):
                    raise Exception(f"LinkedIn Connect action failed: {res.get('error')}")

                # Increment daily count on success
                try:
                    from app.services.linkedin_scheduler_service import increment_daily_count
                    await increment_daily_count(user_id, "connection")
                except Exception as inc_exc:
                    logger.error(f"Failed to increment daily connection count: {inc_exc}")

                # Update relationship stage
                try:
                    from app.utils.id_generator import generate_id
                    stage = "connection_sent"
                    await db.linkedin_relationships.update_one(
                        {"user_id": user_id, "linkedin_url": lead["linkedin_url"]},
                        {
                            "$set": {"current_stage": stage, "updated_at": datetime.now(timezone.utc)},
                            "$push": {"stage_history": {"stage": stage, "timestamp": datetime.now(timezone.utc)}},
                            "$setOnInsert": {"id": generate_id(), "created_at": datetime.now(timezone.utc)},
                        },
                        upsert=True,
                    )
                except Exception as rel_exc:
                    logger.error(f"Failed to update linkedin relationship for connect: {rel_exc}")

                # Record tracking event
                try:
                    from app.utils.id_generator import generate_id
                    await db.tracking_events.insert_one({
                        "id": generate_id(),
                        "user_id": user_id,
                        "event_type": "linkedin_connection_sent",
                        "linkedin_url": lead["linkedin_url"],
                        "channel": "linkedin",
                        "timestamp": datetime.now(timezone.utc),
                    })
                except Exception as tr_exc:
                    logger.error(f"Failed to record tracking event for connect: {tr_exc}")

                await FlowExecutionService.log_to_run(run["id"], "INFO", f"LinkedIn Connection request sent successfully to {lead['linkedin_url']}.")
                
                try:
                    user_doc = await db.users.find_one({"id": user_id})
                    user_name = user_doc.get("name", "Unknown User") if user_doc else "Unknown User"
                    activity = ActivityLog(
                        user_id=user_id,
                        user_name=user_name,
                        action="linkedin_action_executed",
                        reference_id=action_id,
                        reference_type="linkedin_action",
                        details=f"LinkedIn Connection action executed successfully for lead {lead.get('name')}"
                    )
                    await db.activity_logs.insert_one(activity.to_dict())
                except Exception as act_exc:
                    logger.error(f"Failed to insert ActivityLog for linkedin action execution: {act_exc}")

                return {
                    "status": "completed",
                    "output": {"success": True, "action_id": action_id, "note": note, "result": res},
                    "branch": "default"
                }

        elif node_type == "linkedinMessage":
            if not lead or not lead.get("linkedin_url"):
                raise ValueError("Lead does not have a valid LinkedIn URL.")

            message_text = await personalize(params.get("message") or params.get("body_template") or "Hi")
            from app.utils.id_generator import generate_id
            action_id = generate_id()

            # Form action document
            action_doc = {
                "id": action_id,
                "user_id": user_id,
                "lead_id": lead_id,
                "linkedin_url": lead["linkedin_url"],
                "action_type": "message",
                "status": "pending_approval" if (lead and "Mock Lead" in lead.get("name", "")) else "executing",
                "message": message_text,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            }

            if lead and "Mock Lead" in lead.get("name", ""):
                # Mode 1: Mock Lead - Save to db and return
                await db.linkedin_actions.insert_one(action_doc)
                await FlowExecutionService.log_to_run(run["id"], "INFO", f"LinkedIn DM drafted and queued in Tasks Approval queue (ID: {action_id})")
                
                try:
                    user_doc = await db.users.find_one({"id": user_id})
                    user_name = user_doc.get("name", "Unknown User") if user_doc else "Unknown User"
                    activity = ActivityLog(
                        user_id=user_id,
                        user_name=user_name,
                        action="linkedin_action_queued",
                        reference_id=action_id,
                        reference_type="linkedin_action",
                        details=f"LinkedIn DM action queued for mock lead {lead.get('name')}"
                    )
                    await db.activity_logs.insert_one(activity.to_dict())
                except Exception as act_exc:
                    logger.error(f"Failed to insert ActivityLog for linkedin message action: {act_exc}")

                return {
                    "status": "completed",
                    "output": {"success": True, "action_id": action_id, "message_text": message_text, "message": "Direct message drafted and queued for approval"},
                    "branch": "default"
                }
            else:
                # Mode 2: Real Lead - Execute immediately
                await db.linkedin_actions.insert_one(action_doc)
                await FlowExecutionService.log_to_run(run["id"], "INFO", f"LinkedIn Message: Sending direct message immediately to {lead['linkedin_url']}...")
                
                res = await send_message(
                    linkedin_url=lead["linkedin_url"],
                    message=message_text,
                    user_id=user_id
                )
                
                new_status = "executed" if res.get("success") else "failed"
                await db.linkedin_actions.update_one(
                    {"id": action_id},
                    {"$set": {
                        "status": new_status,
                        "execution_result": res,
                        "executed_at": datetime.now(timezone.utc),
                        "updated_at": datetime.now(timezone.utc)
                    }}
                )
                
                if not res.get("success"):
                    raise Exception(f"LinkedIn Message action failed: {res.get('error')}")

                # Increment daily count on success
                try:
                    from app.services.linkedin_scheduler_service import increment_daily_count
                    await increment_daily_count(user_id, "message")
                except Exception as inc_exc:
                    logger.error(f"Failed to increment daily message count: {inc_exc}")

                # Update relationship stage
                try:
                    from app.utils.id_generator import generate_id
                    stage = "message_sent"
                    await db.linkedin_relationships.update_one(
                        {"user_id": user_id, "linkedin_url": lead["linkedin_url"]},
                        {
                            "$set": {"current_stage": stage, "updated_at": datetime.now(timezone.utc)},
                            "$push": {"stage_history": {"stage": stage, "timestamp": datetime.now(timezone.utc)}},
                            "$setOnInsert": {"id": generate_id(), "created_at": datetime.now(timezone.utc)},
                        },
                        upsert=True,
                    )
                except Exception as rel_exc:
                    logger.error(f"Failed to update linkedin relationship for message: {rel_exc}")

                # Record tracking event
                try:
                    from app.utils.id_generator import generate_id
                    await db.tracking_events.insert_one({
                        "id": generate_id(),
                        "user_id": user_id,
                        "event_type": "linkedin_message_sent",
                        "linkedin_url": lead["linkedin_url"],
                        "channel": "linkedin",
                        "timestamp": datetime.now(timezone.utc),
                    })
                except Exception as tr_exc:
                    logger.error(f"Failed to record tracking event for message: {tr_exc}")

                await FlowExecutionService.log_to_run(run["id"], "INFO", f"LinkedIn DM sent successfully to {lead['linkedin_url']}.")
                
                try:
                    user_doc = await db.users.find_one({"id": user_id})
                    user_name = user_doc.get("name", "Unknown User") if user_doc else "Unknown User"
                    activity = ActivityLog(
                        user_id=user_id,
                        user_name=user_name,
                        action="linkedin_action_executed",
                        reference_id=action_id,
                        reference_type="linkedin_action",
                        details=f"LinkedIn DM action executed successfully for lead {lead.get('name')}"
                    )
                    await db.activity_logs.insert_one(activity.to_dict())
                except Exception as act_exc:
                    logger.error(f"Failed to insert ActivityLog for linkedin message execution: {act_exc}")

                return {
                    "status": "completed",
                    "output": {"success": True, "action_id": action_id, "message_text": message_text, "result": res},
                    "branch": "default"
                }

        elif node_type == "enrichment":
            if not lead or not lead.get("email"):
                raise ValueError("Lead email is missing for enrichment.")

            if lead and "Mock Lead" in lead.get("name", ""):
                await FlowExecutionService.log_to_run(run["id"], "INFO", "Enrichment: Research Logs generated successfully")
                await FlowExecutionService.log_to_run(run["id"], "INFO", "Enrichment: Verification Logs generated successfully")
                await FlowExecutionService.log_to_run(run["id"], "INFO", "Enrichment: Enrichment Summary saved in execution history")
                await FlowExecutionService.log_to_run(run["id"], "INFO", "Enrichment: Lead Score calculated as: 98")
                
                verification = {"status": "valid", "score": 98, "enrichment_summary": "Mock lead verified as deliverable."}
                return {
                    "status": "completed",
                    "output": {"verification": verification},
                    "branch": "default"
                }

            from app.services.hunter_enrichment_service import HunterEnrichmentService
            enricher = HunterEnrichmentService()
            verification = await enricher.verify_email(lead["email"])

            await db.leads.update_one(
                {"id": lead_id},
                {"$set": {"enrichment_data.email_verification": verification, "updated_at": datetime.now(timezone.utc)}}
            )

            return {
                "status": "completed",
                "output": {"verification": verification},
                "branch": "default"
            }

        elif node_type == "aiAction":
            # Run the real agent pipeline
            if lead:
                try:
                    from app.agents.research_agent import research_lead
                    from app.agents.personalization_agent import personalize_for_lead
                    from app.agents.outreach_writer_agent import write_outreach_email

                    await FlowExecutionService.log_to_run(run["id"], "INFO", "Research Started")
                    research = await asyncio.to_thread(research_lead, lead)
                    await FlowExecutionService.log_to_run(run["id"], "INFO", "Research Completed")
                    
                    await FlowExecutionService.log_to_run(run["id"], "INFO", "Personalization Started")
                    personalization = await asyncio.to_thread(personalize_for_lead, lead, research)
                    await FlowExecutionService.log_to_run(run["id"], "INFO", "Personalization Completed")

                    # Persist research and personalization if real lead
                    if lead_id and not lead_id.startswith("mock-lead"):
                        await db.leads.update_one(
                            {"id": lead_id},
                            {
                                "$set": {
                                    "research_data": research,
                                    "personalization_data": personalization,
                                    "updated_at": datetime.now(timezone.utc)
                                }
                            }
                        )
                        # Update lead in memory and context
                        lead["research_data"] = research
                        lead["personalization_data"] = personalization
                        await db.flow_runs.update_one(
                            {"id": run["id"]},
                            {
                                "$set": {
                                    "context.lead.research_data": research,
                                    "context.lead.personalization_data": personalization
                                }
                            }
                        )
                    
                    await FlowExecutionService.log_to_run(run["id"], "INFO", "Drafting Outreach Started")
                    
                    # Resolve sender details from active Gmail account
                    sender_name = ""
                    sender_email = ""
                    sender_title = "Founder & CEO"
                    active_acct = await db.gmail_accounts.find_one({"user_id": user_id, "is_active": True})
                    if active_acct:
                        sender_name = active_acct.get("name", "")
                        sender_email = active_acct.get("email", "")
                        sender_title = active_acct.get("title", "Founder & CEO")

                    draft = await asyncio.to_thread(
                        write_outreach_email,
                        lead_data=lead,
                        personalization_data=personalization,
                        tone=params.get("tone") or "professional",
                        body_template=params.get("prompt") or "",
                        sender_name=sender_name,
                        sender_email=sender_email,
                        sender_title=sender_title
                    )
                    
                    body = draft.get("body") or draft.get("email_body") or draft.get("content") or draft.get("body_text") or draft.get("body_html") or ""
                    
                    await FlowExecutionService.log_to_run(run["id"], "INFO", "Email Draft Generated")
                    return {
                        "status": "completed",
                        "output": {"result": body, "subject": draft.get("subject", "")},
                        "branch": "default"
                    }
                except Exception as agent_exc:
                    logger.error(f"Agent pipeline execution failed inside flow runner: {agent_exc}")
                    await FlowExecutionService.log_to_run(run["id"], "WARNING", f"Agent pipeline failed ({agent_exc}). Falling back to simple inference.")
            
            # Fallback to simple inference if no lead or agent fails
            from orchestrator.engine import get_orchestrator
            orchestrator = await get_orchestrator()

            prompt = await personalize(params.get("prompt") or "Write a short cold outreach greeting")
            system_prompt = "You are an AI Outreach Assistant. Formulate your response as a direct greeting. Output a JSON object with key 'result'."
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ]
            
            inference = await orchestrator._llm_inference({"messages": messages}, {})
            content = inference.get("content", "")
            try:
                parsed = orchestrator._extract_json(content)
            except Exception:
                parsed = {"result": content}

            return {
                "status": "completed",
                "output": parsed,
                "branch": "default"
            }

        elif node_type == "delay":
            delay_value = int(params.get("delay") or 1)
            unit = params.get("unit", "days").lower() # minutes, hours, days
            
            now = datetime.now(timezone.utc)
            if unit == "minutes":
                wait_until = now + timedelta(minutes=delay_value)
            elif unit == "hours":
                wait_until = now + timedelta(hours=delay_value)
            else:
                wait_until = now + timedelta(days=delay_value)

            return {
                "status": "waiting_for_delay",
                "wait_until": wait_until,
                "output": {"wait_until": wait_until.isoformat()},
                "branch": "default"
            }

        elif node_type == "humanApproval":
            # Wait for user validation on UI builder panel
            approval_msg = await personalize(params.get("message") or "Requires outreach message review.")
            return {
                "status": "waiting_for_approval",
                "output": {"approval_message": approval_msg},
                "branch": "default"
            }

        elif node_type == "condition":
            condition_type = params.get("condition_type", "has_email")
            condition_met = False

            if condition_type == "has_email":
                condition_met = bool(lead and lead.get("email"))
            elif condition_type == "has_linkedin":
                condition_met = bool(lead and lead.get("linkedin_url"))
            elif condition_type == "replied":
                condition_met = bool(lead and lead.get("status") == "replied")
            elif condition_type == "ai_classification":
                # AI Classification
                from orchestrator.engine import get_orchestrator
                orchestrator = await get_orchestrator()
                
                check = await personalize(params.get("ai_prompt") or "Is the lead interested?")
                sys_prompt = "Classify if criteria is met. Return JSON object: {'result': true} or {'result': false}."
                messages = [
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": check}
                ]
                inference = await orchestrator._llm_inference({"messages": messages}, {})
                try:
                    parsed = orchestrator._extract_json(inference.get("content", ""))
                    condition_met = bool(parsed.get("result"))
                except Exception:
                    condition_met = False

            branch_name = "true" if condition_met else "false"
            return {
                "status": "completed",
                "output": {"condition_evaluated": condition_type, "result": condition_met},
                "branch": branch_name
            }

        elif node_type == "sendNotification":
            notif_title = await personalize(params.get("title") or "Workflow Notification")
            notif_msg = await personalize(params.get("message") or "Workflow action succeeded.")

            notification = Notification(
                user_id=user_id,
                type="workflow_completed",
                title=notif_title,
                message=notif_msg,
                reference_id=run["id"],
                reference_type="workflow"
            )
            await db.notifications.insert_one(notification.to_dict())

            return {
                "status": "completed",
                "output": {"notification_sent": True},
                "branch": "default"
            }

        else:
            # Pass-through generic / placeholder step
            return {
                "status": "completed",
                "output": {"message": "Placeholder execution completed"},
                "branch": "default"
            }

    @staticmethod
    async def resume_delay_runs() -> None:
        """Finds all waiting_for_delay runs that completed their sleep, and advances them."""
        db = await get_database()
        now = datetime.now(timezone.utc)

        waiting_runs = await db.flow_runs.find({
            "status": "waiting_for_delay",
            "wait_until": {"$lte": now}
        }).to_list(length=100)

        if not waiting_runs:
            return

        logger.info(f"FlowExecutionService: Resuming {len(waiting_runs)} runs from delay sleep.")
        for run in waiting_runs:
            run_id = run["id"]
            
            # Fetch current node Next node ID
            flow_doc = await db.campaign_flows.find_one({"id": run["flow_id"]})
            if not flow_doc:
                continue

            translated = translate_flow_to_workflow(flow_doc)
            steps_map = {step["id"]: step for step in translated.get("steps", [])}
            current_step = steps_map.get(run["current_step_id"])
            if not current_step:
                continue

            next_node_id = current_step.get("next_steps", {}).get("default")

            await db.flow_runs.update_one(
                {"id": run_id},
                {
                    "$set": {
                        "status": "resumed",
                        "current_step_id": next_node_id
                    }
                }
            )
            await FlowExecutionService.log_to_run(run_id, "INFO", f"Resuming delay node. Advancing to node: {next_node_id}")
            asyncio.create_task(FlowExecutionService.execute_run_step(run_id))

    @staticmethod
    async def approve_run_step(run_id: str, approved: bool) -> None:
        """Approve or reject a humanApproval node step."""
        db = await get_database()
        run = await db.flow_runs.find_one({"id": run_id, "status": "waiting_for_approval"})
        if not run:
            raise ValueError(f"Run {run_id} is not waiting for human approval.")

        flow_doc = await db.campaign_flows.find_one({"id": run["flow_id"]})
        if not flow_doc:
            raise ValueError("Flow template not found.")

        translated = translate_flow_to_workflow(flow_doc)
        steps_map = {step["id"]: step for step in translated.get("steps", [])}
        current_step = steps_map.get(run["current_step_id"])
        if not current_step:
            raise ValueError("Current step config not found.")

        branch = "true" if approved else "false"
        next_node_id = current_step.get("next_steps", {}).get(branch)
        if not next_node_id and branch != "default":
            next_node_id = current_step.get("next_steps", {}).get("default")

        await db.flow_runs.update_one(
            {"id": run_id},
            {
                "$set": {
                    "status": "resumed",
                    "current_step_id": next_node_id,
                    f"node_states.{run['current_step_id']}.status": "completed",
                    f"node_states.{run['current_step_id']}.approved": approved,
                    f"node_states.{run['current_step_id']}.completed_at": datetime.now(timezone.utc).isoformat()
                }
            }
        )
        
        status_word = "Approved" if approved else "Rejected"
        await FlowExecutionService.log_to_run(run_id, "INFO", f"User {status_word} step. Proceeding along branch '{branch}' to node: {next_node_id}")
        asyncio.create_task(FlowExecutionService.execute_run_step(run_id))
