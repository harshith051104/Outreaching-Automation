"""
Application-wide constants.

These values are intentionally hard-coded and NOT loaded from environment
variables because they define the domain vocabulary of the platform.
"""

import base64

REPLY_CLASSIFICATIONS: list[str] = [
    "interested",
    "meeting_requested",
    "not_interested",
    "follow_up_later",
    "spam",
]

CAMPAIGN_STATUSES: list[str] = [
    "draft",
    "active",
    "paused",
    "completed",
]

EMAIL_STATUSES: list[str] = [
    "pending",
    "sent",
    "delivered",
    "bounced",
    "failed",
]

LEAD_STATUSES: list[str] = [
    "new",
    "contacted",
    "engaged",
    "qualified",
    "converted",
    "lost",
]

TRACKING_EVENT_TYPES: list[str] = [
    "open",
    "click",
    "reply",
    "bounce",
]

MAX_CSV_ROWS: int = 10_000

DEFAULT_FOLLOWUP_DELAY_HOURS: int = 48

_TRACKING_PIXEL_BYTES: bytes = (
    b"\x47\x49\x46\x38\x39\x61"
    b"\x01\x00\x01\x00"
    b"\x80\x00\x00"
    b"\xff\xff\xff"
    b"\x00\x00\x00"
    b"\x21\xf9\x04"
    b"\x01\x00\x00\x00\x00"
    b"\x2c\x00\x00\x00\x00"
    b"\x01\x00\x01\x00\x00"
    b"\x02\x02\x44\x01\x00"
    b"\x3b"
)

TRACKING_PIXEL_BASE64: str = base64.b64encode(_TRACKING_PIXEL_BYTES).decode("ascii")