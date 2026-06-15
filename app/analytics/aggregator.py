"""
Analytics aggregation utilities.

Provides functions to compute campaign performance metrics
from tracking events and email data.
"""

from typing import Any


def compute_open_rate(total_sent: int, unique_opens: int) -> float:
    """Compute open rate as a percentage."""
    if total_sent == 0:
        return 0.0
    return round((unique_opens / total_sent) * 100, 2)


def compute_click_rate(total_sent: int, unique_clicks: int) -> float:
    """Compute click rate as a percentage."""
    if total_sent == 0:
        return 0.0
    return round((unique_clicks / total_sent) * 100, 2)


def compute_reply_rate(total_sent: int, total_replies: int) -> float:
    """Compute reply rate as a percentage."""
    if total_sent == 0:
        return 0.0
    return round((total_replies / total_sent) * 100, 2)


def compute_bounce_rate(total_sent: int, total_bounces: int) -> float:
    """Compute bounce rate as a percentage."""
    if total_sent == 0:
        return 0.0
    return round((total_bounces / total_sent) * 100, 2)


def compute_positive_reply_rate(total_replies: int, positive_replies: int) -> float:
    """Compute positive reply rate as a percentage of all replies."""
    if total_replies == 0:
        return 0.0
    return round((positive_replies / total_replies) * 100, 2)


def aggregate_lead_engagement(events: list[dict]) -> dict[str, Any]:
    """
    Aggregate tracking events for a lead into engagement summary.

    Args:
        events: List of tracking event documents for a lead.

    Returns:
        Engagement summary dict with counts and timestamps.
    """
    opens = [e for e in events if e.get("event_type") == "open"]
    clicks = [e for e in events if e.get("event_type") == "click"]
    replies = [e for e in events if e.get("event_type") == "reply"]

    first_open = opens[0]["timestamp"] if opens else None
    last_open = opens[-1]["timestamp"] if opens else None
    first_click = clicks[0]["timestamp"] if clicks else None

    return {
        "total_events": len(events),
        "open_count": len(opens),
        "click_count": len(clicks),
        "reply_count": len(replies),
        "first_open_at": first_open,
        "last_open_at": last_open,
        "first_click_at": first_click,
        "engagement_score": (
            len(opens) * 1 +
            len(clicks) * 2 +
            len(replies) * 5
        ),
    }


def compute_campaign_health(analytics: dict) -> str:
    """
    Compute an overall health grade for a campaign based on metrics.

    Args:
        analytics: Campaign analytics dict with open_rate, click_rate, reply_rate.

    Returns:
        Health grade: "excellent", "good", "needs_attention", "critical".
    """
    open_rate = analytics.get("open_rate", 0)
    reply_rate = analytics.get("reply_rate", 0)

    if open_rate >= 30 and reply_rate >= 5:
        return "excellent"
    elif open_rate >= 20 and reply_rate >= 2:
        return "good"
    elif open_rate >= 10:
        return "needs_attention"
    else:
        return "critical"
