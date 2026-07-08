"""
Analytics API routes.

Dashboard stats, campaign analytics, daily breakdowns, and AI insights.
"""

from fastapi import APIRouter, Depends, Query

from app.auth.dependencies import get_current_user
from app.services.analytics_service import (
    get_dashboard_stats,
    get_campaign_analytics,
    get_daily_stats,
    generate_campaign_insights,
)
from app.agents.analytics_agent import generate_campaign_insights as ai_generate_insights

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/dashboard", summary="Dashboard statistics")
async def dashboard(
    current_user: dict = Depends(get_current_user),
):
    """
    Return aggregated stats across all of the user's campaigns.
    """
    return await get_dashboard_stats(current_user["id"])


@router.get("/campaign/{campaign_id}", summary="Campaign analytics")
async def campaign_analytics(
    campaign_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Return detailed analytics for a specific campaign."""
    return await get_campaign_analytics(campaign_id, current_user["id"])


@router.get("/campaign/{campaign_id}/daily", summary="Daily campaign stats")
async def daily_stats(
    campaign_id: str,
    days: int = Query(30, ge=1, le=90),
    current_user: dict = Depends(get_current_user),
):
    """Return per-day breakdowns of sends, opens, clicks, and replies."""
    return await get_daily_stats(campaign_id, days=days)


@router.get("/ai-insights", summary="Global AI optimization insights across all campaigns")
async def ai_insights(
    current_user: dict = Depends(get_current_user),
):
    """
    Generate cross-campaign AI insights: best subject lines, send times,
    highest reply rate campaigns, and optimization recommendations.
    """
    db = await get_database()
    user_id = current_user["id"]

    campaigns = await db.campaigns.find(
        {"user_id": user_id, "status": {"$ne": "deleted"}}
    ).to_list(length=100)

    campaign_ids = [c["id"] for c in campaigns]

    send_pipeline = [
        {"$match": {"campaign_id": {"$in": campaign_ids}, "status": "sent"}},
        {"$group": {
            "_id": {"$hour": "$sent_at"},
            "count": {"$sum": 1},
        }},
        {"$sort": {"count": -1}},
    ]
    send_hour_results = await db.emails.aggregate(send_pipeline).to_list(length=24)
    best_send_hours = [
        {"hour": r["_id"], "emails_sent": r["count"]}
        for r in send_hour_results[:5]
    ]

    campaign_stats = []
    for c in campaigns:
        try:
            stats = await get_campaign_analytics(c["id"], user_id)
            campaign_stats.append({
                "campaign_id": c["id"],
                "name": c.get("name", "Untitled"),
                "status": c.get("status", "unknown"),
                "emails_sent": stats.get("emails_sent", 0),
                "open_rate": stats.get("open_rate", 0.0),
                "click_rate": stats.get("click_rate", 0.0),
                "reply_rate": stats.get("reply_rate", 0.0),
            })
        except Exception:
            pass

    campaign_stats.sort(key=lambda x: x["reply_rate"], reverse=True)
    top_campaigns = campaign_stats[:5]

    total_sent = sum(c["emails_sent"] for c in campaign_stats)
    avg_open = sum(c["open_rate"] for c in campaign_stats) / len(campaign_stats) if campaign_stats else 0
    avg_click = sum(c["click_rate"] for c in campaign_stats) / len(campaign_stats) if campaign_stats else 0
    avg_reply = sum(c["reply_rate"] for c in campaign_stats) / len(campaign_stats) if campaign_stats else 0

    return {
        "summary": {
            "total_campaigns": len(campaign_stats),
            "total_emails_sent": total_sent,
            "avg_open_rate": round(avg_open, 2),
            "avg_click_rate": round(avg_click, 2),
            "avg_reply_rate": round(avg_reply, 2),
        },
        "best_send_times": best_send_hours,
        "top_campaigns_by_reply_rate": top_campaigns,
        "all_campaigns": campaign_stats,
    }


@router.get("/campaign/{campaign_id}/insights", summary="AI-powered campaign insights")
async def insights(
    campaign_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Generate AI-powered insights and recommendations for a campaign.
    """
    campaign_analytics = await get_campaign_analytics(campaign_id, current_user["id"])

    from app.config.mongodb_config import get_database
    db = await get_database()
    other_campaigns = await db.campaigns.find({
        "user_id": current_user["id"],
        "id": {"$ne": campaign_id}
    }).to_list(length=10)
    
    comparison_data = []
    for other in other_campaigns:
        try:
            other_stats = await get_campaign_analytics(other["id"], current_user["id"])
            comparison_data.append({
                "campaign_id": other["id"],
                "name": other["name"],
                "metrics": {
                    "sent_count": other_stats.get("emails_sent", 0),
                    "open_rate": other_stats.get("open_rate", 0.0),
                    "click_rate": other_stats.get("click_rate", 0.0),
                    "reply_rate": other_stats.get("reply_rate", 0.0)
                },
                "strategy": other.get("description", "")
            })
        except Exception:
            pass

    analytics_context = {
        "other_campaigns": comparison_data
    }

    return await ai_generate_insights(campaign_analytics, analytics_context)


@router.post("/dashboard/export/sheets", summary="Export dashboard stats to Google Sheets")
async def export_dashboard_to_sheets(
    current_user: dict = Depends(get_current_user),
):
    stats = await get_dashboard_stats(current_user["id"])
    
    headers = [
        "Metric / Campaign Name",
        "Sent Count",
        "Opened Count",
        "Clicked Count",
        "Replied Count",
        "Open Rate (%)",
        "Click Rate (%)",
        "Reply Rate (%)"
    ]
    
    rows = []
    # Add Overall Stats Row
    rows.append([
        "OVERALL DASHBOARD SUMMARY",
        stats.get("total_emails_sent", 0),
        stats.get("total_opens", 0),
        stats.get("total_clicks", 0),
        stats.get("total_replies", 0),
        stats.get("open_rate", 0.0),
        stats.get("click_rate", 0.0),
        stats.get("reply_rate", 0.0)
    ])
    
    # Fetch actual campaigns and flows to populate the breakdown section
    from app.config.mongodb_config import get_database
    db = await get_database()
    
    campaigns = await db.campaigns.find(
        {"user_id": current_user["id"], "status": {"$ne": "deleted"}}
    ).to_list(length=100)
    
    flows = await db.campaign_flows.find(
        {"user_id": current_user["id"]}
    ).to_list(length=100)
    
    all_campaigns_and_flows = []
    for c in campaigns:
        all_campaigns_and_flows.append({"id": c["id"], "name": c.get("name", "Campaign"), "type": "Campaign"})
    for f in flows:
        all_campaigns_and_flows.append({"id": f["id"], "name": f.get("name", "Visual Flow"), "type": "Visual Flow"})
        
    if all_campaigns_and_flows:
        # Empty Row for separation
        rows.append(["", "", "", "", "", "", "", ""])
        
        # Campaigns Section Header
        rows.append(["CAMPAIGN / FLOW BREAKDOWN", "", "", "", "", "", "", ""])
        
        # Add Campaign Performance Rows
        for c in all_campaigns_and_flows:
            try:
                c_stats = await get_campaign_analytics(c["id"], current_user["id"])
                sent = c_stats.get("emails_sent", 0)
                opened = c_stats.get("unique_opens", 0)
                clicked = c_stats.get("unique_clicks", 0)
                replied = c_stats.get("total_replies", 0)
                
                rows.append([
                    f"{c['name']} ({c['type']})",
                    sent,
                    opened,
                    clicked,
                    replied,
                    c_stats.get("open_rate", 0.0),
                    c_stats.get("click_rate", 0.0),
                    c_stats.get("reply_rate", 0.0)
                ])
            except Exception:
                pass
        
    from app.services.google_sheets_service import create_and_fill_spreadsheet
    from datetime import datetime
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    return await create_and_fill_spreadsheet(
        user_id=current_user["id"],
        title=f"Campaigns Dashboard Stats - {now_str}",
        headers=headers,
        rows=rows
    )


@router.post("/campaign/{campaign_id}/export/sheets", summary="Export campaign analytics to Google Sheets")
async def export_campaign_analytics_to_sheets(
    campaign_id: str,
    days: int = Query(30, ge=1, le=90),
    current_user: dict = Depends(get_current_user),
):
    from app.config.mongodb_config import get_database
    db = await get_database()
    campaign = await db.campaigns.find_one({"id": campaign_id})
    if not campaign:
        campaign = await db.campaign_flows.find_one({"id": campaign_id})
    campaign_name = campaign.get("name", "Campaign") if campaign else "Campaign"
    
    stats = await get_campaign_analytics(campaign_id, current_user["id"])
    daily = await get_daily_stats(campaign_id, days=days)
    
    headers = [
        "Date / Summary",
        "Sent Count",
        "Opened Count",
        "Clicked Count",
        "Replied Count",
        "Open Rate (%)",
        "Click Rate (%)",
        "Reply Rate (%)"
    ]
    
    rows = []
    # Add Overall Summary Row
    rows.append([
        f"SUMMARY FOR: {campaign_name}",
        stats.get("emails_sent", 0),
        stats.get("unique_opens", 0),
        stats.get("unique_clicks", 0),
        stats.get("total_replies", 0),
        stats.get("open_rate", 0.0),
        stats.get("click_rate", 0.0),
        stats.get("reply_rate", 0.0)
    ])
    
    # Separator
    rows.append(["", "", "", "", "", "", "", ""])
    rows.append(["DAILY BREAKDOWN STATS", "", "", "", "", "", "", ""])
    
    # Add Daily stats rows
    for day in daily:
        date_str = day.get("date", "")
        sent = day.get("emails_sent", 0)
        opened = day.get("opens", 0)
        clicked = day.get("clicks", 0)
        replied = day.get("replies", 0)
        
        open_rate = round((opened / sent * 100), 2) if sent > 0 else 0.0
        click_rate = round((clicked / sent * 100), 2) if sent > 0 else 0.0
        reply_rate = round((replied / sent * 100), 2) if sent > 0 else 0.0
        
        rows.append([
            date_str,
            sent,
            opened,
            clicked,
            replied,
            open_rate,
            click_rate,
            reply_rate
        ])
        
    from app.services.google_sheets_service import create_and_fill_spreadsheet
    from datetime import datetime
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    return await create_and_fill_spreadsheet(
        user_id=current_user["id"],
        title=f"Campaign Analytics - {campaign_name} - {now_str}",
        headers=headers,
        rows=rows
    )


@router.get("/deliverability", summary="Check domain deliverability status")
async def check_deliverability(
    domain: str = Query(..., description="The sender domain to inspect"),
    current_user: dict = Depends(get_current_user)
):
    """
    Check SPF, DKIM, and DMARC settings for the specified domain.
    """
    from app.services.deliverability_service import check_domain_deliverability
    return await check_domain_deliverability(domain)


@router.get("/campaign/{campaign_id}/health", summary="Get detailed campaign health score")
async def campaign_health(
    campaign_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Calculate and return the 0-100 Campaign Health Score with warning checklists.
    """
    from app.services.deliverability_service import get_campaign_health_score
    from app.services.analytics_service import get_campaign_analytics
    
    analytics = await get_campaign_analytics(campaign_id, current_user["id"])
    return get_campaign_health_score(analytics)