import logging
from typing import Dict, Any
from app.config.mongodb_config import get_database
from app.utils.id_generator import generate_id

logger = logging.getLogger(__name__)

async def mongodb_query(inputs: Dict[str, Any], context: Dict[str, Any]) -> Any:
    db = await get_database()
    collection = db[inputs.get("collection", "")]
    # Note: query resolution is handled externally by the executor template resolver
    query = inputs.get("query", {})
    docs = await collection.find(query).to_list(length=inputs.get("limit", 50))
    return docs

async def mongodb_insert(inputs: Dict[str, Any], context: Dict[str, Any]) -> Any:
    db = await get_database()
    collection = db[inputs.get("collection", "")]

    if "documents" in inputs:
        docs = inputs["documents"]
        if not isinstance(docs, list):
            docs = [docs] if docs else []
        for doc in docs:
            if isinstance(doc, dict):
                if "id" not in doc:
                    doc["id"] = generate_id()
                doc.pop("_id", None)
        if docs:
            result = await collection.insert_many(docs)
            return {"ids": [str(x) for x in result.inserted_ids], "documents": docs, "count": len(docs)}
        return {"ids": [], "documents": [], "count": 0}
    else:
        doc = inputs.get("document", {})
        if isinstance(doc, dict):
            if "id" not in doc:
                doc["id"] = generate_id()
            doc.pop("_id", None)
            result = await collection.insert_one(doc)
            return {"id": str(result.inserted_id), "document": doc}
        return {"id": None, "document": {}}

async def mongodb_update(inputs: Dict[str, Any], context: Dict[str, Any]) -> Any:
    db = await get_database()
    collection = db[inputs.get("collection", "")]

    query = inputs.get("query", {})
    if isinstance(query, dict):
        query.pop("_id", None)
    update = inputs.get("update", {})
    if isinstance(update, dict):
        update.pop("_id", None)
        if not any(k.startswith("$") for k in update.keys()):
            update = {"$set": update}

    result = await collection.update_one(query, update)
    return {"matched_count": result.matched_count, "modified_count": result.modified_count}

async def mongodb_upsert(inputs: Dict[str, Any], context: Dict[str, Any]) -> Any:
    db = await get_database()
    collection = db[inputs.get("collection", "")]

    query = inputs.get("query", {})
    if isinstance(query, dict):
        query.pop("_id", None)
    doc = inputs.get("doc", {})
    if isinstance(doc, dict):
        doc.pop("_id", None)

    result = await collection.update_one(query, {"$set": doc}, upsert=True)
    return {"upserted_id": str(result.upserted_id) if result.upserted_id else None}

def register_mongodb_tools(dispatcher: Any) -> None:
    dispatcher.register("mongodb_query", mongodb_query)
    dispatcher.register("mongodb_insert", mongodb_insert)
    dispatcher.register("mongodb_update", mongodb_update)
    dispatcher.register("mongodb_upsert", mongodb_upsert)
