"""
Google Sheets integration service.

Allows exporting tasks and campaign analytics to Google Spreadsheets
using the user's authenticated Google Account credentials.
"""

import logging
from datetime import datetime, timezone
from typing import Any, List, Optional
from fastapi import HTTPException, status
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.auth.exceptions import RefreshError
from googleapiclient.discovery import build

from app.config.mongodb_config import get_database
from app.config.settings import settings
from app.config.gmail_config import refresh_credentials

logger = logging.getLogger(__name__)


async def _get_google_credentials(user_id: str) -> Credentials:
    """Retrieve and refresh Google credentials for a user."""
    db = await get_database()
    account = await db.gmail_accounts.find_one({"user_id": user_id, "is_active": True})
    
    if not account:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active Google account connected. Please connect your Google account in Settings."
        )

    creds = Credentials(
        token=account["access_token"],
        refresh_token=account.get("refresh_token"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
    )

    if creds.expired and creds.refresh_token:
        try:
            refreshed = refresh_credentials({
                "access_token": creds.token,
                "refresh_token": creds.refresh_token,
                "token_uri": creds.token_uri,
                "client_id": creds.client_id,
                "client_secret": creds.client_secret,
                "scopes": creds.scopes,
            })
            await db.gmail_accounts.update_one(
                {"id": account["id"]},
                {
                    "$set": {
                        "access_token": refreshed["access_token"],
                        "updated_at": datetime.now(timezone.utc),
                    }
                },
            )
            creds.token = refreshed["access_token"]
            logger.info("Successfully refreshed Google credentials for user %s", user_id)
        except Exception as e:
            logger.error("Failed to refresh Google credentials: %s", e)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Google login session expired. Please re-authenticate your Google account."
            )

    return creds


