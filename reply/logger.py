"""
Structured logging for the reply subsystem.
"""

import logging
from typing import Any, Optional


def get_reply_logger(
    name: str,
    execution_id: Optional[str] = None,
    campaign_id: Optional[str] = None,
    lead_id: Optional[str] = None,
    thread_id: Optional[str] = None,
    message_id: Optional[str] = None,
) -> logging.Logger:
    """
    Get a logger with reply subsystem context.

    All fields are attached as extra attributes for structured log aggregation.
    """
    logger = logging.getLogger(f"reply.{name}")

    # Attach context as log record factory
    old_factory = logging.getLogRecordFactory()

    def record_factory(*args: Any, **kwargs: Any) -> logging.LogRecord:
        record = old_factory(*args, **kwargs)
        if execution_id:
            record.execution_id = execution_id
        if campaign_id:
            record.campaign_id = campaign_id
        if lead_id:
            record.lead_id = lead_id
        if thread_id:
            record.thread_id = thread_id
        if message_id:
            record.message_id = message_id
        return record

    logging.setLogRecordFactory(record_factory)
    return logger
