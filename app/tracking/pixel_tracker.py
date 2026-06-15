"""
Tracking pixel serving utilities.

Provides functions to serve tracking pixels (1x1 transparent GIF)
for email open tracking.
"""

import base64

from app.config.constants import TRACKING_PIXEL_BASE64, _TRACKING_PIXEL_BYTES


def get_pixel_headers() -> dict:
    """
    Return cache-control headers to prevent browser caching of the tracking pixel.

    Returns:
        Dict of HTTP headers for the tracking pixel response.
    """
    return {
        "Content-Type": "image/gif",
        "Cache-Control": "no-store, no-cache, must-revalidate, proxy-revalidate",
        "Pragma": "no-cache",
        "Expires": "0",
        "Content-Length": str(len(_TRACKING_PIXEL_BYTES)),
    }


def get_pixel_response() -> tuple[bytes, dict]:
    """
    Get the raw pixel bytes and headers for an HTTP response.

    Returns:
        Tuple of (pixel_bytes, headers_dict).
    """
    return _TRACKING_PIXEL_BYTES, get_pixel_headers()
