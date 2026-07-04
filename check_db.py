import asyncio
from pymongo import MongoClient

MONGODB_URL = "mongodb+srv://sriharshith0511:kanna051104@intersnhip.9qedzpx.mongodb.net/?appName=intersnhip&tlsAllowInvalidCertificates=true"
DB_NAME = "outreach_ai"

def check():
    client = MongoClient(MONGODB_URL)
    db = client[DB_NAME]
    
    print("=== USERS ===")
    for u in db.users.find({}, {"_id": 0, "id": 1, "name": 1, "email": 1}):
        print(u)
        
    print("\n=== CAMPAIGNS ===")
    for c in db.campaigns.find({}, {"_id": 0, "id": 1, "name": 1, "user_id": 1}):
        print(c)
        
    print("\n=== REPLIES ===")
    for r in db.replies.find({}, {"_id": 0, "id": 1, "campaign_id": 1, "from_email": 1, "subject": 1, "received_at": 1}):
        print(r)
        
    print("\n=== LEADS WHO REPLIED ===")
    for l in db.leads.find({"status": "replied"}, {"_id": 0, "id": 1, "name": 1, "email": 1, "status": 1}):
        print(l)

if __name__ == "__main__":
    check()
