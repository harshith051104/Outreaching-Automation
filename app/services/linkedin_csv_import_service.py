"""
LinkedIn CSV Import Service.

Handles importing LinkedIn leads from CSV files for outreach campaigns.
Supports batch connection requests and DMs.
"""

import csv
import io
import logging
import re
from datetime import datetime, timezone
from typing import Any, Optional

from app.config.mongodb_config import get_database
from app.utils.id_generator import generate_id

logger = logging.getLogger(__name__)

LINKEDIN_URL_PATTERNS = [
    r"https?://(?:www\.)?linkedin\.com/in/[a-zA-Z0-9_-]+/?",
    r"linkedin\.com/in/[a-zA-Z0-9_-]+/?",
]


def is_valid_linkedin_url(url: str) -> bool:
    """Check if a string is a valid LinkedIn profile URL."""
    if not url:
        return False
    for pattern in LINKEDIN_URL_PATTERNS:
        if re.search(pattern, url, re.IGNORECASE):
            return True
    return False


def normalize_linkedin_url(url: str) -> str:
    """Normalize a LinkedIn URL to a consistent format."""
    if not url:
        return ""
    url = url.strip()
    if not url.startswith("http"):
        url = "https://" + url
    match = re.search(r"linkedin\.com/in/[a-zA-Z0-9_-]+", url, re.IGNORECASE)
    if match:
        return f"https://{match.group(0)}"
    return url


def extract_linkedin_urls_from_text(text: str) -> list[str]:
    """Extract all LinkedIn URLs from a text field."""
    urls = []
    for pattern in LINKEDIN_URL_PATTERNS:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            normalized = normalize_linkedin_url(match)
            if normalized and normalized not in urls:
                urls.append(normalized)
    return urls


def parse_csv_content(csv_content: bytes | str) -> list[dict[str, Any]]:
    """
    Parse CSV content and return list of row dictionaries.
    
    Handles various encodings and common CSV formats.
    """
    if isinstance(csv_content, bytes):
        for encoding in ['utf-8', 'latin-1', 'cp1252', 'utf-16']:
            try:
                csv_content = csv_content.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
    
    reader = csv.DictReader(io.StringIO(csv_content))
    rows = []
    for row in reader:
        cleaned_row = {k.strip().lower().replace(" ", "_"): v.strip() if v else "" 
                       for k, v in row.items()}
        rows.append(cleaned_row)
    return rows


def extract_lead_fields(row: dict[str, Any]) -> dict[str, Any]:
    """
    Extract lead fields from a CSV row.
    
    Supports common column name variations for LinkedIn and email outreach leads.
    """
    lead = {}
    
    email_fields = ["email", "email_address", "email_addresses", "mail", "e-mail"]
    for field in email_fields:
        if field in row and row[field]:
            email_val = row[field].strip().lower()
            if "@" in email_val:
                lead["email"] = email_val
                break
    
    # Advanced Name extraction supporting separate first_name/last_name fields or single full name field
    first_name = ""
    last_name = ""
    
    first_name_fields = ["first_name", "firstname", "given_name"]
    last_name_fields = ["last_name", "lastname", "family_name"]
    
    for f in first_name_fields:
        if f in row and row[f]:
            first_name = row[f].strip()
            break
            
    for f in last_name_fields:
        if f in row and row[f]:
            last_name = row[f].strip()
            break
            
    lead["first_name"] = first_name
    lead["last_name"] = last_name
    
    full_name_fields = ["name", "full_name", "fullname", "contact_name", "person_name"]
    full_name = ""
    for field in full_name_fields:
        if field in row and row[field]:
            full_name = row[field].strip()
            break
            
    if not full_name:
        full_name = f"{first_name} {last_name}".strip()
        
    if full_name:
        lead["name"] = full_name
    elif "email" in lead:
        lead["name"] = lead["email"]
    
    company_fields = ["company", "company_name", "organization", "org", "company_name_1"]
    for field in company_fields:
        if field in row and row[field]:
            lead["company"] = row[field].strip()
            break
    
    role_fields = ["role", "job_title", "title", "position", "job_title_1", "headline"]
    for field in role_fields:
        if field in row and row[field]:
            lead["role"] = row[field].strip()
            break
    
    linkedin_fields = ["linkedin", "linkedin_url", "linkedin_profile", "linkedin_profile_url", "profile_url", "profile", "url", "linkedin_link"]
    for field in linkedin_fields:
        if field in row and row[field]:
            potential_url = row[field].strip()
            if is_valid_linkedin_url(potential_url):
                normalized = normalize_linkedin_url(potential_url)
                lead["linkedin_url"] = normalized
                lead["linkedin"] = normalized
                break
    
    website_fields = ["website", "company_website", "company_url", "site"]
    for field in website_fields:
        if field in row and row[field]:
            lead["website"] = row[field].strip()
            break
            
    focus_fields = ["focus", "investor_focus", "investorfocus", "investor focus"]
    for field in focus_fields:
        if field in row and row[field]:
            lead["focus"] = row[field].strip()
            break
    
    notes_fields = ["notes", "note", "description", "about", "comments", "备注"]
    for field in notes_fields:
        if field in row and row[field]:
            lead["notes"] = row[field].strip()
            break
    
    return lead


