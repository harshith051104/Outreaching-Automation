"""
CSV parsing utilities for lead imports.

Supports standard CSV formats with flexible column name matching.
"""

import csv
import io
from typing import Any

from app.config.constants import MAX_CSV_ROWS


COLUMN_ALIASES: dict[str, str] = {
    "email": "email",
    "emailaddress": "email",
    "email_address": "email",
    "firstname": "first_name",
    "first_name": "first_name",
    "lastname": "last_name",
    "last_name": "last_name",
    "name": "first_name",
    "fullname": "first_name",
    "company": "company",
    "company_name": "company",
    "organization": "company",
    "title": "title",
    "job_title": "title",
    "role": "title",
    "phone": "phone",
    "phone_number": "phone",
    "linkedin": "linkedin_url",
    "linkedin_url": "linkedin_url",
    "website": "website",
    "url": "website",
    "industry": "industry",
}


def normalize_column_name(col: str) -> str:
    """Map a CSV column header to the canonical key name."""
    col_lower = col.lower().strip().replace(" ", "_")
    return COLUMN_ALIASES.get(col_lower, col_lower)


def parse_leads_csv(file_content: bytes) -> list[dict[str, Any]]:
    """
    Parse a CSV file containing lead data.

    Args:
        file_content: Raw bytes of the CSV file.

    Returns:
        List of dictionaries, each representing a lead row.

    Raises:
        ValueError: If the CSV is malformed or exceeds MAX_CSV_ROWS.
    """
    try:
        text = file_content.decode("utf-8")
    except UnicodeDecodeError:
        for encoding in ["latin-1", "cp1252"]:
            try:
                text = file_content.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        else:
            raise ValueError("Unable to decode CSV file. Ensure UTF-8 encoding.")

    reader = csv.DictReader(io.StringIO(text))

    if not reader.fieldnames:
        raise ValueError("CSV file is empty or has no headers.")

    canonical_fields = [normalize_column_name(f) for f in reader.fieldnames]
    reader.fieldnames = canonical_fields

    rows: list[dict[str, Any]] = []
    for i, row in enumerate(reader, start=1):
        if i > MAX_CSV_ROWS:
            break

        if not row.get("email", "").strip():
            continue

        cleaned = {k: (v.strip() if isinstance(v, str) else "") for k, v in row.items()}
        rows.append(cleaned)

    return rows


def validate_lead_row(row: dict[str, Any]) -> tuple[bool, str]:
    """
    Validate a single lead row.

    Returns:
        Tuple of (is_valid, error_message).
    """
    email = row.get("email", "").strip()
    if not email:
        return False, "Missing email field"

    if "@" not in email or "." not in email.split("@")[-1]:
        return False, f"Invalid email format: {email}"

    return True, ""