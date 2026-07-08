import asyncio
from app.config.mongodb_config import get_database

async def main():
    db = await get_database()
    campaigns = await db.campaigns.find().to_list(length=10)
    print("Campaigns:")
    for c in campaigns:
        lead_count = await db.leads.count_documents({"campaign_id": c["id"]})
        print(f"- {c.get('name')} ({c.get('id')}): {lead_count} leads")
        
    print("\nTotal leads count in DB:", await db.leads.count_documents({}))
    
    # Print the last 5 leads
    leads = await db.leads.find().sort("created_at", -1).limit(5).to_list(length=5)
    print("\nLast 5 leads:")
    for l in leads:
        print(f"- {l.get('name')} ({l.get('email')}): campaign_id={l.get('campaign_id')}")

if __name__ == "__main__":
    asyncio.run(main())
