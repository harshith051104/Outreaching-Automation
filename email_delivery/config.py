"""
Email subsystem configuration.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.config.settings import settings


@dataclass
class EmailConfig:
    """Configuration for the email delivery subsystem."""
    backend_url: str = ""
    default_retry_policy: str = "exponential"
    max_retry_attempts: int = 3
    retry_base_delay_seconds: float = 5.0
    retry_max_delay_seconds: float = 300.0
    daily_send_limit: int = 50
    hourly_send_limit: int = 50
    tracking_pixel_enabled: bool = True
    click_tracking_enabled: bool = True
    open_tracking_weight: float = 1.0
    click_tracking_weight: float = 2.0
    reply_tracking_weight: float = 5.0
    attachment_tracking_weight: float = 3.0

    @classmethod
    def from_settings(cls) -> "EmailConfig":
        return cls(backend_url=settings.BACKEND_URL)


email_config = EmailConfig.from_settings()
