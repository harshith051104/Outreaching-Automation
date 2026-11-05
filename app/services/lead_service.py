"""
Lead management service layer.

Handles lead CRUD, bulk CSV imports, engagement scoring, and
engagement history retrieval.
"""

from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status
import httpx
import logging

from app.config.mongodb_config import get_database
from app.schemas.lead import LeadCreate
from app.utils.id_generator import generate_id
from app.utils.csv_parser import (
    parse_leads_file,
    extract_spreadsheet_id,
    inspect_xlsx_sheets,
    parse_leads_xlsx_sheets,
    normalize_column_name,
)
from app.utils.validators import validate_email_format

logger = logging.getLogger(__name__)


async def create_lead(user_id: str, data: LeadCreate) -> dict:
    """Create a single lead and increment the campaign lead count."""
    db = await get_database()

    if not validate_email_format(data.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid email format: {data.email}",
        )

    existing = await db.leads.find_one(
        {"campaign_id": data.campaign_id, "email": data.email.lower()}
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Lead with this email already exists in the campaign.",
        )

    now = datetime.now(timezone.utc)
    full_name = data.name.strip()
    parts = full_name.split(None, 1)
    first_name = parts[0] if parts else ""
    last_name = parts[1] if len(parts) > 1 else ""

    lead_doc = {
        "id": generate_id(),
        "user_id": user_id,
        "campaign_id": data.campaign_id,
        "name": full_name,
        "first_name": first_name,
        "last_name": last_name,
        "email": data.email.lower().strip(),
        "company": getattr(data, "company", "") or "",
        "role": getattr(data, "role", "") or "",
        "website": getattr(data, "website", "") or "",
        "focus": getattr(data, "focus", "") or "",
        "custom_fields": getattr(data, "custom_fields", {}) or {},
        "status": "new",
        "score": 0.0,
        "research_data": {},
        "personalization_data": {},
        "created_at": now,
        "updated_at": now,
    }

    await db.leads.insert_one(lead_doc)

    await db.campaigns.update_one(
        {"id": data.campaign_id}, {"$inc": {"total_leads": 1}}
    )

    lead_doc.pop("_id", None)
    return lead_doc


async def get_leads(
    campaign_id: str, user_id: str, skip: int = 0, limit: int = 50
) -> list:
    """List leads for a campaign with pagination."""
    db = await get_database()
    
    # Self-healing: if campaign_id is a UUID, check if we need to migrate leads matching campaign name
    if campaign_id and len(campaign_id) == 36:
        campaign = await db.campaigns.find_one({"id": campaign_id, "user_id": user_id})
        if campaign:
            camp_name = campaign.get("name")
            if camp_name:
                import re
                name_query = {
                    "user_id": user_id,
                    "campaign_id": {"$regex": f"^{re.escape(camp_name)}$", "$options": "i"}
                }
                matching_count = await db.leads.count_documents(name_query)
                if matching_count > 0:
                    await db.leads.update_many(
                        name_query,
                        {"$set": {"campaign_id": campaign_id, "updated_at": datetime.now(timezone.utc)}}
                    )
                    total_leads = await db.leads.count_documents({"campaign_id": campaign_id})
                    await db.campaigns.update_one(
                        {"id": campaign_id},
                        {"$set": {"total_leads": total_leads}}
                    )

    query: dict = {"user_id": user_id}
    if campaign_id:
        query["campaign_id"] = campaign_id

    cursor = (
        db.leads.find(query, {"_id": 0})
        .sort("created_at", -1)
        .skip(skip)
        .limit(limit)
    )
    return await cursor.to_list(length=limit)


async def get_lead(lead_id: str, user_id: str) -> dict:
    """Get a single lead by id, verifying ownership."""
    db = await get_database()
    lead = await db.leads.find_one(
        {"id": lead_id, "user_id": user_id}, {"_id": 0}
    )
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead not found.",
        )
    return lead


async def update_lead(lead_id: str, user_id: str, data: dict) -> dict:
    """Update a lead's mutable fields."""
    db = await get_database()

    data["updated_at"] = datetime.now(timezone.utc)

    result = await db.leads.update_one(
        {"id": lead_id, "user_id": user_id}, {"$set": data}
    )
    if result.matched_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead not found.",
        )

    return await get_lead(lead_id, user_id)


