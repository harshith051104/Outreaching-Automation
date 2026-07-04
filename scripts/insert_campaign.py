import os
import re
import sys
from datetime import datetime, timezone
from pymongo import MongoClient

def load_env(env_path):
    env_vars = {}
    if not os.path.exists(env_path):
        print(f"Warning: .env file not found at {env_path}")
        return env_vars
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            match = re.match(r'^([^=]+)=(.*)$', line)
            if match:
                key = match.group(1).strip()
                val = match.group(2).strip()
                # Strip quotes if present
                if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                    val = val[1:-1]
                env_vars[key] = val
    return env_vars

def main():
    env_path = ".env"
    env_vars = load_env(env_path)
    
    mongodb_url = env_vars.get("MONGODB_URL")
    db_name = env_vars.get("MONGODB_DB_NAME", "outreach_ai")
    
    if not mongodb_url:
        print("Error: MONGODB_URL not found in .env file.")
        sys.exit(1)
        
    print(f"Connecting to MongoDB...")
    try:
        # Connect using the parsed MONGODB_URL
        client = MongoClient(mongodb_url, tlsAllowInvalidCertificates=True)
        db = client[db_name]
        print(f"Connected successfully to database: {db_name}")
    except Exception as e:
        print(f"Error connecting to MongoDB: {e}")
        sys.exit(1)
        
    # Campaign data from the user request
    campaign_doc = {
        "id": "1d87aeff-f5b7-43a5-b0b5-88f7c3b1fc55",
        "user_id": "3f229c2f-fed1-49b5-8f82-adbde8f7b7c4",
        "name": "Market Stakeholder",
        "description": "Investment outreach campaign targeting market stakeholders for ElectraWireless. Leads imported from Google Sheets. Focus on personalized investment pitches highlighting vision, products, market opportunity, execution strategy, and investment impact.",
        "gmail_account_id": "5aac4dec-5421-49c2-bca6-fff8cd2ba819",
        "subject_template": "{{company}} — ElectraWireless Series A: $12B+ TAM in RF Front-End Innovation",
        "body_template": "Hi {{first_name}},\n\nI'm reaching out because {{company}}'s investment focus on frontier technology and next-generation infrastructure aligns with what we're building at ElectraWireless.\n\nWe're revolutionizing wireless connectivity through proprietary RF front-end solutions that solve the critical efficiency-linearity trade-off plaguing 5G/6G and satellite communications. Our GaN and SOI-based FEMs, LNAs, and Power Amplifiers deliver industry-leading performance where incumbents fall short—at the mmWave frequencies driving next-gen infrastructure.\n\n**The market momentum is substantial:** the RF Front-End market is surging past $35B by 2028, fueled by 5G densification, 6G research, and LEO satellite constellation proliferation. We've identified a $12B+ TAM in base station and satellite terminal FEMs alone—two sectors where our architecture commands measurable technical advantages.\n\n**Our traction is accelerating:** design wins are advancing with Tier-1 OEMs, and we're in active qualification with two major satellite constellation programs projected to generate $50M+ ARR by Year 3.\n\nWe're raising a $15M Series A to scale manufacturing with foundry partners, accelerate 6G-ready chipset tape-outs, and secure these transformative design wins. Exit pathways include strategic acquisition by semiconductor leaders (Qorvo, Skyworks, Broadcom) or IPO.\n\nI would welcome the opportunity to share our detailed investor deck and discuss how ElectraWireless aligns with your portfolio thesis. Are you available for a brief 20-minute call next week to review our technology differentiation and financial projections?\n\nBest regards,\n\n{{sender_name}}\n{{sender_title}}\n{{sender_email}}",
        "followup_enabled": False,
        "followup_stages": 3,
        "followup_delay_days": 3,
        "daily_send_limit": 50,
        "status": "active",
        "total_leads": 10,
        "emails_sent": 0,
        "sequence_steps": [
            {
                "step_number": 1,
                "channel": "email",
                "delay_days": 3,
                "subject_template": "Quick follow-up: ElectraWireless technical deep-dive & financial model",
                "body_template": "Hi {{first_name}},\n\nI wanted to follow up on my note about ElectraWireless's Series A opportunity.\n\nI understand your inbox is crowded with semiconductor investment pitches. What differentiates our opportunity is the technical moat we've built—and the speed at which we're converting that into commercial traction.\n\n**A few specifics I didn't share previously:**\n\n• Our proprietary GaN-on-SOI process achieves 40% better power-added efficiency than competing Qorvo and Skyworks solutions at 28GHz and 39GHz—critical frequencies for 6G and dense urban 5G\n• Thermal performance improvements allow us to reduce base station cooling overhead by 15-20%, a major OPEX win for operators\n• We've secured LOIs from two Tier-1 infrastructure OEMs and are in final qualification stages with a top-three LEO satellite operator\n\nOur financial model projects 70%+ gross margins at scale, with a clear path to $50M+ ARR by Year 3 driven by satellite terminal and base station FEM volumes.\n\nI've prepared a technical deep-dive and detailed financial model that I'd value your perspective on. Would 20 minutes next Tuesday or Thursday work for a walkthrough?\n\n{{sender_name}}\n{{sender_title}}\n{{sender_email}}"
            },
            {
                "step_number": 2,
                "channel": "email",
                "delay_days": 10,
                "subject_template": "{{first_name}} — Why now: RF Front-End inflection point & ElectraWireless timing",
                "body_template": "Hi {{first_name}},\n\nThe RF Front-End market is at an inflection point that creates a narrow window for outsized returns—and I want to make sure {{company}} doesn't miss it.\n\n**Three converging forces are reshaping competitive dynamics:**\n\n1. **Spectrum scarcity is accelerating mmWave deployment.** Sub-6GHz is congested; operators and satellite providers are moving higher in frequency faster than incumbent architectures can adapt. Our GaN-on-SOI solutions were architected specifically for this transition.\n\n2. **LEO constellation build-outs are creating demand surges.** Starlink's 5,000+ satellites, Amazon Kuiper's planned 3,236, and OneWeb's expanding fleet require millions of ground terminals annually—each needing high-performance, cost-optimized FEMs. We're qualified with programs representing over 60% of deployed and planned LEO capacity.\n\n3. **Incumbent technology roadmaps are stalled.** Qorvo, Skyworks, and Broadcom are optimizing legacy architectures. Our clean-sheet design delivers 2-3x performance advantages in metrics that matter for next-gen systems.\n\nOur $15M Series A is structured to achieve technical de-risking milestones that position us for a significant up-round within 18 months or strategic exit. The round is 40% committed by strategic and financial investors with deep semiconductor expertise.\n\nI'm happy to share our data room and arrange conversations with our technical advisory board (former CTOs from Qualcomm RF and Analog Devices) if helpful.\n\nCan we find time this week or next?\n\n{{sender_name}}\n{{sender_title}}\n{{sender_email}}"
            },
            {
                "step_number": 3,
                "channel": "email",
                "delay_days": 20,
                "subject_template": "Final note: ElectraWireless Series A — closing {{company}}'s evaluation window",
                "body_template": "Hi {{first_name}},\n\nThis is my final outreach regarding ElectraWireless's Series A. I recognize the timing may not be right for {{company}}, and I respect your decision either way.\n\nBefore closing this loop, I want to leave you with the core investment thesis:\n\n**Problem worth solving:** The $35B+ RF Front-End market is constrained by a fundamental efficiency-linearity trade-off at mmWave frequencies. Incumbent solutions force unacceptable compromises in 5G/6G infrastructure and satellite terminals.\n\n**Our solution:** Proprietary GaN-on-S PMIC architecture delivering 40% efficiency gains and 2-3x linearity improvements, with a manufacturing roadmap that scales through established foundry partnerships.\n\n**Market validation:** $12B+ TAM in target segments, with LOIs and active qualifications from Tier-1 OEMs and major LEO operators representing 60%+ of constellation capacity.\n\n**Capital efficiency:** $15M Series A funds tape-out, manufacturing scale-up, and go-to-market expansion to $50M+ ARR by Year 3. Strong strategic acquisition interest already signaled.\n\n**Why now:** Round is 40% committed; term sheet discussions active with co-leads. Evaluation window for new investors is narrowing.\n\nIf this resonates, I'm available for a brief conversation at your convenience. If not, I hope our paths cross on a future opportunity.\n\nBest wishes for your continued success,\n\n{{sender_name}}\n{{sender_title}}\n{{sender_email}}\n\nP.S. — I'm happy to add you to our quarterly investor update if you'd prefer to track our progress passively. Just reply \"updates\" and I'll include you."
            }
        ],
        "settings": {
            "max_emails_per_day": 50,
            "delay_between_emails_seconds": 60,
            "follow_up_count": 3,
            "follow_up_delay_hours": 48,
            "tone": "professional",
            "timezone": "UTC"
        },
        "created_at": datetime.fromisoformat("2026-07-01T13:46:42.142000").replace(tzinfo=timezone.utc),
        "updated_at": datetime.fromisoformat("2026-07-01T17:31:24.857000").replace(tzinfo=timezone.utc),
        "started_at": datetime.fromisoformat("2026-07-01T17:31:24.857000").replace(tzinfo=timezone.utc)
    }

    # Insert or update campaign document
    campaigns_coll = db["campaigns"]
    campaign_id = campaign_doc["id"]
    
    print(f"Upserting campaign with ID '{campaign_id}' into collection 'campaigns'...")
    res = campaigns_coll.update_one(
        {"id": campaign_id},
        {"$set": campaign_doc},
        upsert=True
    )
    
    if res.matched_count > 0:
        print(f"Campaign with ID '{campaign_id}' was matched and updated successfully.")
    elif res.upserted_id:
        print(f"Campaign with ID '{campaign_id}' was inserted successfully (upserted).")
    else:
        print(f"Campaign with ID '{campaign_id}' was modified/upserted.")
        
    # Check DB stats for verification
    num_campaigns = campaigns_coll.count_documents({})
    num_leads = db["leads"].count_documents({"campaign_id": campaign_id})
    print(f"Total campaigns in DB: {num_campaigns}")
    print(f"Total leads associated with this campaign: {num_leads}")
    
    print("Done!")

if __name__ == "__main__":
    main()
