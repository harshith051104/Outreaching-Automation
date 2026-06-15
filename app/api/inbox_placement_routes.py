"""
Inbox Placement Testing API Routes.

Exposes endpoints to record and review inbox deliverability tests.
"""

import uuid
import logging
import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth.dependencies import get_current_user
from app.config.mongodb_config import get_database
from app.services.gmail_service import send_email

router = APIRouter(prefix="/inbox-placement", tags=["Inbox Placement"])
logger = logging.getLogger(__name__)

class InboxTestRequest(BaseModel):
    from_email: str
    to_email: str
    subject: str
    body: str

@router.post("/test", summary="Run a new deliverability test and save the results")
async def run_inbox_test(
    request: InboxTestRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Run an email inbox placement deliverability test.
    Optionally delivers email if the from_email matches a connected Gmail account,
    computes a heuristic spam score, and stores the run in MongoDB.
    """
    try:
        db = await get_database()
        
        # 1. Analyze email content for realistic spam score
        spam_words = [
            "free", "guaranteed", "earn", "cash", "viagra", "buy now", 
            "risk free", "make money", "winner", "congratulations", 
            "opportunity", "claims", "unlimited", "income"
        ]
        
        spam_score = 0.1
        body_lower = request.body.lower()
        subject_lower = request.subject.lower()
        
        # Word triggers
        for word in spam_words:
            if word in body_lower:
                spam_score += 1.2
            if word in subject_lower:
                spam_score += 1.8
                
        # Subject line casing check
        if request.subject.isupper() and len(request.subject) > 5:
            spam_score += 2.5
            
        # Subject line length check
        if len(request.subject) < 3:
            spam_score += 1.0
            
        # Body length check
        if len(request.body) < 15:
            spam_score += 1.5
            
        # Cap spam score at 10.0
        spam_score = min(10.0, round(spam_score, 1))
        
        # Classify placement
        result = "spam" if spam_score >= 5.0 else "inbox"
        
        # 2. Attempt real email delivery if Gmail account is connected
        sent_real = False
        try:
            account = await db.gmail_accounts.find_one({
                "user_id": current_user["id"],
                "email": request.from_email,
                "is_active": True
            })
            if account:
                # Deliver real email using HTML wrapper
                await send_email(
                    gmail_account_id=account["id"],
                    to=request.to_email,
                    subject=request.subject,
                    body_html=f"<p>{request.body.replace(chr(10), '<br>')}</p>"
                )
                sent_real = True
                logger.info(f"Delivered real test email from {request.from_email} to {request.to_email}")
        except Exception as email_exc:
            logger.warning(f"Could not send real test email: {email_exc}")
            
        # 3. Store test result in database
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        test_doc = {
            "id": str(uuid.uuid4()),
            "user_id": current_user["id"],
            "from_email": request.from_email,
            "to_email": request.to_email,
            "subject": request.subject,
            "body": request.body,
            "result": result,
            "spam_score": spam_score,
            "sent_real": sent_real,
            "created_at": now
        }
        
        await db.inbox_placement_tests.insert_one(test_doc)
        test_doc.pop("_id", None)
        
        return {"status": "success", "test": test_doc}
    except Exception as exc:
        logger.exception("Inbox placement test failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))

@router.get("/history", summary="Get previous deliverability tests")
async def get_inbox_history(
    current_user: dict = Depends(get_current_user)
):
    """Retrieve history of deliverability tests run by the user."""
    try:
        db = await get_database()
        history = await db.inbox_placement_tests.find(
            {"user_id": current_user["id"]},
            {"_id": 0}
        ).sort("created_at", -1).to_list(length=50)
        return {"status": "success", "history": history}
    except Exception as exc:
        logger.exception("Failed to get inbox placement history: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))
