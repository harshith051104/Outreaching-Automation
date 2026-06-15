"""
Email HTML template utilities.

Provides reusable email template functions with consistent styling
and structure for outreach emails.
"""

from app.config.constants import TRACKING_PIXEL_BASE64


def base_email_template(
    title: str,
    preview_text: str,
    header_content: str,
    body_content: str,
    footer_content: str,
    tracking_pixel_html: str = "",
) -> str:
    """
    Generate a responsive HTML email template.

    Args:
        title: Page <title> and email subject preview context.
        preview_text: Email preview/snippet text (shown in inbox).
        header_content: HTML content for the header section.
        body_content: HTML content for the main body.
        footer_content: HTML content for the footer.
        tracking_pixel_html: Optional tracking pixel to inject.

    Returns:
        Complete HTML email document.
    """
    return f"""<!DOCTYPE html>
<html lang="en" xmlns="http://www.w3.org/1999/xhtml">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="X-UA-Compatible" content="IE=edge">
    <meta name="x-apple-disable-message-reformatting">
    <title>{title}</title>
    <!--[if mso]>
    <noscript>
        <xml>
            <o:OfficeDocumentSettings>
                <o:AllowPNG/>
                <o:PixelsPerInch>96</o:PixelsPerInch>
            </o:OfficeDocumentSettings>
        </xml>
    </noscript>
    <![endif]-->
    <style>
        body {{
            margin: 0;
            padding: 0;
            background-color: #f4f4f4;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            -webkit-font-smoothing: antialiased;
        }}
        .email-container {{
            max-width: 600px;
            margin: 0 auto;
            background-color: #ffffff;
        }}
        .email-header {{
            background-color: #1a1a2e;
            padding: 32px 40px;
            text-align: center;
        }}
        .email-body {{
            padding: 40px;
        }}
        .email-footer {{
            background-color: #f4f4f4;
            padding: 24px 40px;
            text-align: center;
            font-size: 12px;
            color: #666666;
        }}
        h1 {{
            margin: 0;
            font-size: 24px;
            font-weight: 600;
            color: #ffffff;
        }}
        p {{
            margin: 0 0 16px;
            line-height: 1.6;
            color: #333333;
        }}
        .cta-button {{
            display: inline-block;
            background-color: #4f46e5;
            color: #ffffff;
            padding: 12px 24px;
            text-decoration: none;
            border-radius: 6px;
            font-weight: 600;
            margin: 16px 0;
        }}
        .preheader {{
            display: none;
            visibility: hidden;
            mso-hide: all;
            font-size: 1px;
            line-height: 1px;
            max-height: 0;
            max-width: 0;
            opacity: 0;
            overflow: hidden;
        }}
        @media only screen and (max-width: 480px) {{
            .email-body {{
                padding: 24px !important;
            }}
            .email-header {{
                padding: 24px !important;
            }}
        }}
    </style>
</head>
<body>
    <!-- Preheader text (shown in email clients as preview) -->
    <div class="preheader">{preview_text}</div>

    <div class="email-container">
        <!-- Header -->
        <div class="email-header">
            {header_content}
        </div>

        <!-- Body -->
        <div class="email-body">
            {body_content}
        </div>

        <!-- Footer -->
        <div class="email-footer">
            {footer_content}
        </div>

        <!-- Tracking pixel -->
        {tracking_pixel_html}
    </div>
</body>
</html>"""


def simple_text_email(body_html: str, recipient_name: str = "") -> str:
    """
    Generate a simple text-based email for cold outreach.

    Args:
        body_html: Main body content (paragraphs, etc.).
        recipient_name: Optional recipient name for personalization.

    Returns:
        Complete HTML email.
    """
    greeting = f"<p>Hi {recipient_name},</p>" if recipient_name else "<p>Hi there,</p>"

    return base_email_template(
        title="New message",
        preview_text="Quick question from [Your Name]",
        header_content="<h1>👋</h1>",
        body_content=greeting + body_html,
        footer_content=(
            "<p>You received this email because you're awesome.</p>"
            "<p><a href='*|UNSUB|'>Unsubscribe</a> · <a href='{{privacy_url}}'>Privacy</a></p>"
        ),
    )


def get_default_footer(sender_name: str = "", company: str = "") -> str:
    """
    Generate a default footer for outbound emails.

    Args:
        sender_name: Name of the sending user.
        company: Company name.

    Returns:
        HTML footer string.
    """
    return f"""
    <p style="margin: 0; font-size: 12px; color: #888888; line-height: 1.4;">
        {sender_name}<br>
        {company}
    </p>
    """
