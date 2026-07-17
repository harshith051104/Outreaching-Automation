import asyncio
import sys
from app.config.mongodb_config import get_database

async def main():
    db = await get_database()
    
    collections_to_clear = [
        "leads",
        "campaigns",
        "chat_sessions",
        "emails",
        "scheduled_tasks",
        "followup_tasks",
        "replies",
        "signals",
        "opportunities",
        "analytics",
        "analytics_learning_memory",
        "lead_memories",
        "campaign_memories",
        "outreach"
    ]
    
    print("=== AI Outreach Platform - Database Cleanup ===")
    print("This will permanently delete all campaign, lead, email, chat, and analytics data.")
    print("Credentials (Gmail accounts, LinkedIn accounts, and global settings) will NOT be affected.\n")
    
    # 1. Print current counts
    counts = {}
    for col in collections_to_clear:
        try:
            count = await db[col].count_documents({})
        except Exception:
            count = 0
        counts[col] = count
        print(f"- {col}: {count} documents")
        
    total_docs = sum(counts.values())
    print(f"\nTotal documents to delete: {total_docs}")
    
    if total_docs == 0:
        print("\nDatabase is already clean. Nothing to clear.")
        return

    # 2. Get confirmation (skip if '--yes' flag is passed)
    if len(sys.argv) < 2 or sys.argv[1] != "--yes":
        confirm = input("\nAre you absolutely sure you want to delete these documents? (type 'yes' to confirm): ")
        if confirm.lower() != "yes":
            print("Aborted.")
            return
            
    # 3. Clear collections
    print("\nClearing data...")
    for col in collections_to_clear:
        if counts[col] > 0:
            try:
                res = await db[col].delete_many({})
                print(f"- Cleared {res.deleted_count} documents from '{col}'")
            except Exception as e:
                print(f"- Failed to clear '{col}': {e}")
            
    print("\n=== Cleanup Completed Successfully ===")

if __name__ == "__main__":
    asyncio.run(main())
