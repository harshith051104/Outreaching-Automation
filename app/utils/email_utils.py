"""
Email HTML utilities for tracking pixel injection and link rewriting.

These utilities modify outgoing email HTML to insert tracking elements
that call back to the platform when opened or clicked.
"""

import base64
import re
from urllib.parse import quote, urlencode

from app.config.constants import TRACKING_PIXEL_BASE64
from app.config.settings import settings


def build_tracking_pixel_url(tracking_id: str) -> str:
    """
    Build the full URL for the tracking pixel endpoint.
    """
    return f"{settings.BACKEND_URL}/api/track/open/{tracking_id}"


def inject_tracking_pixel(html: str, tracking_id: str) -> str:
    """
    Inject an invisible tracking pixel at the end of the email HTML.
    """
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


def build_click_tracking_url(tracking_id: str, original_url: str) -> str:
    """
    Build a tracked click URL that redirects through our tracker.
    """
    encoded_url = quote(original_url, safe="")
    return (
        f"{settings.BACKEND_URL}/api/track/click/{tracking_id}"
        f"?url={encoded_url}"
    )


def replace_links_with_tracking(html: str, tracking_id: str) -> str:
    """
    Replace all href URLs in <a> tags with tracked redirect URLs.

    Skips mailto: links, anchor links (#), and empty links.
    """
    def replace_href(match: re.Match) -> str:
        full_tag = match.group(0)
        original_url = match.group(1)

        original_url = original_url.strip()
        if not original_url:
            return full_tag
        if original_url.startswith(("mailto:", "tel:", "#", "javascript:")):
            return full_tag

        tracked_url = build_click_tracking_url(tracking_id, original_url)
        return full_tag.replace(original_url, tracked_url)

    pattern = re.compile(r'<a[^>]*\shref=["\']([^"\']+)["\']', re.IGNORECASE)
    return pattern.sub(replace_href, html)


def get_tracking_pixel_base64() -> str:
    """Return the base64-encoded tracking pixel GIF."""
    return TRACKING_PIXEL_BASE64


def get_tracking_pixel_bytes() -> bytes:
    """Return the raw bytes of the tracking pixel GIF."""
    return base64.b64decode(TRACKING_PIXEL_BASE64)