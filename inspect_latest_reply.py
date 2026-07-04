import asyncio
from pymongo import MongoClient

MONGODB_URL = "mongodb+srv://sriharshith0511:kanna051104@intersnhip.9qedzpx.mongodb.net/?appName=intersnhip&tlsAllowInvalidCertificates=true"
DB_NAME = "outreach_ai"

def inspect():
    client = MongoClient(MONGODB_URL)
    db = client[DB_NAME]
    
    # Get latest reply
    reply = db.replies.find_one({}, sort=[("received_at", -1)])
    if not reply:
        print("No replies found in db")
        return
        
    print("Latest reply:")
    print("  ID:", reply.get("id"))
    print("  From:", reply.get("from_email"))
    print("  Subject:", reply.get("subject"))
    print("  Received at:", reply.get("received_at"))
    print("  Snippet:", reply.get("snippet"))
    print("  Draft response field:", reply.get("draft_response"))
    
    # Get latest pending approval
    approval = db.pending_approvals.find_one({"action_type": "email_reply"}, sort=[("created_at", -1)])
    if approval:
        print("\nLatest pending approval:")
        print("  Action ID:", approval.get("action_id"))
        print("  Description:", repr(approval.get("description")))
        print("  Payload:", approval.get("payload"))
        print("  Status:", approval.get("status"))
    else:
        print("\nNo pending approvals found for action_type 'email_reply'")

if __name__ == "__main__":
    inspect()
