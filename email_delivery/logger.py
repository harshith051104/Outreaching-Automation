"""
Structured logging for the email subsystem.
"""

import logging


def get_logger(name: str) -> logging.Logger:
    """Get a logger with email subsystem prefix."""
    return logging.getLogger(f"email_delivery.{name}")
