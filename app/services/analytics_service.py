"""
Analytics service layer.

Provides campaign-level analytics, dashboard aggregation,
daily breakdowns, and basic campaign insights.
"""

from datetime import datetime, timezone, timedelta

from fastapi import HTTPException, status

from app.config.mongodb_config import get_database
from app.utils.id_generator import generate_id


async def get_campaign_analytics(campaign_id: str, user_id: str) -> dict:
    """
    Compute and return analytics for a single campaign.

    Verifies campaign ownership before returning data.
    """
    db = await get_database()

    campaign = await db.campaigns.find_one(
        {"id": campaign_id, "user_id": user_id}, {"_id": 0}
    )
    if not campaign:
        campaign = await db.campaign_flows.find_one(
            {"id": campaign_id, "user_id": user_id}, {"_id": 0}
        )
        if not campaign:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Campaign not found.",
            )

    analytics = await db.analytics.find_one(
        {"campaign_id": campaign_id}, {"_id": 0}
    )

    if analytics:
        return analytics

    return await _compute_analytics(campaign_id)


async def get_dashboard_stats(user_id: str) -> dict:
    """
    Aggregate high-level stats across all campaigns owned by user.
    """
    db = await get_database()

    total_campaigns = await db.campaigns.count_documents(
        {"user_id": user_id, "status": {"$ne": "deleted"}}
    )
    active_campaigns = await db.campaigns.count_documents(
        {"user_id": user_id, "status": "active"}
    )
    
    total_flows = await db.campaign_flows.count_documents(
        {"user_id": user_id}
    )
    active_flows = await db.campaign_flows.count_documents(
        {"user_id": user_id, "status": "active"}
    )

    total_campaigns += total_flows
    active_campaigns += active_flows

    total_leads = await db.leads.count_documents({"user_id": user_id})

    campaign_cursor = db.campaigns.find(
        {"user_id": user_id, "status": {"$ne": "deleted"}}, {"id": 1, "_id": 0}
    )
    campaign_ids = [c["id"] for c in await campaign_cursor.to_list(length=500)]

    flow_cursor = db.campaign_flows.find(
        {"user_id": user_id}, {"id": 1, "_id": 0}
    )
    flow_ids = [f["id"] for f in await flow_cursor.to_list(length=500)]
    campaign_ids.extend(flow_ids)

    total_emails_sent = await db.emails.count_documents(
        {"campaign_id": {"$in": campaign_ids}, "status": "sent"}
    )

    pipeline = [
        {"$match": {"campaign_id": {"$in": campaign_ids}}},
        {"$group": {"_id": "$event_type", "count": {"$sum": 1}}},
    ]
    agg_results = await db.tracking_events.aggregate(pipeline).to_list(length=10)

    event_counts: dict = {}
    for r in agg_results:
        event_counts[r["_id"]] = r["count"]

    total_opens = event_counts.get("open", 0)
    total_clicks = event_counts.get("click", 0)
    total_replies = event_counts.get("reply", 0)

    # Compute emails sent today
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    sent_today = await db.emails.count_documents(
        {
            "campaign_id": {"$in": campaign_ids},
            "status": "sent",
            "sent_at": {"$gte": today_start}
        }
    )

    # Get daily limit from system_preferences
    daily_limit = 50
    prefs = await db.system_settings.find_one({"user_id": user_id, "type": "system_preferences"})
    if prefs and "dailyLimit" in prefs:
        daily_limit = prefs["dailyLimit"]

    open_rate = (total_opens / total_emails_sent * 100) if total_emails_sent > 0 else 0.0
    click_rate = (total_clicks / total_emails_sent * 100) if total_emails_sent > 0 else 0.0
    reply_rate = (total_replies / total_emails_sent * 100) if total_emails_sent > 0 else 0.0

    return {
        "total_campaigns": total_campaigns,
        "active_campaigns": active_campaigns,
        "total_leads": total_leads,
        "total_emails_sent": total_emails_sent,
        "total_opens": total_opens,
        "total_clicks": total_clicks,
        "total_replies": total_replies,
        "open_rate": round(open_rate, 2),
        "click_rate": round(click_rate, 2),
        "reply_rate": round(reply_rate, 2),
        "sent_today": sent_today,
        "daily_send_limit": daily_limit,
    }


async def update_campaign_analytics(campaign_id: str) -> None:
    """
    Recalculate analytics from tracking events and persist the result.
    """
    analytics = await _compute_analytics(campaign_id)

    db = await get_database()
    now = datetime.now(timezone.utc)

    existing = await db.analytics.find_one({"campaign_id": campaign_id})
    if existing:
        await db.analytics.update_one(
            {"campaign_id": campaign_id},
            {"$set": {**analytics, "updated_at": now}},
        )
    else:
        analytics["id"] = generate_id()
        analytics["created_at"] = now
        analytics["updated_at"] = now
        await db.analytics.insert_one(analytics)