async def import_leads_from_csv(
    csv_content: bytes | str,
    user_id: str,
    campaign_id: Optional[str] = None,
    create_leads: bool = True,
) -> dict[str, Any]:
    """
    Import leads from CSV content.
    
    Args:
        csv_content: Raw CSV content as bytes or string
        user_id: ID of the user importing the leads
        campaign_id: Optional campaign ID to associate leads with
        create_leads: Whether to create lead records in the database
        
    Returns:
        Dictionary with import results:
        - total_rows: Total number of rows parsed
        - valid_leads: Number of rows with valid LinkedIn URLs or email addresses
        - leads_created: Number of new leads created
        - leads_updated: Number of existing leads updated
        - errors: List of error messages
        - leads: List of extracted lead data
    """
    rows = parse_csv_content(csv_content)
    
    total_rows = len(rows)
    valid_leads = 0
    leads_created = 0
    leads_updated = 0
    errors = []
    extracted_leads = []
    
    db = await get_database()
    
    for idx, row in enumerate(rows):
        try:
            lead_data = extract_lead_fields(row)
            
            # A lead is valid if it has either a LinkedIn URL OR a valid email address
            if not lead_data.get("linkedin_url") and not lead_data.get("email"):
                continue
            
            valid_leads += 1
            lead_data["user_id"] = user_id
            lead_data["discovery_source"] = "csv_import"
            
            if campaign_id:
                lead_data["campaign_id"] = campaign_id
            
            if create_leads:
                # Dynamically construct existing lead lookup conditions
                or_conditions = []
                if lead_data.get("linkedin_url"):
                    or_conditions.append({"linkedin": lead_data["linkedin_url"]})
                    or_conditions.append({"linkedin_url": lead_data["linkedin_url"]})
                if lead_data.get("email"):
                    or_conditions.append({"email": lead_data["email"]})
                
                existing = None
                if or_conditions:
                    # Filter matching lead in this campaign or user context
                    existing_query = {"user_id": user_id, "$or": or_conditions}
                    if campaign_id:
                        existing_query["campaign_id"] = campaign_id
                    existing = await db.leads.find_one(existing_query)
                
                if existing:
                    await db.leads.update_one(
                        {"_id": existing["_id"]},
                        {"$set": {
                            **lead_data,
                            "updated_at": datetime.now(timezone.utc)
                        }}
                    )
                    leads_updated += 1
                    lead_data["id"] = existing["id"]
                else:
                    lead_id = generate_id()
                    lead_data["id"] = lead_id
                    lead_data["status"] = "new"
                    lead_data["created_at"] = datetime.now(timezone.utc)
                    lead_data["updated_at"] = datetime.now(timezone.utc)
                    await db.leads.insert_one(lead_data)
                    leads_created += 1
            else:
                lead_data["id"] = generate_id()
            
            extracted_leads.append(lead_data)
            
        except Exception as exc:
            errors.append(f"Row {idx + 1}: {str(exc)}")
            logger.warning("Error processing row %d: %s", idx + 1, exc)
            
    # Keep campaign lead counters in sync
    if create_leads and campaign_id and leads_created > 0:
        await db.campaigns.update_one(
            {"id": campaign_id}, {"$inc": {"total_leads": leads_created}}
        )
    
    return {
        "total_rows": total_rows,
        "valid_leads": valid_leads,
        "leads_created": leads_created,
        "leads_updated": leads_updated,
        "errors": errors,
        "leads": extracted_leads,
    }


async def get_linkedin_leads_for_outreach(
    user_id: str,
    campaign_id: Optional[str] = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """
    Get LinkedIn leads ready for outreach.
    
    Args:
        user_id: User ID
        campaign_id: Optional campaign ID to filter by
        limit: Maximum number of leads to return
        
    Returns:
        List of lead dictionaries with LinkedIn URLs
    """
    db = await get_database()
    
    query = {
        "user_id": user_id,
        "$or": [
            {"linkedin": {"$exists": True, "$ne": ""}},
            {"linkedin_url": {"$exists": True, "$ne": ""}}
        ]
    }
    
    if campaign_id:
        query["campaign_id"] = campaign_id
    
    cursor = db.leads.find(
        query,
        {"_id": 0}
    ).sort("created_at", -1).limit(limit)
    
    return await cursor.to_list(length=limit)


async def bulk_create_linkedin_actions(
    user_id: str,
    lead_ids: list[str],
    action_type: str,
    message: Optional[str] = None,
    note: Optional[str] = None,
) -> dict[str, Any]:
    """
    Create bulk LinkedIn actions for multiple leads.
    
    Args:
        user_id: User ID
        lead_ids: List of lead IDs to create actions for
        action_type: Type of action (connection_request, send_message)
        message: Optional message for the action
        note: Optional note for connection request
        
    Returns:
        Dictionary with creation results
    """
    db = await get_database()
    
    now = datetime.now(timezone.utc)
    created_count = 0
    errors = []
    
    for lead_id in lead_ids:
        try:
            lead = await db.leads.find_one({"id": lead_id, "user_id": user_id})
            if not lead:
                errors.append(f"Lead {lead_id} not found")
                continue
            
            linkedin_url = lead.get("linkedin") or lead.get("linkedin_url", "")
            if not linkedin_url:
                errors.append(f"Lead {lead_id} has no LinkedIn URL")
                continue
            
            existing = await db.linkedin_actions.find_one({
                "user_id": user_id,
                "lead_id": lead_id,
                "action_type": action_type,
                "status": "pending"
            })
            if existing:
                continue
            
            action_doc = {
                "id": generate_id(),
                "user_id": user_id,
                "lead_id": lead_id,
                "linkedin_url": linkedin_url,
                "action_type": action_type,
                "message": message or "",
                "note": note or "",
                "status": "pending",
                "created_at": now,
                "updated_at": now,
            }
            
            await db.linkedin_actions.insert_one(action_doc)
            created_count += 1
            
        except Exception as exc:
            errors.append(f"Lead {lead_id}: {str(exc)}")
            logger.warning("Error creating action for lead %s: %s", lead_id, exc)
    
    return {
        "requested": len(lead_ids),
        "created": created_count,
        "errors": errors,
    }