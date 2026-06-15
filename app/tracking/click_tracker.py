"""
Click tracking redirect utilities.

Provides functions to record click events and redirect to the
original destination URL.
"""

from urllib.parse import unquote


def parse_click_url(url_param: str) -> str:
    """
    Parse and decode a click tracking URL parameter.

    Args:
        url_param: The encoded destination URL from the query string.

    Returns:
        Decoded original URL.
    """
    if not url_param or url_param == "None":
        return ""
    return unquote(url_param)


def build_tracking_redirect(location: str) -> dict:
    """
    Build response headers for a 302 redirect to the original URL.

    Args:
        location: The decoded destination URL.

    Returns:
        Dict of HTTP headers for the redirect response.
    """
    return {
        "Location": location,
        "Cache-Control": "no-cache, no-store, must-revalidate",
    }
