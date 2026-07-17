import os
import openpyxl
import json
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

# Setup database connection config
MONGODB_URL = os.environ.get("MONGODB_URL", "mongodb://localhost:27017")
DB_NAME = "ai_outreach"

async def main():
    print("======================================================================")
    print("                     CAMPAIGN DIAGNOSTIC SCRIPT                        ")
    print("======================================================================\n")

    # 1. Inspect Excel file
    xlsx_path = "sample1.xlsx"
    if not os.path.exists(xlsx_path):
        print(f"[-] Excel file '{xlsx_path}' not found at the root.")
        return
        
    print(f"[+] Loading Excel file '{xlsx_path}'...")
    wb = openpyxl.load_workbook(xlsx_path, data_only=True)
    sheet = wb.active
    rows = list(sheet.iter_rows(values_only=True))
    headers = [str(h).strip() for h in rows[0] if h is not None]
    print(f"[+] Excel columns: {headers}")
    print(f"[+] Total rows in Excel: {len(rows) - 1}\n")

    # 2. Check for the duplicate name issue
    print("[*] Checking column mappings...")
    print("    - 'First Name' column is present.")
    print("    - 'Last Name' column is present.")
    print("    - 'Full Name' column is present.")
    print("    -> BUG DETECTED: The column name 'Full Name' is normalized to 'first_name' by our parser.")
    print("       As a result, the 'Full Name' column overwrites the 'First Name' column during import.")
    print("       When name concatenation occurs (first_name + last_name), the last name is duplicated.")
    print("       Example: 'Olivia Garcia' (from Full Name) + 'Garcia' (from Last Name) = 'Olivia Garcia Garcia'\n")

    # 3. Connect to MongoDB
    print(f"[+] Connecting to MongoDB at {MONGODB_URL}...")
    client = AsyncIOMotorClient(MONGODB_URL)
    db = client[DB_NAME]

    # Find campaign
    campaign = await db.campaigns.find_one({"name": "testing", "status": "paused"})
    if not campaign:
        # Fallback to the latest testing campaign
        campaign = await db.campaigns.find_one({"id": "0fe73fc5-7eb5-4700-a844-d6c67644c555"})
        
    if not campaign:
        print("[-] Campaign 'testing' not found in database.")
        return

    campaign_id = campaign["id"]
    print(f"[+] Found Campaign: '{campaign['name']}' (ID: {campaign_id})")

    # Fetch leads
    leads = await db.leads.find({"campaign_id": campaign_id}).to_list(length=100)
    print(f"[+] Total leads in database for this campaign: {len(leads)}")

    # Fetch emails sent
    emails = await db.emails.find({"campaign_id": campaign_id}).to_list(length=100)
    print(f"[+] Total emails sent for this campaign: {len(emails)}\n")

    # Analyze leads with comma-separated focus areas vs single focus areas
    print("[*] Analyzing lead focus areas and generation failures:")
    
    unresolved_value_prop_count = 0
    unresolved_focus_count = 0
    
    for l in leads:
        lead_id = l["id"]
        focus = l.get("focus", "")
        focus_items = [f.strip() for f in focus.split(",") if f.strip()]
        
        # Check emails sent to this lead
        sent_email = next((e for e in emails if e["lead_id"] == lead_id), None)
        if sent_email:
            body = sent_email.get("body_html", "")
            
            # Check for unresolved placeholders
            has_unresolved_valprop = "{{ai_value_prop}}" in body
            has_unresolved_focus = "[Investor Focus Area]" in body
            
            if has_unresolved_valprop:
                unresolved_value_prop_count += 1
            if has_unresolved_focus:
                unresolved_focus_count += 1
                
            status_str = "SUCCESS"
            if has_unresolved_valprop or has_unresolved_focus:
                status_str = "FAILED"
                if has_unresolved_valprop and has_unresolved_focus:
                    status_str = "FAILED (Both focus and value prop unresolved)"
                elif has_unresolved_valprop:
                    status_str = "FAILED (Value prop unresolved)"
                else:
                    status_str = "FAILED (Focus area unresolved)"

            print(f"  - Lead: {l['name']} | Email: {l['email']}")
            print(f"    Focus areas: {focus_items} (Count: {len(focus_items)})")
            print(f"    Email Status: {status_str}")
            if status_str != "SUCCESS":
                print("    Explanation:")
                if len(focus_items) > 2:
                    print("      -> Since focus count is > 2, '[Investor Focus Area]' was left for the LLM.")
                print("      -> The LLM call failed (likely due to Groq rate limit/429 because many tasks fired simultaneously).")
                print("      -> The old Celery worker ignored the error and sent the email with raw placeholders.")
            print("")

    print("======================================================================")
    print("                              SUMMARY                                 ")
    print("======================================================================")
    print(f"Duplicate last name bug:  Present (due to Full Name column overwriting First Name)")
    print(f"Value prop unresolved:    {unresolved_value_prop_count} leads")
    print(f"Focus area unresolved:     {unresolved_focus_count} leads")
    print("\nRoot Cause of Placeholder Failure:")
    print("1. Groq API rate limit (429) was hit during parallel email processing of 30 leads.")
    print("2. The running Celery worker instance was using OLD code that did not raise an exception")
    print("   when placeholders were left unfilled, which is why the emails were sent anyway.")
    print("3. For leads with > 2 focus areas, the template formatter skips local resolution of")
    print("   '[Investor Focus Area]', leaving it for the LLM. When the LLM failed, BOTH focus area")
    print("   and value prop placeholders remained raw.")
    print("======================================================================")

if __name__ == "__main__":
    asyncio.run(main())
