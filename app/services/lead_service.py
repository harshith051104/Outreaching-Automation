"""
Lead management service layer.

Handles lead CRUD, bulk CSV imports, engagement scoring, and
engagement history retrieval.
"""

from datetime import datetime, timezone

from fastapi import HTTPException, status

from app.config.mongodb_config import get_database
from app.schemas.lead import LeadCreate
from app.utils.id_generator import generate_id
from app.utils.csv_parser import parse_leads_csv
from app.utils.validators import validate_email_format


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


async def import_leads_csv(
    campaign_id: str, user_id: str, file_content: bytes
) -> dict:
    """
    Parse a CSV file, validate each row, and bulk-insert leads.

    Returns summary with imported count, skipped count, and errors.
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

    rows = parse_leads_csv(file_content)

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
        full_name = f"{first_name} {last_name}".strip() or email

        lead_doc = {
            "id": generate_id(),
            "user_id": user_id,
            "campaign_id": campaign_id,
            "name": full_name,
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "company": (row.get("company") or "").strip(),
            "role": (row.get("title") or row.get("job_title") or "").strip(),
            "website": (row.get("website") or row.get("url") or "").strip(),
            "status": "new",
            "score": 0.0,
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