"""
Setup script: Create 'English Idea' campaign + import leads from Google Sheet.
Run: python -m scripts.setup_english_idea
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config.mongodb_config import get_database, mongodb_client
from app.services.campaign_service import create_campaign
from app.services.lead_service import import_leads_csv
from app.schemas.campaign import CampaignCreate
from uuid import uuid4
from datetime import datetime, timezone
import httpx


EMAIL_SUBJECT = "Next Billion-dollar idea | Wireless Power Infrastructure: Smart Kitchens to EV"

EMAIL_BODY = """Dear [Investor Name],

I'm Shivam, Founder of ElectraWireless (California, US). I lead our hardware architecture and power systems, bringing deep domain expertise in converting magnetic resonance R&D into commercially viable products.

We know your time is limited, so I'm reaching out specifically because ElectraWireless sits at the intersection of your core investment themes. [1-sentence value prop tied to their focus]

What We Are Building
We are developing the wireless power layer for the modern world; A hardware + software stack that delivers safe, resonant power (5W-30kW) without physical cables.

The Strategy: A Phased Rollout
We are executing a "High-Velocity Wedge" strategy to fund our infrastructure goals:

Phase 1 (The Wedge): Smart Kitchens.
We are deploying wireless countertops that power appliances directly. This high-volume consumer entry point validates our Unit Economics and generates immediate cash flow.

Phase 2-4 (The Moat): Industrial & EV.
Leveraging the same core IP, we scale into logistics (AGVs) and EV charging. This shifts our revenue model from hardware sales to OEM Licensing and charging-as-a-Service (CaaS).

The "Elly" Advantage
Hardware is just the vessel. Elly, our AI control layer, manages real-time safety, efficiency, and diagnostics. This allows us to capture recurring software revenue (SaaS) on top of every hardware deployment.

The Ask:
We are raising a $5M seed round to complete productization, reach manufacturing readiness, and launch our Phase 1 pilots.

We'd welcome the chance to discuss how we are bridging the gap between consumer electronics and critical infrastructure. Are you open to a brief 20-minute intro next week?

Best regards,
The ElectraWireless Team"""

FOLLOWUP_1_SUBJECT = "Re: Next Billion-dollar idea | Wireless Power Infrastructure: Smart Kitchens to EV"
FOLLOWUP_1_BODY = """Hi [Investor Name],

Checking back in on ElectraWireless. Since my last note, we [1-sentence specific update about a recent milestone or benchmark].

Given your focus on [Specific thesis point tied to their investment area], I thought this progress would be worth noting. Do you have 15 minutes next week to discuss our roadmap?

Best,
Shivam"""

FOLLOWUP_2_SUBJECT = "Quick update / ElectraWireless"
FOLLOWUP_2_BODY = """Hi [Investor Name],

I noticed [Firm Name] recently invested in [Portfolio Company]. It's a great move, we actually see a lot of overlap in how they handle [What the portfolio company does] and how our wireless tech solves [Specific problem in their space].

We're seeing strong early interest from [Target customer segment], confirming our thesis on [Relevant market trend]. Would love to share the deck and get your take on where this fits in the current landscape.

Best,
Shivam"""

FOLLOWUP_3_SUBJECT = "Moving ElectraWireless forward"
FOLLOWUP_3_BODY = """Hi [Investor Name],

I haven't heard back, so I'll assume the timing isn't right for [Firm Name] at the moment.

I'll stop the frequent updates for now, but I'd love to keep you in the loop on major milestones as we scale. If your capacity changes or you'd like to see the data room before we close the round, just let me know.

Best,
Shivam"""

GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/1IP5A2wgsOTk1kRgJqLB2HQpgplumDqwEteKp3j1Ejp8/export?format=csv"


async def main():
    await mongodb_client.connect()
    db = await get_database()

    user_id = "default_user"

    # 1. Create campaign
    print("Creating campaign 'English Idea'...")
    campaign_data = CampaignCreate(
        name="English Idea",
        description="Campaign for ElectraWireless investor outreach",
        subject_template=EMAIL_SUBJECT,
        body_template=EMAIL_BODY,
        settings={
            "max_emails_per_day": 50,
            "delay_between_emails_seconds": 60,
            "follow_up_count": 3,
            "follow_up_delay_hours": 48,
            "tone": "professional",
            "timezone": "UTC",
        },
        sequence_steps=[
            {
                "step_number": 1,
                "channel": "email",
                "delay_days": 3,
                "subject_template": FOLLOWUP_1_SUBJECT,
                "body_template": FOLLOWUP_1_BODY,
                "notes": "Relevant Update - benchmark/pilot progress",
            },
            {
                "step_number": 2,
                "channel": "email",
                "delay_days": 10,
                "subject_template": FOLLOWUP_2_SUBJECT,
                "body_template": FOLLOWUP_2_BODY,
                "notes": "Social proof/insight - portfolio company overlap",
            },
            {
                "step_number": 3,
                "channel": "email",
                "delay_days": 21,
                "subject_template": FOLLOWUP_3_SUBJECT,
                "body_template": FOLLOWUP_3_BODY,
                "notes": "Soft break-up - keep door open for data room",
            },
        ],
    )
    campaign = await create_campaign(user_id, campaign_data)
    campaign_id = campaign["id"]
    print(f"Campaign created: {campaign_id}")

    # 2. Import leads from Google Sheet
    print("Fetching Google Sheet...")
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(GOOGLE_SHEET_URL, follow_redirects=True)
        if response.status_code != 200:
            print(f"Failed to fetch sheet: {response.status_code}")
            await mongodb_client.disconnect()
            return
        csv_content = response.content

    print(f"Importing {len(csv_content)} bytes of CSV data...")
    import_result = await import_leads_csv(campaign_id, user_id, csv_content, "investors.csv")
    print(f"Import result: {import_result}")

    # 3. Store AI placeholder metadata on campaign
    ai_placeholders = {
        "1-sentence value prop tied to their focus": "Generate a 1-sentence value prop explaining how ElectraWireless aligns with this investor's primary investment thesis. Use their 'focus' field.",
        "1-sentence specific update about a recent milestone or benchmark": "Generate a realistic 1-sentence benchmark update for ElectraWireless (e.g., signal efficiency milestone, new pilot partnership, manufacturing progress).",
        "Specific thesis point tied to their investment area": "Generate a specific investment thesis point from this investor's focus area that relates to wireless power, energy infrastructure, or hardware.",
        "Firm Name": "Use the investor's company/firm name from lead data. If not available, generate a plausible VC firm name.",
        "Portfolio Company": "Generate a relevant portfolio company name that a firm with this investor's focus would have invested in.",
        "What the portfolio company does": "Describe what the portfolio company does in 1 sentence, relating to wireless power or energy.",
        "Specific problem in their space": "Describe how ElectraWireless's wireless power tech solves the same problem in 1 sentence.",
        "Target customer segment": "Generate a relevant customer segment (e.g., commercial kitchen operators, EV fleet managers, industrial automation companies).",
        "Relevant market trend": "Generate a market trend related to wireless power adoption or infrastructure modernization.",
    }

    await db.campaigns.update_one(
        {"id": campaign_id},
        {"$set": {"ai_placeholder_definitions": ai_placeholders, "updated_at": datetime.now(timezone.utc)}},
    )
    print(f"AI placeholder definitions stored on campaign {campaign_id}")

    await mongodb_client.disconnect()
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
