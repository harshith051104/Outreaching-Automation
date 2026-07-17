"""
Email Delivery & Tracking subsystem.

Modular, provider-agnostic email infrastructure with:
- Pluggable email providers (Gmail default, extensible)
- Full email status lifecycle tracking
- Retry policies (NONE, FIXED, EXPONENTIAL, EXPONENTIAL_JITTER)
- Open/click/reply tracking with engagement scoring
"""

from email_delivery.models import EmailStatus, RetryPolicy, EmailRecord, TrackingEvent
from email_delivery.delivery_manager import DeliveryManager

__all__ = [
    "EmailStatus",
    "RetryPolicy",
    "EmailRecord",
    "TrackingEvent",
    "DeliveryManager",
]
