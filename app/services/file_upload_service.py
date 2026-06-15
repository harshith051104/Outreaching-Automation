"""
File upload service.

Handles file uploads for the chatbot and email attachments.
"""

import os
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional

from app.config.mongodb_config import get_database
from app.utils.id_generator import generate_id

logger = logging.getLogger(__name__)

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


async def upload_file(
    user_id: str,
    file_content: bytes,
    filename: str,
    content_type: str = "application/octet-stream",
    max_size_mb: int = 50,
) -> dict:
    """
    Save an uploaded file and return its metadata.
    """
    file_size = len(file_content)
    if file_size > max_size_mb * 1024 * 1024:
        raise ValueError(f"File too large: {file_size / (1024 * 1024):.1f}MB (max {max_size_mb}MB)")
    
    file_id = generate_id()
    ext = os.path.splitext(filename)[1] if "." in filename else ""
    safe_filename = f"{file_id}{ext}"
    
    file_path = os.path.join(UPLOAD_DIR, safe_filename)
    with open(file_path, "wb") as f:
        f.write(file_content)
    
    file_size = len(file_content)
    
    db = await get_database()
    now = datetime.now(timezone.utc)
    
    file_doc = {
        "id": file_id,
        "user_id": user_id,
        "original_filename": filename,
        "stored_filename": safe_filename,
        "file_path": file_path,
        "content_type": content_type,
        "file_size": file_size,
        "download_url": f"/api/files/{file_id}/download",
        "created_at": now,
    }
    
    await db.uploaded_files.insert_one(file_doc)
    
    return {
        "id": file_id,
        "filename": filename,
        "file_size": file_size,
        "content_type": content_type,
        "file_path": file_path,
        "download_url": f"/api/files/{file_id}/download",
    }


async def get_user_files(user_id: str, limit: int = 50) -> list:
    """Get all uploaded files for a user."""
    db = await get_database()
    cursor = db.uploaded_files.find(
        {"user_id": user_id},
        {"_id": 0, "file_path": 0}
    ).sort("created_at", -1).limit(limit)
    
    return await cursor.to_list(length=limit)


async def get_file(file_id: str, user_id: str) -> Optional[dict]:
    """Get a single file by ID."""
    db = await get_database()
    return await db.uploaded_files.find_one(
        {"id": file_id, "user_id": user_id},
        {"_id": 0}
    )


async def delete_file(file_id: str, user_id: str) -> bool:
    """Delete an uploaded file."""
    db = await get_database()
    
    file_doc = await db.uploaded_files.find_one(
        {"id": file_id, "user_id": user_id}
    )
    if not file_doc:
        return False
    
    file_path = file_doc.get("file_path")
    if file_path and os.path.exists(file_path):
        os.remove(file_path)
    
    await db.uploaded_files.delete_one({"id": file_id})
    return True