async def get_daily_stats(campaign_id: str, days: int = 30) -> list:
    """
    Return daily breakdowns of sends, opens, clicks, and replies
    for the past N days.
    """
    db = await get_database()
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    pipeline = [
        {"$match": {"campaign_id": campaign_id, "timestamp": {"$gte": cutoff}}},
        {
            "$group": {
                "_id": {
                    "date": {
                        "$dateToString": {"format": "%Y-%m-%d", "date": "$timestamp"}
                    },
                    "event_type": "$event_type",
                },
                "count": {"$sum": 1},
            }
        },
        {"$sort": {"_id.date": 1}},
    ]

    results = await db.tracking_events.aggregate(pipeline).to_list(length=500)

    daily_map: dict[str, dict] = {}
    for r in results:
        date_str = r["_id"]["date"]
        event_type = r["_id"]["event_type"]
        if date_str not in daily_map:
            daily_map[date_str] = {
                "date": date_str,
                "opens": 0,
                "clicks": 0,
                "replies": 0,
            }
        key_mapping = {
            "open": "opens",
            "click": "clicks",
            "reply": "replies"
        }
        plural_key = key_mapping.get(event_type, event_type + "s")
        if plural_key in daily_map[date_str]:
            daily_map[date_str][plural_key] = r["count"]

    send_pipeline = [
        {"$match": {"campaign_id": campaign_id, "sent_at": {"$gte": cutoff}, "status": "sent"}},
        {
            "$group": {
                "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$sent_at"}},
                "count": {"$sum": 1},
            }
        },
    ]
    send_results = await db.emails.aggregate(send_pipeline).to_list(length=500)
    for r in send_results:
        date_str = r["_id"]
        if date_str not in daily_map:
            daily_map[date_str] = {
                "date": date_str,
                "opens": 0,
                "clicks": 0,
                "replies": 0,
            }
        daily_map[date_str]["emails_sent"] = r["count"]

    daily_list = []
    for i in range(days):
        d = (datetime.now(timezone.utc) - timedelta(days=days - 1 - i)).strftime("%Y-%m-%d")
        entry = daily_map.get(d, {"date": d, "opens": 0, "clicks": 0, "replies": 0})
        entry.setdefault("emails_sent", 0)
        daily_list.append(entry)

    return daily_list


async def generate_campaign_insights(campaign_id: str) -> dict:
    """
    Compute basic campaign insights: top-engaged leads, trend direction, etc.

    For AI-powered insights, use the CrewAI routes instead.
    """
    db = await get_database()
    stats = await _compute_analytics(campaign_id)

    top_leads_cursor = (
        db.leads.find({"campaign_id": campaign_id}, {"_id": 0})
        .sort("engagement_score", -1)
        .limit(5)
    )
    top_leads = await top_leads_cursor.to_list(length=5)

    now = datetime.now(timezone.utc)
    recent_opens = await db.tracking_events.count_documents(
        {
            "campaign_id": campaign_id,
            "event_type": "open",
            "timestamp": {"$gte": now - timedelta(days=7)},
        }
    )
    previous_opens = await db.tracking_events.count_documents(
        {
            "campaign_id": campaign_id,
            "event_type": "open",
            "timestamp": {
                "$gte": now - timedelta(days=14),
                "$lt": now - timedelta(days=7),
            },
        }
    )

    if previous_opens > 0:
        trend_pct = ((recent_opens - previous_opens) / previous_opens) * 100
    else:
        trend_pct = 100.0 if recent_opens > 0 else 0.0

    trend_direction = "up" if trend_pct > 0 else ("down" if trend_pct < 0 else "flat")

    return {
        "campaign_id": campaign_id,
        "stats": stats,
        "top_leads": [
            {
                "lead_id": l["id"],
                "email": l.get("email", ""),
                "name": f'{l.get("first_name", "")} {l.get("last_name", "")}'.strip(),
                "engagement_score": l.get("engagement_score", 0),
            }
            for l in top_leads
        ],
        "trend": {
            "direction": trend_direction,
            "percentage": round(trend_pct, 1),
            "recent_opens": recent_opens,
            "previous_opens": previous_opens,
        },
    }


async def _compute_analytics(campaign_id: str) -> dict:
    """Live-compute analytics from emails and tracking events."""
    db = await get_database()

    emails_sent = await db.emails.count_documents(
        {"campaign_id": campaign_id, "status": "sent"}
    )
    emails_failed = await db.emails.count_documents(
        {"campaign_id": campaign_id, "status": "failed"}
    )

    pipeline = [
        {"$match": {"campaign_id": campaign_id}},
        {
            "$group": {
                "_id": "$event_type",
                "count": {"$sum": 1},
                "unique_emails": {"$addToSet": "$email_id"},
            }
        },
    ]
    agg = await db.tracking_events.aggregate(pipeline).to_list(length=10)

    opens = clicks = replies = unique_opens = unique_clicks = 0
    for r in agg:
        if r["_id"] == "open":
            opens = r["count"]
            unique_opens = len(r["unique_emails"])
        elif r["_id"] == "click":
            clicks = r["count"]
            unique_clicks = len(r["unique_emails"])
        elif r["_id"] == "reply":
            replies = r["count"]

    open_rate = (unique_opens / emails_sent * 100) if emails_sent > 0 else 0.0
    click_rate = (unique_clicks / emails_sent * 100) if emails_sent > 0 else 0.0
    reply_rate = (replies / emails_sent * 100) if emails_sent > 0 else 0.0

    return {
        "campaign_id": campaign_id,
        "emails_sent": emails_sent,
        "emails_failed": emails_failed,
        "total_opens": opens,
        "unique_opens": unique_opens,
        "total_clicks": clicks,
        "unique_clicks": unique_clicks,
        "total_replies": replies,
        "open_rate": round(open_rate, 2),
        "click_rate": round(click_rate, 2),
        "reply_rate": round(reply_rate, 2),
    }