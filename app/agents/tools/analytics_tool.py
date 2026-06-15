"""
Analytics Tool for Campaign Performance Tracking.

Parses, computes, and formats campaign metrics into structured
summaries that agents can use for analysis and recommendations.
"""

import json
import logging
from typing import Type
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class CampaignMetricsInput(BaseModel):
    """Input schema for the Campaign Metrics Tool."""
    campaign_data: str = Field(
        ...,
        description=(
            "Campaign performance data as a JSON string. Expected keys include: "
            "emails_sent, emails_delivered, emails_opened, emails_clicked, "
            "emails_replied, emails_bounced, unsubscribes, and optionally "
            "leads (list of dicts with lead-level engagement data)."
        ),
    )


class CampaignMetricsTool:
    """
    Retrieves and formats campaign performance metrics for analysis.

    Accepts raw campaign data as JSON, computes derived metrics
    (open rate, click rate, reply rate, etc.), identifies top performers,
    and returns a structured summary ready for agent consumption.
    """

    def __init__(self):
        self.name = "Campaign Metrics Tool"
        self.description = (
            "Retrieve and format campaign performance metrics for analysis. "
            "Computes open rates, click rates, reply rates, bounce rates, "
            "and identifies top-performing leads."
        )

    def run(self, campaign_data: str) -> str:
        return self._run(campaign_data)

    def _run(self, campaign_data: str) -> str:
        """Parse campaign data, compute derived metrics, and return a formatted summary."""
        try:
            data = json.loads(campaign_data)
        except json.JSONDecodeError:
            return json.dumps({
                "error": "Invalid JSON in campaign_data. Please provide valid JSON.",
                "raw_input": campaign_data[:500],
            })

        emails_sent = data.get("emails_sent", 0)
        emails_delivered = data.get("emails_delivered", emails_sent)
        emails_opened = data.get("emails_opened", 0)
        emails_clicked = data.get("emails_clicked", 0)
        emails_replied = data.get("emails_replied", 0)
        emails_bounced = data.get("emails_bounced", 0)
        unsubscribes = data.get("unsubscribes", 0)
        leads = data.get("leads", [])

        def safe_rate(numerator: int, denominator: int) -> float:
            if denominator == 0:
                return 0.0
            return round((numerator / denominator) * 100, 2)

        delivery_rate = safe_rate(emails_delivered, emails_sent)
        open_rate = safe_rate(emails_opened, emails_delivered)
        click_rate = safe_rate(emails_clicked, emails_delivered)
        reply_rate = safe_rate(emails_replied, emails_delivered)
        bounce_rate = safe_rate(emails_bounced, emails_sent)
        unsubscribe_rate = safe_rate(unsubscribes, emails_delivered)
        click_to_open_rate = safe_rate(emails_clicked, emails_opened)

        benchmarks = {
            "open_rate": 21.5,
            "click_rate": 2.3,
            "reply_rate": 1.0,
            "bounce_rate": 2.0,
            "unsubscribe_rate": 0.3,
        }

        def vs_benchmark(actual: float, benchmark: float) -> str:
            diff = actual - benchmark
            if abs(diff) < 0.5:
                return "at_benchmark"
            return "above_benchmark" if diff > 0 else "below_benchmark"

        benchmark_comparison = {
            "open_rate": vs_benchmark(open_rate, benchmarks["open_rate"]),
            "click_rate": vs_benchmark(click_rate, benchmarks["click_rate"]),
            "reply_rate": vs_benchmark(reply_rate, benchmarks["reply_rate"]),
            "bounce_rate": vs_benchmark(bounce_rate, benchmarks["bounce_rate"]),
            "unsubscribe_rate": vs_benchmark(unsubscribe_rate, benchmarks["unsubscribe_rate"]),
        }

        top_leads: list[dict] = []
        if leads:
            scored_leads = []
            for lead in leads:
                engagement_score = 0
                if lead.get("opened"):
                    engagement_score += 1
                if lead.get("clicked"):
                    engagement_score += 2
                if lead.get("replied"):
                    engagement_score += 5
                if lead.get("meeting_booked"):
                    engagement_score += 10
                scored_leads.append({
                    "lead_id": lead.get("lead_id", "unknown"),
                    "email": lead.get("email", "unknown"),
                    "name": lead.get("name", "unknown"),
                    "engagement_score": engagement_score,
                    "opened": lead.get("opened", False),
                    "clicked": lead.get("clicked", False),
                    "replied": lead.get("replied", False),
                })
            scored_leads.sort(key=lambda x: x["engagement_score"], reverse=True)
            top_leads = scored_leads[:10]

        funnel = {
            "sent": emails_sent,
            "delivered": emails_delivered,
            "opened": emails_opened,
            "clicked": emails_clicked,
            "replied": emails_replied,
        }

        health_issues: list[str] = []
        if bounce_rate > 5:
            health_issues.append("High bounce rate — clean your email list.")
        if unsubscribe_rate > 1:
            health_issues.append("High unsubscribe rate — review content relevance.")
        if open_rate < 10:
            health_issues.append("Very low open rate — improve subject lines.")
        if click_rate < 1 and open_rate > 15:
            health_issues.append("Opens but no clicks — improve email body and CTA.")
        if reply_rate < 0.5 and open_rate > 20:
            health_issues.append("Good opens but low replies — strengthen call to action.")

        overall_health = (
            "healthy" if not health_issues
            else "needs_attention" if len(health_issues) <= 2
            else "critical"
        )

        summary = {
            "campaign_summary": {
                "raw_counts": {
                    "emails_sent": emails_sent,
                    "emails_delivered": emails_delivered,
                    "emails_opened": emails_opened,
                    "emails_clicked": emails_clicked,
                    "emails_replied": emails_replied,
                    "emails_bounced": emails_bounced,
                    "unsubscribes": unsubscribes,
                },
                "rates": {
                    "delivery_rate": delivery_rate,
                    "open_rate": open_rate,
                    "click_rate": click_rate,
                    "reply_rate": reply_rate,
                    "bounce_rate": bounce_rate,
                    "unsubscribe_rate": unsubscribe_rate,
                    "click_to_open_rate": click_to_open_rate,
                },
                "benchmark_comparison": benchmark_comparison,
                "industry_benchmarks": benchmarks,
            },
            "engagement_funnel": funnel,
            "top_performing_leads": top_leads,
            "health": {
                "status": overall_health,
                "issues": health_issues,
            },
        }

        return json.dumps(summary, indent=2)