async def delete_lead(lead_id: str, user_id: str) -> None:
    """Delete a lead and decrement the campaign lead count."""
    db = await get_database()

    lead = await db.leads.find_one({"id": lead_id, "user_id": user_id})
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead not found.",
        )

    await db.leads.delete_one({"id": lead_id, "user_id": user_id})

    await db.campaigns.update_one(
        {"id": lead["campaign_id"]}, {"$inc": {"total_leads": -1}}
    )


async def import_parsed_lead_rows(
    campaign_id: str,
    user_id: str,
    rows: list[dict[str, Any]],
    source_name: str = "leads",
) -> dict:
    """
    Validate and bulk-insert a list of pre-parsed lead dictionaries.
    """
    db = await get_database()

    campaign = await db.campaigns.find_one(
        {"id": campaign_id, "user_id": user_id}
    )
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found.",
        )

    imported = 0
    skipped = 0
    errors: list[str] = []
    now = datetime.now(timezone.utc)

    for idx, row in enumerate(rows, start=1):
        email = (row.get("email") or "").lower().strip()
        if not email:
            errors.append(f"Row {idx}: missing email")
            skipped += 1
            continue

        if not validate_email_format(email):
            errors.append(f"Row {idx}: invalid email '{email}'")
            skipped += 1
            continue

        existing = await db.leads.find_one(
            {"campaign_id": campaign_id, "email": email}
        )
        if existing:
            skipped += 1
            continue

        first_name = (row.get("first_name") or "").strip()
        last_name = (row.get("last_name") or "").strip()

        full_name = ""
        full_name_fields = [
            "name", "full_name", "fullname", "contact_name", "person_name",
            "investor's_name", "investors_name", "investor_name"
        ]
        for f in full_name_fields:
            if f in row and row[f]:
                full_name = str(row[f]).strip()
                break

        if not first_name and full_name:
            parts = full_name.split(None, 1)
            first_name = parts[0]
            if not last_name and len(parts) > 1:
                last_name = parts[1]

        if not full_name:
            full_name = f"{first_name} {last_name}".strip() or email

        role = (row.get("title") or row.get("job_title") or "").strip()
        website = (row.get("website") or row.get("url") or "").strip()
        focus = (row.get("focus") or "").strip()
        phone = (row.get("phone") or "").strip()
        linkedin_url = (row.get("linkedin_url") or "").strip()
        industry = (row.get("industry") or "").strip()

        standard_keys = {
            "email", "first_name", "last_name", "company", "title", "job_title", 
            "website", "url", "focus", "phone", "linkedin_url", "linkedin", "industry",
            "name", "full_name", "fullname", "contact_name", "person_name",
            "investor's_name", "investors_name", "investor_name", "_sheet_source"
        }

        custom_fields = {}
        for k, v in row.items():
            if k and k not in standard_keys and k.strip():
                val_str = str(v).strip()
                if val_str:
                    custom_fields[k] = val_str

        if row.get("_sheet_source"):
            custom_fields["sheet_tab"] = str(row["_sheet_source"])

        lead_doc = {
            "id": generate_id(),
            "user_id": user_id,
            "campaign_id": campaign_id,
            "name": full_name,
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "company": (row.get("company") or "").strip(),
            "role": role,
            "website": website,
            "focus": focus,
            "phone": phone,
            "linkedin_url": linkedin_url,
            "industry": industry,
            "status": "new",
            "score": 0.0,
            "custom_fields": custom_fields,
            "research_data": {},
            "personalization_data": {},
            "created_at": now,
            "updated_at": now,
        }
        await db.leads.insert_one(lead_doc)
        imported += 1

    if imported > 0:
        await db.campaigns.update_one(
            {"id": campaign_id}, {"$inc": {"total_leads": imported}}
        )

    return {
        "campaign_id": campaign_id,
        "imported": imported,
        "skipped": skipped,
        "errors": errors[:50],
    }


