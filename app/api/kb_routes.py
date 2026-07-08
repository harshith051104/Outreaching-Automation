"""
AI RAG Knowledge Base Router.
ponytail: Simple Mongo + Qdrant wrapper.
"""

from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from app.auth.dependencies import get_current_user
from app.config.mongodb_config import get_database
from app.services.qdrant_service import store_document, search_similar
from app.utils.id_generator import generate_id

router = APIRouter(prefix="/kb", tags=["AI Knowledge Base"])


class KBDocumentCreate(BaseModel):
    title: str
    content: str
    category: str = "general"  # e.g., overview, patent, deck, Technical


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_kb_document(
    data: KBDocumentCreate,
    current_user: dict = Depends(get_current_user)
):
    """
    Upload a company knowledge base document (e.g. patents, whitepapers, specs).
    Auto-embeds and stores the content in Qdrant for semantic RAG lookup.
    """
    db = await get_database()
    doc_id = generate_id()
    now = datetime.now(timezone.utc)
    
    doc = {
        "id": doc_id,
        "user_id": current_user["id"],
        "title": data.title,
        "content": data.content,
        "category": data.category,
        "created_at": now,
        "updated_at": now,
    }
    
    # Store in MongoDB
    await db.kb_documents.insert_one(doc)
    
    # Store in Qdrant
    text_to_embed = f"Title: {data.title}\nCategory: {data.category}\nContent:\n{data.content}"
    await store_document(
        collection_name="kb_documents",
        doc_id=doc_id,
        text=text_to_embed,
        metadata={
            "user_id": current_user["id"],
            "title": data.title,
            "category": data.category,
            "created_at": now.isoformat()
        }
    )
    
    doc.pop("_id", None)
    return doc


@router.get("")
async def list_kb_documents(
    category: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user)
):
    """
    List all knowledge base documents.
    """
    db = await get_database()
    query = {"user_id": current_user["id"]}
    if category:
        query["category"] = category
        
    cursor = db.kb_documents.find(query, {"_id": 0}).sort("created_at", -1)
    return await cursor.to_list(length=100)


@router.delete("/{doc_id}")
async def delete_kb_document(
    doc_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Delete a knowledge base document from MongoDB and Qdrant.
    """
    db = await get_database()
    res = await db.kb_documents.delete_one({"id": doc_id, "user_id": current_user["id"]})
    if res.deleted_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found."
        )
        
    # ponytail: Qdrant deletion is YAGNI/optional but good practice.
    # Qdrant client delete can be bypassed if qdrant is offline.
    try:
        from app.config.qdrant_config import get_qdrant_client
        client = get_qdrant_client()
        client.delete(collection_name="kb_documents", points_selector=[doc_id])
    except Exception:
        pass
        
    return {"status": "deleted", "doc_id": doc_id}


@router.get("/search")
async def search_kb(
    q: str = Query(..., min_length=1),
    limit: int = Query(3, ge=1, le=10),
    current_user: dict = Depends(get_current_user)
):
    """
    Perform a semantic similarity search across knowledge base documents.
    """
    results = await search_similar("kb_documents", query=q, limit=limit)
    # Filter by user ownership (tenant isolation)
    user_results = [
        r for r in results
        if r.get("metadata", {}).get("user_id") == current_user["id"]
    ]
    return user_results
