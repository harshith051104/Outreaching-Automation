"""
Gmail reply tracking and detection.

Provides utilities for detecting new replies in Gmail threads
and correlating them with tracked emails.
"""

from typing import Any


def is_reply_from_lead(from_header: str, lead_email: str) -> bool:
    """
    Check if an incoming message is from the original lead (not from the sender).

    Args:
        from_header: The From header from the Gmail message.
        lead_email: The lead's email address.

    Returns:
        True if the message is from the lead, False if from the sender.
    """
    if not from_header or not lead_email:
        return False

    # Extract email from "Name <email>" format
    if "<" in from_header:
        email = from_header.split("<")[1].split(">")[0].strip()
    else:
        email = from_header.strip()

    return email.lower() == lead_email.lower()


def extract_reply_body(message_payload: dict) -> str:
    """
    Extract the reply body text from a Gmail message payload.

    Handles both plain text and HTML parts.

    Args:
        message_payload: The 'payload' dict from a Gmail API message.

    Returns:
        Extracted body text.
    """
    body = ""

    # Try body.data first (for simple messages)
    if message_payload.get("body", {}).get("data"):
        import base64
        try:
            body = base64.urlsafe_b64decode(
                message_payload["body"]["data"]
            ).decode("utf-8", errors="replace")
        except Exception:
            pass

    # Try parts for multipart messages
    if not body and message_payload.get("parts"):
        for part in message_payload["parts"]:
            if part.get("mimeType") == "text/plain" and part.get("body", {}).get("data"):
                import base64
                try:
                    body = base64.urlsafe_b64decode(
                        part["body"]["data"]
                    ).decode("utf-8", errors="replace")
                    break
                except Exception:
                    continue
            elif part.get("mimeType") == "text/html" and part.get("body", {}).get("data") and not body:
                # Fall back to HTML if no plain text
                import base64
                try:
                    body = base64.urlsafe_b64decode(
                        part["body"]["data"]
                    ).decode("utf-8", errors="replace")
                except Exception:
                    continue

    return body
