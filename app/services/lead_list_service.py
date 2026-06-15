"""
Lead list and label service.

Manages lead lists for organizing contacts and labels for categorization.
"""

from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import HTTPException, status

from app.config.mongodb_config import get_database
from app.utils.id_generator import generate_id


async def create_lead_list(user_id: str, name: str, description: str = "") -> dict:
    """Create a new lead list."""
    db = await get_database()

    now = datetime.now(timezone.utc)
    list_doc = {
        "id": generate_id(),
        "user_id": user_id,
        "name": name.strip(),
        "description": description,
        "created_at": now,
        "updated_at": now,
    }

    await db.lead_lists.insert_one(list_doc)
    list_doc.pop("_id", None)
    return list_doc


async def get_lead_lists(user_id: str) -> list:
    """Get all lead lists for a user with lead counts."""
    db = await get_database()
    cursor = db.lead_lists.find({"user_id": user_id}, {"_id": 0}).sort("created_at", -1)
    lists = await cursor.to_list(length=100)

    for lst in lists:
        count = await db.leads.count_documents({"list_id": lst["id"]})
        lst["total_leads"] = count

    return lists


async def get_lead_list(list_id: str, user_id: str) -> dict:
    """Get a single lead list."""
    db = await get_database()
    lst = await db.lead_lists.find_one({"id": list_id, "user_id": user_id}, {"_id": 0})
    if not lst:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead list not found.",
        )

    count = await db.leads.count_documents({"list_id": list_id})
    lst["total_leads"] = count
    return lst


async def update_lead_list(list_id: str, user_id: str, data: dict) -> dict:
    """Update a lead list."""
    db = await get_database()
    data["updated_at"] = datetime.now(timezone.utc)

    result = await db.lead_lists.update_one(
        {"id": list_id, "user_id": user_id},
        {"$set": data},
    )
    if result.matched_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead list not found.",
        )

    return await get_lead_list(list_id, user_id)


async def delete_lead_list(list_id: str, user_id: str) -> bool:
    """Delete a lead list (leads are not deleted, only unlinked)."""
    db = await get_database()

    await db.leads.update_many(
        {"list_id": list_id, "user_id": user_id},
        {"$set": {"list_id": None}},
    )

    result = await db.lead_lists.delete_one({"id": list_id, "user_id": user_id})
    return result.deleted_count > 0


async def create_lead_label(
    user_id: str, name: str, color: str = "#3B82F6", description: str = ""
) -> dict:
    """Create a new lead label."""
    db = await get_database()

    now = datetime.now(timezone.utc)
    label_doc = {
        "id": generate_id(),
        "user_id": user_id,
        "name": name.strip(),
        "color": color,
        "description": description,
        "created_at": now,
    }

    await db.lead_labels.insert_one(label_doc)
    label_doc.pop("_id", None)
    return label_doc


async def get_lead_labels(user_id: str) -> list:
    """Get all lead labels for a user."""
    db = await get_database()
    cursor = db.lead_labels.find({"user_id": user_id}, {"_id": 0}).sort("created_at", -1)
    return await cursor.to_list(length=100)


async def get_lead_label(label_id: str, user_id: str) -> Optional[dict]:
    """Get a single lead label."""
    db = await get_database()
    return await db.lead_labels.find_one({"id": label_id, "user_id": user_id}, {"_id": 0})


async def update_lead_label(label_id: str, user_id: str, data: dict) -> Optional[dict]:
    """Update a lead label."""
    db = await get_database()
    result = await db.lead_labels.update_one(
        {"id": label_id, "user_id": user_id},
        {"$set": data},
    )
    if result.matched_count == 0:
        return None
    return await get_lead_label(label_id, user_id)


async def delete_lead_label(label_id: str, user_id: str) -> bool:
    """Delete a lead label."""
    db = await get_database()

    await db.leads.update_many(
        {"labels": label_id, "user_id": user_id},
        {"$pull": {"labels": label_id}},
    )

    result = await db.lead_labels.delete_one({"id": label_id, "user_id": user_id})
    return result.deleted_count > 0


async def assign_label_to_leads(label_id: str, lead_ids: list[str], user_id: str) -> int:
    """Assign a label to multiple leads. Returns count of updated leads."""
    db = await get_database()
    result = await db.leads.update_many(
        {"id": {"$in": lead_ids}, "user_id": user_id},
        {"$addToSet": {"labels": label_id}},
    )
    return result.modified_count


async def remove_label_from_leads(label_id: str, lead_ids: list[str], user_id: str) -> int:
    """Remove a label from multiple leads. Returns count of updated leads."""
    db = await get_database()
    result = await db.leads.update_many(
        {"id": {"$in": lead_ids}, "user_id": user_id},
        {"$pull": {"labels": label_id}},
    )
    return result.modified_count


async def add_to_block_list(user_id: str, value: str, reason: str = "") -> dict:
    """Add an email or domain to the block list."""
    db = await get_database()

    existing = await db.block_list.find_one({"user_id": user_id, "value": value.lower()})
    if existing:
        return {"id": existing["id"], "value": value, "status": "already_exists"}

    now = datetime.now(timezone.utc)
    entry_doc = {
        "id": generate_id(),
        "user_id": user_id,
        "value": value.lower().strip(),
        "reason": reason,
        "created_at": now,
    }

    await db.block_list.insert_one(entry_doc)
    entry_doc.pop("_id", None)
    return entry_doc


async def get_block_list(user_id: str) -> list:
    """Get all block list entries for a user."""
    db = await get_database()
    cursor = db.block_list.find({"user_id": user_id}, {"_id": 0}).sort("created_at", -1)
    return await cursor.to_list(length=1000)


async def remove_from_block_list(entry_id: str, user_id: str) -> bool:
    """Remove an entry from the block list."""
    db = await get_database()
    result = await db.block_list.delete_one({"id": entry_id, "user_id": user_id})
    return result.deleted_count > 0


async def is_blocked(user_id: str, email: str) -> bool:
    """Check if an email or its domain is blocked."""
    db = await get_database()
    email_lower = email.lower()
    domain = email_lower.split("@")[-1] if "@" in email_lower else ""

    query = {
        "user_id": user_id,
        "$or": [
            {"value": email_lower},
            {"value": domain},
        ],
    }
    count = await db.block_list.count_documents(query)
    return count > 0