async def import_leads_csv(
    campaign_id: str, user_id: str, file_content: bytes, filename: str = "leads.csv"
) -> dict:
    """
    Parse a lead file (CSV, Excel, or PDF), validate each row, and bulk-insert leads.
    """
    rows = await parse_leads_file(file_content, filename)
    return await import_parsed_lead_rows(campaign_id, user_id, rows, filename)


async def fetch_google_sheet_worksheets(url: str, user_id: str) -> dict:
    """
    Inspect a Google Spreadsheet URL and list all available worksheets/tabs,
    their approximate row counts, and whether email columns are detected.
    """
    spreadsheet_id = extract_spreadsheet_id(url)
    export_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=xlsx"
    xlsx_bytes = None

    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        try:
            resp = await client.get(export_url)
            is_html_or_login = (
                "accounts.google.com" in str(resp.url)
                or "html" in resp.headers.get("content-type", "").lower()
                or resp.status_code != 200
                or len(resp.content) < 200
            )
            if not is_html_or_login:
                xlsx_bytes = resp.content
        except Exception as exc:
            logger.warning("Public export request failed for spreadsheet %s: %s", spreadsheet_id, exc)

    if xlsx_bytes:
        sheets_info = inspect_xlsx_sheets(xlsx_bytes)
        return {
            "spreadsheet_id": spreadsheet_id,
            "url": url,
            "sheets": sheets_info,
        }

    # Fallback to authenticated Google OAuth API if user connected Google Account
    try:
        from app.services.google_sheets_service import _get_google_credentials
        from googleapiclient.discovery import build
        import asyncio

        creds = await _get_google_credentials(user_id)

        def _call_api():
            service = build("sheets", "v4", credentials=creds, cache_discovery=False)
            meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
            sheets = []
            for s in meta.get("sheets", []):
                props = s.get("properties", {})
                title = props.get("title", "")
                grid = props.get("gridProperties", {})
                row_count = grid.get("rowCount", 0)
                try:
                    val_resp = service.spreadsheets().values().get(
                        spreadsheetId=spreadsheet_id, range=f"'{title}'!A1:Z3"
                    ).execute()
                    values = val_resp.get("values", [])
                    headers = [str(c).strip() for c in values[0]] if values else []
                    canonical = [normalize_column_name(h) for h in headers]
                    has_email = any(c == "email" for c in canonical)
                except Exception:
                    headers = []
                    has_email = False

                sheets.append({
                    "name": title,
                    "row_count": max(0, row_count - 1),
                    "headers": headers[:8],
                    "has_email": has_email,
                    "leads_count": max(0, row_count - 1) if has_email else 0,
                })
            return sheets

        sheets_info = await asyncio.to_thread(_call_api)
        return {
            "spreadsheet_id": spreadsheet_id,
            "url": url,
            "sheets": sheets_info,
        }
    except Exception as api_exc:
        logger.warning("Google API fallback failed for sheet %s: %s", spreadsheet_id, api_exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to access Google Sheet. Please ensure sharing is set to 'Anyone with the link can view' or connect your Google account in Settings.",
        )


