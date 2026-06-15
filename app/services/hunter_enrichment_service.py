"""
Hunter.io email verification service.
"""

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

HAS_HUNTER = True

try:
    import httpx
    from app.config.settings import settings
except ImportError:
    HAS_HUNTER = False


class HunterEnrichmentService:
    """Service for verifying emails via Hunter.io."""

    def __init__(self):
        self.api_key = settings.HUNTER_API_KEY
        self.base_url = "https://api.hunter.io/v2"

    async def verify_email(self, email: str) -> Dict[str, Any]:
        """Verify an email address using Hunter.io."""
        if not self.api_key:
            logger.warning("Hunter API key not set")
            return {"status": "unknown", "score": 0}

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/email-verifier",
                    params={"email": email, "api_key": self.api_key},
                )

                if response.status_code == 200:
                    data = response.json().get("data", {})
                    status = data.get("status", "unknown")
                    score = data.get("score", 0)

                    return {
                        "email": email,
                        "status": status,
                        "score": score,
                        "deliverable": status in ["valid", "deliverable"],
                        "reason": data.get("result", ""),
                    }
                else:
                    return {"email": email, "status": "unknown", "score": 0}
        except Exception as e:
            logger.error(f"Hunter verification error: {e}")
            return {"email": email, "status": "unknown", "score": 0}

    async def domain_search(self, domain: str) -> Dict[str, Any]:
        """Search for email patterns at a domain."""
        if not self.api_key:
            return {}

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/domain-search",
                    params={"domain": domain, "api_key": self.api_key},
                )

                if response.status_code == 200:
                    return response.json()
                return {}
        except Exception as e:
            logger.error(f"Hunter domain search error: {e}")
            return {}