async def create_and_fill_spreadsheet(
    user_id: str,
    title: str,
    headers: List[str],
    rows: List[List[Any]]
) -> dict:
    """
    Creates a new Google Spreadsheet in the user's Google Drive,
    populates it with the headers and rows, makes it link-shareable,
    and returns its details.
    """
    creds = await _get_google_credentials(user_id)
    
    try:
        # Build Google Sheets and Drive services
        sheets_service = build("sheets", "v4", credentials=creds, cache_discovery=False)
        drive_service = build("drive", "v3", credentials=creds, cache_discovery=False)
        
        # 1. Create Spreadsheet
        spreadsheet_body = {
            "properties": {
                "title": title
            }
        }
        logger.info("Creating Google Spreadsheet titled: '%s'...", title)
        spreadsheet = sheets_service.spreadsheets().create(
            body=spreadsheet_body,
            fields="spreadsheetId,spreadsheetUrl,sheets(properties(sheetId,title))"
        ).execute()
        
        spreadsheet_id = spreadsheet.get("spreadsheetId")
        spreadsheet_url = spreadsheet.get("spreadsheetUrl")
        
        sheets = spreadsheet.get("sheets", [])
        sheet_id = 0
        if sheets:
            sheet_id = sheets[0].get("properties", {}).get("sheetId", 0)

        # 2. Format and layout values
        is_analytics = any("Metric" in h or "Summary" in h or "Date" in h or "Open Rate" in h for h in headers)
        is_tasks = "Task ID" in headers
        
        # Define clean, beautiful color constants matching modern dark/light UI
        INDIGO_BANNER = {"red": 30 / 255, "green": 27 / 255, "blue": 75 / 255}      # #1E1B4B deep indigo
        TEXT_LIGHT_INDIGO = {"red": 199 / 255, "green": 210 / 255, "blue": 254 / 255} # #C7D2FE
        SLATE_DARK = {"red": 15 / 255, "green": 23 / 255, "blue": 42 / 255}         # #0F172A
        WHITE = {"red": 1.0, "green": 1.0, "blue": 1.0}
        LIGHT_PURPLE_BG = {"red": 245 / 255, "green": 243 / 255, "blue": 255 / 255} # #F5F3FF
        PURPLE_TEXT = {"red": 107 / 255, "green": 33 / 255, "blue": 168 / 255}      # #6B21A8
        VIBRANT_INDIGO = {"red": 79 / 255, "green": 70 / 255, "blue": 229 / 255}    # #4F46E5
        SLATE_TEXT = {"red": 71 / 255, "green": 85 / 255, "blue": 105 / 255}         # #475569
        LIGHT_GRAY_BG = {"red": 248 / 255, "green": 250 / 255, "blue": 252 / 255}   # #F8FAFC
        BORDER_LIGHT_VAL = {"red": 226 / 255, "green": 232 / 255, "blue": 240 / 255} # #E2E8F0
        BORDER_CARD_VAL = {"red": 199 / 255, "green": 210 / 255, "blue": 254 / 255}  # #C7D2FE
        
        border_light = {"style": "SOLID", "color": BORDER_LIGHT_VAL}
        border_card = {"style": "SOLID", "color": BORDER_CARD_VAL}
        
        # Task Status & Priority formatting configs
        STATUS_COLORS = {
            "completed": {
                "bg": {"red": 220/255, "green": 252/255, "blue": 231/255}, # #DCFCE7
                "text": {"red": 22/255, "green": 101/255, "blue": 52/255}  # #166534
            },
            "in_progress": {
                "bg": {"red": 219/255, "green": 234/255, "blue": 254/255}, # #DBEAFE
                "text": {"red": 30/255, "green": 64/255, "blue": 175/255}   # #1E40AF
            },
            "todo": {
                "bg": {"red": 241/255, "green": 245/255, "blue": 249/255}, # #F1F5F9
                "text": {"red": 71/255, "green": 85/255, "blue": 105/255}   # #475569
            }
        }
        
        PRIORITY_COLORS = {
            "high": {
                "bg": {"red": 254/255, "green": 226/255, "blue": 226/255}, # #FEE2E2
                "text": {"red": 153/255, "green": 27/255, "blue": 27/255}  # #991B1B
            },
            "medium": {
                "bg": {"red": 254/255, "green": 243/255, "blue": 199/255}, # #FEF3C7
                "text": {"red": 146/255, "green": 64/255, "blue": 14/255}   # #92400E
            },
            "low": {
                "bg": {"red": 241/255, "green": 245/255, "blue": 249/255}, # #F1F5F9
                "text": {"red": 71/255, "green": 85/255, "blue": 105/255}   # #475569
            }
        }

        def safe_float_pct(val):
            if val is None:
                return 0.0
            try:
                if isinstance(val, (int, float)):
                    return float(val) / 100.0
                s_val = str(val).replace("%", "").strip()
                if not s_val:
                    return 0.0
                return float(s_val) / 100.0
            except ValueError:
                return 0.0

        def safe_int(val):
            if val is None:
                return 0
            try:
                if isinstance(val, (int, float)):
                    return int(val)
                s_val = str(val).strip()
                if not s_val:
                    return 0
                return int(float(s_val))
            except ValueError:
                return 0

        values = []
        styling_requests = []

        if is_analytics and len(rows) >= 3:
            # Reconstruction for Analytics report layout
            summary_row = rows[0]
            detail_rows = rows[3:] if len(rows) > 3 else []
            clean_headers = ["Campaign Name / Date", "Sent", "Opened", "Clicked", "Replied", "Open Rate", "Click Rate", "Reply Rate"]
            num_cols = len(clean_headers)
            
            # Row 0: Banner Title
            values.append([title] + [""] * (num_cols - 1))
            # Row 1: Subtitle
            now_str = datetime.now(timezone.utc).strftime("%b %d, %Y %I:%M %p UTC")
            values.append([f"Report Generated: {now_str} | Workspace Performance Stats"] + [""] * (num_cols - 1))
            # Row 2: Spacer
            values.append([""] * num_cols)
            # Row 3: KPI Card Labels
            values.append(["SUMMARY OVERVIEW", "TOTAL SENT", "TOTAL OPENS", "TOTAL CLICKS", "TOTAL REPLIES", "OPEN RATE", "CLICK RATE", "REPLY RATE"])
            
            # Row 4: KPI Card Values
            kpi_title = str(summary_row[0])
            sent_val = safe_int(summary_row[1]) if len(summary_row) > 1 else 0
            opens_val = safe_int(summary_row[2]) if len(summary_row) > 2 else 0
            clicks_val = safe_int(summary_row[3]) if len(summary_row) > 3 else 0
            replies_val = safe_int(summary_row[4]) if len(summary_row) > 4 else 0
            open_rate_val = safe_float_pct(summary_row[5]) if len(summary_row) > 5 else 0.0
            click_rate_val = safe_float_pct(summary_row[6]) if len(summary_row) > 6 else 0.0
            reply_rate_val = safe_float_pct(summary_row[7]) if len(summary_row) > 7 else 0.0
            
            values.append([kpi_title, sent_val, opens_val, clicks_val, replies_val, open_rate_val, click_rate_val, reply_rate_val])
            # Row 5: Spacer
            values.append([""] * num_cols)
            # Row 6: Section title
            section_title = str(rows[2][0]) if len(rows) > 2 else "BREAKDOWN STATS"
            values.append([section_title] + [""] * (num_cols - 1))
            # Row 7: Table Headers
            values.append(clean_headers)
            
            # Row 8+: Detail rows
            start_data_row_idx = len(values)
            for r in detail_rows:
                if not r or not str(r[0]).strip() or "SUMMARY" in str(r[0]) or "BREAKDOWN" in str(r[0]):
                    values.append([""] * num_cols)
                else:
                    d_title = str(r[0])
                    d_sent = safe_int(r[1]) if len(r) > 1 else 0
                    d_opens = safe_int(r[2]) if len(r) > 2 else 0
                    d_clicks = safe_int(r[3]) if len(r) > 3 else 0
                    d_replies = safe_int(r[4]) if len(r) > 4 else 0
                    d_open_rate = safe_float_pct(r[5]) if len(r) > 5 else 0.0
                    d_click_rate = safe_float_pct(r[6]) if len(r) > 6 else 0.0
                    d_reply_rate = safe_float_pct(r[7]) if len(r) > 7 else 0.0
                    
                    values.append([d_title, d_sent, d_opens, d_clicks, d_replies, d_open_rate, d_click_rate, d_reply_rate])
            
            end_row_idx = len(values)
            
            # Styling requests for Analytics:
            # Merges
            styling_requests.append({
                "mergeCells": {
                    "range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 1, "startColumnIndex": 0, "endColumnIndex": num_cols},
                    "mergeType": "MERGE_ALL"
                }
            })
            styling_requests.append({
                "mergeCells": {
                    "range": {"sheetId": sheet_id, "startRowIndex": 1, "endRowIndex": 2, "startColumnIndex": 0, "endColumnIndex": num_cols},
                    "mergeType": "MERGE_ALL"
                }
            })
            styling_requests.append({
                "mergeCells": {
                    "range": {"sheetId": sheet_id, "startRowIndex": 3, "endRowIndex": 5, "startColumnIndex": 0, "endColumnIndex": 1},
                    "mergeType": "MERGE_ALL"
                }
            })
            styling_requests.append({
                "mergeCells": {
                    "range": {"sheetId": sheet_id, "startRowIndex": 6, "endRowIndex": 7, "startColumnIndex": 0, "endColumnIndex": num_cols},
                    "mergeType": "MERGE_ALL"
                }
            })
            
            # Heights
            row_heights = [
                (0, 1, 48), (1, 2, 22), (2, 3, 15),
                (3, 4, 24), (4, 5, 34), (5, 6, 20),
                (6, 7, 30), (7, 8, 35)
            ]
            for start, end, size in row_heights:
                styling_requests.append({
                    "updateDimensionProperties": {
                        "range": {"sheetId": sheet_id, "dimension": "ROWS", "startIndex": start, "endIndex": end},
                        "properties": {"pixelSize": size},
                        "fields": "pixelSize"
                    }
                })
            styling_requests.append({
                "updateDimensionProperties": {
                    "range": {"sheetId": sheet_id, "dimension": "ROWS", "startIndex": 8, "endIndex": end_row_idx},
                    "properties": {"pixelSize": 25},
                    "fields": "pixelSize"
                }
            })
            
            # Base font
            styling_requests.append({
                "repeatCell": {
                    "range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": end_row_idx, "startColumnIndex": 0, "endColumnIndex": num_cols},
                    "cell": {
                        "userEnteredFormat": {
                            "textFormat": {"fontFamily": "Outfit", "fontSize": 10},
                            "verticalAlignment": "MIDDLE"
                        }
                    },
                    "fields": "userEnteredFormat(textFormat,verticalAlignment)"
                }
            })
            
            # Banner format
            styling_requests.append({
                "repeatCell": {
                    "range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 1, "startColumnIndex": 0, "endColumnIndex": num_cols},
                    "cell": {
                        "userEnteredFormat": {
                            "backgroundColor": INDIGO_BANNER,
                            "textFormat": {"foregroundColor": WHITE, "bold": True, "fontSize": 15, "fontFamily": "Outfit"},
                            "horizontalAlignment": "CENTER"
                        }
                    },
                    "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment)"
                }
            })
            styling_requests.append({
                "repeatCell": {
                    "range": {"sheetId": sheet_id, "startRowIndex": 1, "endRowIndex": 2, "startColumnIndex": 0, "endColumnIndex": num_cols},
                    "cell": {
                        "userEnteredFormat": {
                            "backgroundColor": INDIGO_BANNER,
                            "textFormat": {"foregroundColor": TEXT_LIGHT_INDIGO, "italic": True, "fontSize": 9, "fontFamily": "Outfit"},
                            "horizontalAlignment": "CENTER"
                        }
                    },
                    "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment)"
                }
            })
            
            # KPI Card format
            styling_requests.append({
                "repeatCell": {
                    "range": {"sheetId": sheet_id, "startRowIndex": 3, "endRowIndex": 4, "startColumnIndex": 0, "endColumnIndex": num_cols},
                    "cell": {
                        "userEnteredFormat": {
                            "backgroundColor": LIGHT_PURPLE_BG,
                            "textFormat": {"foregroundColor": PURPLE_TEXT, "bold": True, "fontSize": 8, "fontFamily": "Outfit"},
                            "horizontalAlignment": "CENTER",
                            "borders": {"top": border_card, "left": border_card, "right": border_card}
                        }
                    },
                    "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment,borders)"
                }
            })
            styling_requests.append({
                "repeatCell": {
                    "range": {"sheetId": sheet_id, "startRowIndex": 4, "endRowIndex": 5, "startColumnIndex": 0, "endColumnIndex": num_cols},
                    "cell": {
                        "userEnteredFormat": {
                            "backgroundColor": LIGHT_PURPLE_BG,
                            "textFormat": {"foregroundColor": SLATE_DARK, "bold": True, "fontSize": 13, "fontFamily": "Outfit"},
                            "horizontalAlignment": "CENTER",
                            "borders": {"bottom": border_card, "left": border_card, "right": border_card}
                        }
                    },
                    "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment,borders)"
                }
            })
            
            styling_requests.append({
                "repeatCell": {
                    "range": {"sheetId": sheet_id, "startRowIndex": 3, "endRowIndex": 5, "startColumnIndex": 0, "endColumnIndex": 1},
                    "cell": {
                        "userEnteredFormat": {
                            "textFormat": {"foregroundColor": SLATE_DARK, "bold": True, "fontSize": 11},
                            "horizontalAlignment": "CENTER"
                        }
                    },
                    "fields": "userEnteredFormat(textFormat,horizontalAlignment)"
                }
            })
            
            styling_requests.append({
                "repeatCell": {
                    "range": {"sheetId": sheet_id, "startRowIndex": 4, "endRowIndex": 5, "startColumnIndex": 1, "endColumnIndex": 5},
                    "cell": {
                        "userEnteredFormat": {"numberFormat": {"type": "NUMBER", "pattern": "#,##0"}}
                    },
                    "fields": "userEnteredFormat(numberFormat)"
                }
            })
            styling_requests.append({
                "repeatCell": {
                    "range": {"sheetId": sheet_id, "startRowIndex": 4, "endRowIndex": 5, "startColumnIndex": 5, "endColumnIndex": num_cols},
                    "cell": {
                        "userEnteredFormat": {"numberFormat": {"type": "PERCENT", "pattern": "0.0%"}}
                    },
                    "fields": "userEnteredFormat(numberFormat)"
                }
            })
            
            # Section title format
            styling_requests.append({
                "repeatCell": {
                    "range": {"sheetId": sheet_id, "startRowIndex": 6, "endRowIndex": 7, "startColumnIndex": 0, "endColumnIndex": num_cols},
                    "cell": {
                        "userEnteredFormat": {
                            "textFormat": {"foregroundColor": VIBRANT_INDIGO, "bold": True, "fontSize": 11, "fontFamily": "Outfit"},
                            "horizontalAlignment": "LEFT",
                            "borders": {"bottom": {"style": "DOUBLE", "color": VIBRANT_INDIGO}}
                        }
                    },
                    "fields": "userEnteredFormat(textFormat,horizontalAlignment,borders)"
                }
            })
            
            # Table Header formatting
            styling_requests.append({
                "repeatCell": {
                    "range": {"sheetId": sheet_id, "startRowIndex": 7, "endRowIndex": 8, "startColumnIndex": 0, "endColumnIndex": num_cols},
                    "cell": {
                        "userEnteredFormat": {
                            "backgroundColor": SLATE_DARK,
                            "textFormat": {"foregroundColor": WHITE, "bold": True, "fontSize": 10, "fontFamily": "Outfit"},
                            "horizontalAlignment": "CENTER"
                        }
                    },
                    "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment)"
                }
            })
            styling_requests.append({
                "repeatCell": {
                    "range": {"sheetId": sheet_id, "startRowIndex": 7, "endRowIndex": 8, "startColumnIndex": 0, "endColumnIndex": 1},
                    "cell": {
                        "userEnteredFormat": {"horizontalAlignment": "LEFT"}
                    },
                    "fields": "userEnteredFormat(horizontalAlignment)"
                }
            })
            
            # Detail rows formatting
            for row_idx in range(start_data_row_idx, end_row_idx):
                bg = WHITE
                if row_idx % 2 == 1:
                    bg = LIGHT_GRAY_BG
                
                styling_requests.append({
                    "repeatCell": {
                        "range": {"sheetId": sheet_id, "startRowIndex": row_idx, "endRowIndex": row_idx + 1, "startColumnIndex": 0, "endColumnIndex": num_cols},
                        "cell": {
                            "userEnteredFormat": {
                                "backgroundColor": bg,
                                "borders": {"top": border_light, "bottom": border_light, "left": border_light, "right": border_light}
                            }
                        },
                        "fields": "userEnteredFormat(backgroundColor,borders)"
                    }
                })
                
                # Alignments and number patterns
                styling_requests.append({
                    "repeatCell": {
                        "range": {"sheetId": sheet_id, "startRowIndex": row_idx, "endRowIndex": row_idx + 1, "startColumnIndex": 0, "endColumnIndex": 1},
                        "cell": {
                            "userEnteredFormat": {"horizontalAlignment": "LEFT"}
                        },
                        "fields": "userEnteredFormat(horizontalAlignment)"
                    }
                })
                
                styling_requests.append({
                    "repeatCell": {
                        "range": {"sheetId": sheet_id, "startRowIndex": row_idx, "endRowIndex": row_idx + 1, "startColumnIndex": 1, "endColumnIndex": 5},
                        "cell": {
                            "userEnteredFormat": {
                                "horizontalAlignment": "CENTER",
                                "numberFormat": {"type": "NUMBER", "pattern": "#,##0"}
                            }
                        },
                        "fields": "userEnteredFormat(horizontalAlignment,numberFormat)"
                    }
                })
                styling_requests.append({
                    "repeatCell": {
                        "range": {"sheetId": sheet_id, "startRowIndex": row_idx, "endRowIndex": row_idx + 1, "startColumnIndex": 5, "endColumnIndex": 8},
                        "cell": {
                            "userEnteredFormat": {
                                "horizontalAlignment": "CENTER",
                                "numberFormat": {"type": "PERCENT", "pattern": "0.0%"}
                            }
                        },
                        "fields": "userEnteredFormat(horizontalAlignment,numberFormat)"
                    }
                })

        elif is_tasks:
            # Reconstruction for Tasks Tracker
            num_cols = len(headers)
            clean_headers = ["Task ID", "Title", "Description", "Status", "Priority", "Creator", "Assignee", "Due Date", "Created At"]
            
            # Row 0: Banner Title
            values.append([title] + [""] * (num_cols - 1))
            # Row 1: Subtitle
            now_str = datetime.now(timezone.utc).strftime("%b %d, %Y %I:%M %p UTC")
            values.append([f"Report Generated: {now_str} | Active Tasks Tracker"] + [""] * (num_cols - 1))
            # Row 2: Spacer
            values.append([""] * num_cols)
            # Row 3: Headers
            values.append(clean_headers)
            
            # Row 4+: Data formatting
            for r in rows:
                formatted_row = []
                for item in r:
                    if item is None:
                        formatted_row.append("")
                    elif isinstance(item, (datetime, str)):
                        formatted_row.append(str(item))
                    else:
                        formatted_row.append(item)
                values.append(formatted_row)
                
            end_row_idx = len(values)
            
            # Merges
            styling_requests.append({
                "mergeCells": {
                    "range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 1, "startColumnIndex": 0, "endColumnIndex": num_cols},
                    "mergeType": "MERGE_ALL"
                }
            })
            styling_requests.append({
                "mergeCells": {
                    "range": {"sheetId": sheet_id, "startRowIndex": 1, "endRowIndex": 2, "startColumnIndex": 0, "endColumnIndex": num_cols},
                    "mergeType": "MERGE_ALL"
                }
            })
            
            # Heights
            row_heights = [
                (0, 1, 48), (1, 2, 22), (2, 3, 15), (3, 4, 35)
            ]
            for start, end, size in row_heights:
                styling_requests.append({
                    "updateDimensionProperties": {
                        "range": {"sheetId": sheet_id, "dimension": "ROWS", "startIndex": start, "endIndex": end},
                        "properties": {"pixelSize": size},
                        "fields": "pixelSize"
                    }
                })
            styling_requests.append({
                "updateDimensionProperties": {
                    "range": {"sheetId": sheet_id, "dimension": "ROWS", "startIndex": 4, "endIndex": end_row_idx},
                    "properties": {"pixelSize": 25},
                    "fields": "pixelSize"
                }
            })
            
            # Font
            styling_requests.append({
                "repeatCell": {
                    "range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": end_row_idx, "startColumnIndex": 0, "endColumnIndex": num_cols},
                    "cell": {
                        "userEnteredFormat": {
                            "textFormat": {"fontFamily": "Outfit", "fontSize": 10},
                            "verticalAlignment": "MIDDLE"
                        }
                    },
                    "fields": "userEnteredFormat(textFormat,verticalAlignment)"
                }
            })
            
            # Banner formats
            styling_requests.append({
                "repeatCell": {
                    "range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 1, "startColumnIndex": 0, "endColumnIndex": num_cols},
                    "cell": {
                        "userEnteredFormat": {
                            "backgroundColor": INDIGO_BANNER,
                            "textFormat": {"foregroundColor": WHITE, "bold": True, "fontSize": 15, "fontFamily": "Outfit"},
                            "horizontalAlignment": "CENTER"
                        }
                    },
                    "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment)"
                }
            })
            styling_requests.append({
                "repeatCell": {
                    "range": {"sheetId": sheet_id, "startRowIndex": 1, "endRowIndex": 2, "startColumnIndex": 0, "endColumnIndex": num_cols},
                    "cell": {
                        "userEnteredFormat": {
                            "backgroundColor": INDIGO_BANNER,
                            "textFormat": {"foregroundColor": TEXT_LIGHT_INDIGO, "italic": True, "fontSize": 9, "fontFamily": "Outfit"},
                            "horizontalAlignment": "CENTER"
                        }
                    },
                    "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment)"
                }
            })
            
            # Header formatting
            styling_requests.append({
                "repeatCell": {
                    "range": {"sheetId": sheet_id, "startRowIndex": 3, "endRowIndex": 4, "startColumnIndex": 0, "endColumnIndex": num_cols},
                    "cell": {
                        "userEnteredFormat": {
                            "backgroundColor": SLATE_DARK,
                            "textFormat": {"foregroundColor": WHITE, "bold": True, "fontSize": 10, "fontFamily": "Outfit"},
                            "horizontalAlignment": "CENTER"
                        }
                    },
                    "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment)"
                }
            })
            for col_idx in [0, 1, 2, 5, 6]:
                styling_requests.append({
                    "repeatCell": {
                        "range": {"sheetId": sheet_id, "startRowIndex": 3, "endRowIndex": 4, "startColumnIndex": col_idx, "endColumnIndex": col_idx + 1},
                        "cell": {
                            "userEnteredFormat": {"horizontalAlignment": "LEFT"}
                        },
                        "fields": "userEnteredFormat(horizontalAlignment)"
                    }
                })
                
            # Formatting Data Rows (Row index 4+)
            for row_idx in range(4, end_row_idx):
                bg = WHITE
                if row_idx % 2 == 1:
                    bg = LIGHT_GRAY_BG
                    
                styling_requests.append({
                    "repeatCell": {
                        "range": {"sheetId": sheet_id, "startRowIndex": row_idx, "endRowIndex": row_idx + 1, "startColumnIndex": 0, "endColumnIndex": num_cols},
                        "cell": {
                            "userEnteredFormat": {
                                "backgroundColor": bg,
                                "borders": {"top": border_light, "bottom": border_light, "left": border_light, "right": border_light}
                            }
                        },
                        "fields": "userEnteredFormat(backgroundColor,borders)"
                    }
                })
                
                # Align columns
                for col_idx in [0, 1, 2, 5, 6]:
                    styling_requests.append({
                        "repeatCell": {
                            "range": {"sheetId": sheet_id, "startRowIndex": row_idx, "endRowIndex": row_idx + 1, "startColumnIndex": col_idx, "endColumnIndex": col_idx + 1},
                            "cell": {
                                "userEnteredFormat": {"horizontalAlignment": "LEFT"}
                            },
                            "fields": "userEnteredFormat(horizontalAlignment)"
                        }
                    })
                for col_idx in [3, 4, 7, 8]:
                    styling_requests.append({
                        "repeatCell": {
                            "range": {"sheetId": sheet_id, "startRowIndex": row_idx, "endRowIndex": row_idx + 1, "startColumnIndex": col_idx, "endColumnIndex": col_idx + 1},
                            "cell": {
                                "userEnteredFormat": {"horizontalAlignment": "CENTER"}
                            },
                            "fields": "userEnteredFormat(horizontalAlignment)"
                        }
                    })
                
                # Priority / Status styles
                raw_row = rows[row_idx - 4]
                status_val = str(raw_row[3]).lower() if len(raw_row) > 3 else ""
                priority_val = str(raw_row[4]).lower() if len(raw_row) > 4 else ""
                
                if status_val in STATUS_COLORS:
                    color_cfg = STATUS_COLORS[status_val]
                    cell_patch = {
                        "backgroundColor": color_cfg["bg"],
                        "textFormat": {"foregroundColor": color_cfg["text"], "bold": True}
                    }
                    if status_val == "completed":
                        cell_patch["textFormat"]["strikethrough"] = True
                        
                    styling_requests.append({
                        "repeatCell": {
                            "range": {"sheetId": sheet_id, "startRowIndex": row_idx, "endRowIndex": row_idx + 1, "startColumnIndex": 3, "endColumnIndex": 4},
                            "cell": {
                                "userEnteredFormat": cell_patch
                            },
                            "fields": "userEnteredFormat(backgroundColor,textFormat)"
                        }
                    })
                    
                if priority_val in PRIORITY_COLORS:
                    color_cfg = PRIORITY_COLORS[priority_val]
                    styling_requests.append({
                        "repeatCell": {
                            "range": {"sheetId": sheet_id, "startRowIndex": row_idx, "endRowIndex": row_idx + 1, "startColumnIndex": 4, "endColumnIndex": 5},
                            "cell": {
                                "userEnteredFormat": {
                                    "backgroundColor": color_cfg["bg"],
                                    "textFormat": {"foregroundColor": color_cfg["text"], "bold": True}
                                }
                            },
                            "fields": "userEnteredFormat(backgroundColor,textFormat)"
                        }
                    })

        else:
            # Simple fallback format
            num_cols = len(headers)
            values.append(headers)
            for r in rows:
                formatted_row = []
                for item in r:
                    if item is None:
                        formatted_row.append("")
                    elif isinstance(item, (datetime, str)):
                        formatted_row.append(str(item))
                    else:
                        formatted_row.append(item)
                values.append(formatted_row)
                
            end_row_idx = len(values)
            
            styling_requests.append({
                "repeatCell": {
                    "range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 1, "startColumnIndex": 0, "endColumnIndex": num_cols},
                    "cell": {
                        "userEnteredFormat": {
                            "backgroundColor": SLATE_DARK,
                            "textFormat": {"foregroundColor": WHITE, "bold": True, "fontFamily": "Outfit"},
                            "horizontalAlignment": "CENTER"
                        }
                    },
                    "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment)"
                }
            })
            
            for row_idx in range(1, end_row_idx):
                bg = WHITE
                if row_idx % 2 == 1:
                    bg = LIGHT_GRAY_BG
                styling_requests.append({
                    "repeatCell": {
                        "range": {"sheetId": sheet_id, "startRowIndex": row_idx, "endRowIndex": row_idx + 1, "startColumnIndex": 0, "endColumnIndex": num_cols},
                        "cell": {
                            "userEnteredFormat": {
                                "backgroundColor": bg,
                                "borders": {"top": border_light, "bottom": border_light, "left": border_light, "right": border_light}
                            }
                        },
                        "fields": "userEnteredFormat(backgroundColor,borders)"
                    }
                })

        # 3. Update values in Sheet1
        logger.info("Writing formatted data to spreadsheet %s...", spreadsheet_id)
        sheets_service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range="Sheet1!A1",
            valueInputOption="RAW",
            body={"values": values}
        ).execute()

        # Auto-fit columns based on text size
        styling_requests.append({
            "autoResizeDimensions": {
                "dimensions": {
                    "sheetId": sheet_id,
                    "dimension": "COLUMNS",
                    "startIndex": 0,
                    "endIndex": num_cols
                }
            }
        })

        logger.info("Applying custom design styles to spreadsheet %s...", spreadsheet_id)
        sheets_service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": styling_requests}
        ).execute()
        
        # 4. Make it public link-shareable
        logger.info("Setting permission to anyone-with-link on spreadsheet %s", spreadsheet_id)
        permission = {
            "type": "anyone",
            "role": "reader"
        }
        drive_service.permissions().create(
            fileId=spreadsheet_id,
            body=permission,
            fields="id"
        ).execute()
        
        return {
            "success": True,
            "spreadsheet_id": spreadsheet_id,
            "spreadsheet_url": spreadsheet_url,
            "title": title
        }
        
    except RefreshError as re_err:
        logger.error("Google credentials expired or revoked for user %s: %s", user_id, re_err)
        try:
            db = await get_database()
            await db.gmail_accounts.update_one(
                {"user_id": user_id, "is_active": True},
                {"$set": {"is_active": False, "connection_error": "Token has been expired or revoked."}}
            )
        except Exception as update_exc:
            logger.error("Failed to mark account inactive: %s", update_exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google account disconnected. Please reconnect your Google account in Settings."
        )
    except Exception as e:
        logger.exception("Google Spreadsheet export failed for user %s", user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Google Sheets API Error: {str(e)}"
        )
