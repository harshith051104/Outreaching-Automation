"""
Google Sheets Bi-Directional Sync Service.

Synchronizes lead outreach tracking data between MongoDB and the team's
Google Sheet (1TM5J62Vn-Etaaj7qwx9kSMxgzFi4pz6XRqkRuqcmsuo).

Direction 1 — Platform → Sheet (push):
    When a checkbox is updated or a lead's data changes, this service
    finds the matching row in the user's named tab and updates the columns.

Direction 2 — Sheet → Platform (pull):
    A background task runs every 15 minutes, reads each user's tab,
    and upserts any changes into MongoDB.

Authentication:
    Uses a Service Account JSON credential stored (encrypted) in
    user_integrations for the google_sheets provider.
    Falls back to checking if the user has a spreadsheet_id configured
    with a publicly editable sheet (no auth needed for read).

Column mapping (Google Sheet tabs for investment tracking):
    Col A: Investor Name     → lead.name
    Col B: Focus             → lead.focus
    Col C: LinkedIn URL      → lead.linkedin
    Col D: Email             → lead.email
    Col E: LinkedIn Followed → lead.linkedin_followed
    Col F: Connection Sent   → lead.linkedin_connection_sent
    Col G: Connection Accepted → lead.linkedin_connection_accepted
    Col H: First Message     → lead.linkedin_first_message_sent
    Col I: LinkedIn Reply    → lead.linkedin_reply_received
    Col J: Email Sent        → lead.email_sent
    Col K: Email Opened      → lead.email_opened
    Col L: Email Replied     → lead.email_replied
    Col M: Follow-up 1       → lead.followup_1_sent
    Col N: Follow-up 2       → lead.followup_2_sent
    Col O: Follow-up 3       → lead.followup_3_sent
    Col P: Meeting Scheduled → lead.meeting_scheduled
    Col Q: Closed            → lead.opportunity_closed
    Col R: Notes             → lead.notes
    Col S: Status            → lead.status
    Col T: Last Activity     → lead.last_activity_at (read-only, written by platform)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from app.config.mongodb_config import get_database

logger = logging.getLogger(__name__)

# Column letter → lead field mapping
SHEET_COLUMNS = [
    ("A", "name"),
    ("B", "focus"),
    ("C", "linkedin"),
    ("D", "email"),
    ("E", "linkedin_followed"),
    ("F", "linkedin_connection_sent"),
    ("G", "linkedin_connection_accepted"),
    ("H", "linkedin_first_message_sent"),
    ("I", "linkedin_reply_received"),
    ("J", "email_sent"),
    ("K", "email_opened"),
    ("L", "email_replied"),
    ("M", "followup_1_sent"),
    ("N", "followup_2_sent"),
    ("O", "followup_3_sent"),
    ("P", "meeting_scheduled"),
    ("Q", "opportunity_closed"),
    ("R", "notes"),
    ("S", "status"),
    ("T", "last_activity_at"),  # Written by platform only
]

BOOL_FIELDS = {col[1] for col in SHEET_COLUMNS if col[1] not in ("name", "focus", "linkedin", "email", "notes", "status", "last_activity_at")}


def _build_gspread_client(service_account_json: str):
    """Build an authenticated gspread client from service account JSON."""
    import gspread
    from google.oauth2.service_account import Credentials

    scopes = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    creds_dict = json.loads(service_account_json)
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    return gspread.authorize(creds)


def _bool_to_sheet(val: bool) -> str:
    return "TRUE" if val else "FALSE"


def _sheet_to_bool(val: str) -> bool:
    return str(val).strip().upper() in ("TRUE", "YES", "1", "✓", "X")


# ─────────────────────────────────────────────────────────────────────────────
# Push: Platform → Sheet
# ─────────────────────────────────────────────────────────────────────────────


async def push_lead_to_sheet(lead_id: str, user_id: str) -> None:
    """
    Push a single lead's tracking data to the Google Sheet row
    in the tab matching the assigned user's display_name.
    """
    db = await get_database()

    # Get sheet credentials for this user
    creds = await _get_sheet_creds(user_id)
    if not creds:
        return  # Sheet not configured for this user

    lead = await db.leads.find_one({"id": lead_id})
    if not lead:
        return

    # Determine which tab to write to (tab = assigned_user's display_name)
    tab_name = lead.get("assigned_user") or await _get_user_display_name(db, user_id)
    if not tab_name:
        return

    try:
        await _push_lead_row(creds, tab_name, lead)
        # Log timeline event
        from app.models.lead_timeline import LeadTimeline
        event = LeadTimeline(
            lead_id=lead_id,
            user_id=user_id,
            campaign_id=lead.get("campaign_id", ""),
            event_type="sheet_synced",
            description=f"Synced to Google Sheet tab '{tab_name}'",
        )
        await db.lead_timeline.insert_one(event.to_dict())
    except Exception as exc:
        logger.warning("Sheet push failed for lead %s: %s", lead_id, exc)


async def push_bulk(campaign_id: str, user_id: str) -> int:
    """
    Push all leads in a campaign to Google Sheet.
    Returns the number of rows written.
    """
    db = await get_database()
    creds = await _get_sheet_creds(user_id)
    if not creds:
        return 0

    leads = await db.leads.find({"campaign_id": campaign_id}).to_list(length=2000)
    count = 0
    for lead in leads:
        tab_name = lead.get("assigned_user") or await _get_user_display_name(db, user_id)
        if tab_name:
            try:
                await _push_lead_row(creds, tab_name, lead)
                count += 1
            except Exception as exc:
                logger.warning("Bulk push failed for lead %s: %s", lead.get("id", "?"), exc)
    return count


async def _push_lead_row(creds: dict, tab_name: str, lead: dict) -> None:
    """Write/update the lead row in the named sheet tab (runs sync in thread pool)."""
    import asyncio

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _push_lead_row_sync, creds, tab_name, lead)


def _push_lead_row_sync(creds: dict, tab_name: str, lead: dict) -> None:
    """Synchronous gspread operation — runs in thread pool executor."""
    gc = _build_gspread_client(creds["service_account_json"])
    spreadsheet = gc.open_by_key(creds["spreadsheet_id"])

    try:
        worksheet = spreadsheet.worksheet(tab_name)
    except Exception:
        worksheet = spreadsheet.add_worksheet(title=tab_name, rows=1000, cols=26)

    # Find header row or create it
    all_values = worksheet.get_all_values()
    if not all_values:
        headers = [col[0] + ": " + col[1].replace("_", " ").title() for col in SHEET_COLUMNS]
        worksheet.append_row(headers)
        all_values = [headers]

    # Find existing row by email
    email = lead.get("email", "")
    row_index = None
    for i, row in enumerate(all_values[1:], start=2):
        if len(row) >= 4 and row[3].strip().lower() == email.lower():
            row_index = i
            break

    # Build row data
    row_data = []
    for col_letter, field in SHEET_COLUMNS:
        val = lead.get(field, "")
        if field in BOOL_FIELDS:
            row_data.append(_bool_to_sheet(bool(val)))
        elif field == "last_activity_at" and isinstance(val, datetime):
            row_data.append(val.strftime("%Y-%m-%d %H:%M UTC"))
        else:
            row_data.append(str(val) if val else "")

    if row_index:
        col_count = len(SHEET_COLUMNS)
        worksheet.update(f"A{row_index}:{chr(64 + col_count)}{row_index}", [row_data])
    else:
        worksheet.append_row(row_data)


# ─────────────────────────────────────────────────────────────────────────────
# Pull: Sheet → Platform
# ─────────────────────────────────────────────────────────────────────────────


async def pull_sheet_updates(user_id: str) -> int:
    """
    Read the user's sheet tab and upsert any new/changed leads into MongoDB.
    Returns the number of rows processed.
    """
    db = await get_database()
    creds = await _get_sheet_creds(user_id)
    if not creds:
        return 0

    tab_name = await _get_user_display_name(db, user_id)
    if not tab_name:
        return 0

    try:
        import asyncio
        loop = asyncio.get_event_loop()
        rows = await loop.run_in_executor(None, _read_sheet_tab, creds, tab_name)
    except Exception as exc:
        logger.warning("Sheet pull failed for user %s tab '%s': %s", user_id, tab_name, exc)
        return 0

    count = 0
    now = datetime.now(timezone.utc)
    for row in rows:
        email = row.get("email", "").strip()
        if not email:
            continue

        existing = await db.leads.find_one({"email": email, "user_id": user_id})
        update_fields: dict[str, Any] = {
            "focus": row.get("focus", ""),
            "linkedin": row.get("linkedin", ""),
            "notes": row.get("notes", ""),
            "assigned_user": tab_name,
            "custom_fields": row.get("custom_fields", {}),
            "updated_at": now,
        }
        # Only update checkboxes if TRUE in sheet (never clear a box from sheet side)
        for field in BOOL_FIELDS:
            sheet_val = row.get(field)
            if sheet_val is True:
                update_fields[field] = True

        if existing:
            await db.leads.update_one({"_id": existing["_id"]}, {"$set": update_fields})
        else:
            # Import new lead
            from app.models.lead import Lead
            new_lead = Lead(
                campaign_id="",  # Unassigned — user can link to a campaign later
                user_id=user_id,
                name=row.get("name", "Unknown"),
                email=email,
                focus=row.get("focus", ""),
                linkedin=row.get("linkedin", ""),
                notes=row.get("notes", ""),
                assigned_user=tab_name,
                custom_fields=row.get("custom_fields", {}),
                discovery_source="google_sheet",
            )
            for field in BOOL_FIELDS:
                if row.get(field) is True:
                    setattr(new_lead, field, True)
            await db.leads.insert_one(new_lead.to_dict())

        count += 1

    return count


def _read_sheet_tab(creds: dict, tab_name: str) -> list[dict]:
    """Read all data rows from the named tab. Returns list of field dicts."""
    gc = _build_gspread_client(creds["service_account_json"])
    spreadsheet = gc.open_by_key(creds["spreadsheet_id"])

    try:
        worksheet = spreadsheet.worksheet(tab_name)
    except Exception:
        return []

    all_values = worksheet.get_all_values()
    if len(all_values) < 2:
        return []

    headers = [h.strip().lower().replace(" ", "_") for h in all_values[0]]

    rows = []
    for row in all_values[1:]:
        row_dict: dict[str, Any] = {}
        custom_fields: dict[str, Any] = {}
        
        # 1. Map standard columns by index
        for i, (col_letter, field) in enumerate(SHEET_COLUMNS):
            if i < len(row):
                cell = row[i].strip()
                if field in BOOL_FIELDS:
                    row_dict[field] = _sheet_to_bool(cell)
                else:
                    row_dict[field] = cell
            else:
                row_dict[field] = False if field in BOOL_FIELDS else ""
                
        # 2. Map all other/custom columns by header name
        for i in range(len(row)):
            if i < len(headers):
                header = headers[i]
                is_standard = False
                for col_letter, field in SHEET_COLUMNS:
                    if field == header:
                        is_standard = True
                        break
                if not is_standard and header:
                    custom_fields[header] = row[i].strip()
                    
        row_dict["custom_fields"] = custom_fields
        if row_dict.get("email") or row_dict.get("name"):
            rows.append(row_dict)
    return rows


# ─────────────────────────────────────────────────────────────────────────────
# Background sync loop (called from main.py)
# ─────────────────────────────────────────────────────────────────────────────


async def sync_all_users() -> None:
    """Pull updates from Google Sheets for all users with configured sheets."""
    db = await get_database()
    docs = await db.user_integrations.find(
        {"provider": "google_sheets", "is_active": True}
    ).to_list(length=100)

    for doc in docs:
        user_id = doc.get("user_id")
        if user_id:
            try:
                count = await pull_sheet_updates(user_id)
                if count > 0:
                    logger.info("Sheet sync: pulled %d rows for user %s", count, user_id)
            except Exception as exc:
                logger.error("Sheet sync error for user %s: %s", user_id, exc)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


async def _get_sheet_creds(user_id: str) -> dict | None:
    """Retrieve decrypted Google Sheets credentials for a user."""
    from app.services.integrations_service import get_integration
    creds = await get_integration(user_id, "google_sheets")
    if not creds or not creds.get("spreadsheet_id") or not creds.get("service_account_json"):
        return None
    return creds


async def _get_user_display_name(db, user_id: str) -> str:
    """Get the user's display_name to use as sheet tab name."""
    user = await db.users.find_one({"id": user_id})
    if user:
        return user.get("display_name") or user.get("name", "")
    return ""
