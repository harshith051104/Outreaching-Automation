"""
Abstract base for email providers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ProviderResult:
    """Result from a provider send call."""
    success: bool = False
    message_id: Optional[str] = None
    thread_id: Optional[str] = None
    label_ids: List[str] = field(default_factory=list)
    error: Optional[str] = None


class BaseEmailProvider(ABC):
    """Abstract email provider interface."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier (e.g. 'gmail', 'sendgrid')."""

    @abstractmethod
    async def send(
        self,
        to: str,
        subject: str,
        body_html: str,
        from_email: Optional[str] = None,
        from_name: Optional[str] = None,
        thread_id: Optional[str] = None,
        in_reply_to: Optional[str] = None,
        references: Optional[str] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
    ) -> ProviderResult:
        """Send an email."""

    @abstractmethod
    async def check_connection(self, account_id: str) -> bool:
        """Verify the provider account is still valid/connected."""

    @abstractmethod
    async def get_inbox(self, account_id: str, max_results: int = 20) -> List[Dict[str, Any]]:
        """Fetch recent inbox messages."""

    @abstractmethod
    async def get_thread(self, account_id: str, thread_id: str) -> List[Dict[str, Any]]:
        """Fetch all messages in a thread."""

    @abstractmethod
    async def check_replies(self, account_id: str, thread_ids: List[str]) -> List[Dict[str, Any]]:
        """Check threads for new replies."""
