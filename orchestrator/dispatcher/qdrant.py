import logging
from typing import Dict, Any
from app.services.qdrant_service import search_similar, store_document

logger = logging.getLogger(__name__)

async def qdrant_search(inputs: Dict[str, Any], context: Dict[str, Any]) -> Any:
    results = await search_similar(
        collection_name=inputs.get("collection", "leads"),
        query=inputs.get("query", ""),
        limit=inputs.get("limit", 3),
    )
    return results

async def qdrant_upsert(inputs: Dict[str, Any], context: Dict[str, Any]) -> Any:
    collection = inputs.get("collection", "leads")
    if "documents" in inputs:
        docs = inputs["documents"]
        if not isinstance(docs, list):
            docs = [docs] if docs else []
        for doc in docs:
            if isinstance(doc, dict):
                doc_id = doc.get("id") or doc.get("_id")
                if not doc_id:
                    continue
                text = f"Lead: {doc.get('name')}, Role: {doc.get('role')}, Company: {doc.get('company')}"
                metadata = {
                    "user_id": doc.get("user_id"),
                    "campaign_id": doc.get("campaign_id"),
                    "lead_quality_score": doc.get("lead_quality_score")
                }
                await store_document(
                    collection_name=collection,
                    doc_id=str(doc_id),
                    text=text,
                    metadata=metadata
                )
        return {"success": True, "count": len(docs)}
    else:
        doc_id = inputs.get("doc_id", "")
        text = inputs.get("text", "")
        metadata = inputs.get("metadata", {})
        await store_document(
            collection_name=collection,
            doc_id=doc_id,
            text=text,
            metadata=metadata,
        )
        return {"success": True}

def register_qdrant_tools(dispatcher: Any) -> None:
    dispatcher.register("qdrant_search", qdrant_search)
    dispatcher.register("qdrant_upsert", qdrant_upsert)