async def import_google_sheet_leads(
    campaign_id: str,
    user_id: str,
    url: str,
    selected_sheets: list[str] | None = None,
) -> dict:
    """
    Import leads from a Google Spreadsheet, extracting data from one or more selected sheets.
    """
    spreadsheet_id = extract_spreadsheet_id(url)
    export_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=xlsx"
    xlsx_bytes = None

    async with httpx.AsyncClient(timeout=45.0, follow_redirects=True) as client:
        try:
            resp = await client.get(export_url)
            is_html_or_login = (
                "accounts.google.com" in str(resp.url)
                or "html" in resp.headers.get("content-type", "").lower()
                or resp.status_code != 200
                or len(resp.content) < 200
            )
            if not is_html_or_login:
                xlsx_bytes = resp.content
        except Exception as exc:
            logger.warning("Public export request failed for spreadsheet %s: %s", spreadsheet_id, exc)

    rows: list[dict[str, Any]] = []
    sheets_processed: list[str] = []

    if xlsx_bytes:
        rows = parse_leads_xlsx_sheets(xlsx_bytes, selected_sheets)
        sheets_processed = selected_sheets or [r.get("_sheet_source") for r in rows if r.get("_sheet_source")]
        sheets_processed = list(dict.fromkeys([s for s in sheets_processed if s]))
    else:
        # Fallback to Google Sheets API
        try:
            from app.services.google_sheets_service import _get_google_credentials
            from googleapiclient.discovery import build
            import asyncio

            creds = await _get_google_credentials(user_id)

            def _call_api_values():
                service = build("sheets", "v4", credentials=creds, cache_discovery=False)
                meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
                all_sheet_titles = [s.get("properties", {}).get("title", "") for s in meta.get("sheets", [])]

                target_titles = []
                if selected_sheets:
                    for req in selected_sheets:
                        req_clean = req.strip().lower()
                        for title in all_sheet_titles:
                            if title.strip().lower() == req_clean:
                                if title not in target_titles:
                                    target_titles.append(title)
                                break
                else:
                    target_titles = all_sheet_titles

                fetched_rows = []
                for title in target_titles:
                    try:
                        val_resp = service.spreadsheets().values().get(
                            spreadsheetId=spreadsheet_id, range=f"'{title}'"
                        ).execute()
                        values = val_resp.get("values", [])
                        if not values or len(values) < 2:
                            continue

                        header_idx = 0
                        h_candidates = [str(c).strip() for c in values[0] if c]
                        if not any("email" in normalize_column_name(h) for h in h_candidates) and len(values) > 1:
                            h_candidates_1 = [str(c).strip() for c in values[1] if c]
                            if any("email" in normalize_column_name(h) for h in h_candidates_1):
                                header_idx = 1
                            elif len(values) > 2:
                                h_candidates_2 = [str(c).strip() for c in values[2] if c]
                                if any("email" in normalize_column_name(h) for h in h_candidates_2):
                                    header_idx = 2

                        canonical = [
                            normalize_column_name(str(h).strip()) if h and str(h).strip() else ""
                            for h in values[header_idx]
                        ]
                        if not any(f == "email" for f in canonical):
                            continue

                        for r in values[header_idx + 1:]:
                            row_dict = {}
                            for idx, field in enumerate(canonical):
                                if not field:
                                    continue
                                val = r[idx] if idx < len(r) else None
                                row_dict[field] = str(val).strip() if val is not None else ""
                            if not row_dict.get("email") or "@" not in row_dict["email"]:
                                continue
                            row_dict["_sheet_source"] = title
                            fetched_rows.append(row_dict)
                    except Exception as err:
                        logger.warning("Failed to fetch values for tab %s: %s", title, err)
                return fetched_rows, target_titles

            rows, sheets_processed = await asyncio.to_thread(_call_api_values)
        except Exception as api_exc:
            logger.warning("Google API fallback failed for sheet %s: %s", spreadsheet_id, api_exc)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to access Google Sheet. Please ensure sharing is set to 'Anyone with the link can view' or connect your Google account in Settings.",
            )

    result = await import_parsed_lead_rows(
        campaign_id=campaign_id,
        user_id=user_id,
        rows=rows,
        source_name=f"google_sheet_{spreadsheet_id}",
    )
    result["sheets_processed"] = sheets_processed
    return result


async def update_lead_score(lead_id: str, score_delta: float) -> dict:
    """Increment a lead's engagement score by score_delta."""
    db = await get_database()
    result = await db.leads.find_one_and_update(
        {"id": lead_id},
        {
            "$inc": {"engagement_score": score_delta},
            "$set": {"updated_at": datetime.now(timezone.utc)},
        },
        return_document=True,
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead not found.",
        )
    result.pop("_id", None)
    return result


async def get_lead_engagement(lead_id: str) -> dict:
    """
    Return all tracking events for a specific lead, grouped by type.
    """
    db = await get_database()

    events_cursor = db.tracking_events.find(
        {"lead_id": lead_id}, {"_id": 0}
    ).sort("timestamp", -1)
    events = await events_cursor.to_list(length=500)

    opens = [e for e in events if e.get("event_type") == "open"]
    clicks = [e for e in events if e.get("event_type") == "click"]
    replies = [e for e in events if e.get("event_type") == "reply"]

    return {
        "lead_id": lead_id,
        "total_events": len(events),
        "opens": len(opens),
        "clicks": len(clicks),
        "replies": len(replies),
        "events": events,
    }