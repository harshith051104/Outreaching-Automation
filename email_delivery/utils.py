"""
Email HTML utilities — tracking pixel injection and link rewriting.
"""

from __future__ import annotations

import re

from app.config.constants import TRACKING_PIXEL_BASE64
from app.config.settings import settings


def build_tracking_pixel_url(tracking_id: str) -> str:
    return f"{settings.BACKEND_URL}/api/track/open/{tracking_id}"


def inject_tracking_pixel(html: str, tracking_id: str) -> str:
    pixel_url = build_tracking_pixel_url(tracking_id)
    pixel_html = (
        f'<img src="{pixel_url}" width="1" height="1" '
        f'alt="" style="display:none;border:0;outline:none;" '
        f'loading="lazy" />'
    )
    if "</body>" in html.lower():
        return re.sub(r"(?i)</body>", f"{pixel_html}</body>", html, count=1)
    else:
        return html + pixel_html


def get_tracking_pixel_bytes() -> bytes:
    import base64
    return base64.b64decode(TRACKING_PIXEL_BASE64)
