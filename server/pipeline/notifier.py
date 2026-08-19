"""
pipeline/notifier.py
====================
Crash & error notification system.

Sends alerts to the admin's personal devices when the pipeline crashes
or encounters critical errors. Supports two channels:

  1. Email   — via Gmail SMTP (free, no API key needed)
  2. Telegram — via Telegram Bot API (free, instant push notification)

Configure via environment variables (see .env.example):
  ALERT_EMAIL_TO         — recipient email address
  ALERT_EMAIL_FROM       — sender Gmail address
  ALERT_EMAIL_PASSWORD   — Gmail App Password (NOT your Gmail login password)
  TELEGRAM_BOT_TOKEN     — Telegram bot token from @BotFather
  TELEGRAM_CHAT_ID       — Your personal chat ID (get from @userinfobot)
"""

import os
import traceback
import threading
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# ─── Configuration ────────────────────────────────────────────────────────────
EMAIL_TO       = os.getenv("ALERT_EMAIL_TO")
EMAIL_FROM     = os.getenv("ALERT_EMAIL_FROM")
EMAIL_PASSWORD = os.getenv("ALERT_EMAIL_PASSWORD")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT  = os.getenv("TELEGRAM_CHAT_ID")

# Rate limiting: avoid flooding during cascading failures
_last_alert_time = {}
COOLDOWN_SECONDS = 60  # Minimum gap between duplicate alerts


def _should_send(key: str) -> bool:
    """Return True if we haven't sent an alert with this key recently."""
    now = datetime.now().timestamp()
    last = _last_alert_time.get(key, 0)
    if now - last < COOLDOWN_SECONDS:
        return False
    _last_alert_time[key] = now
    return True


def _send_email(subject: str, body: str):
    """Send alert email via Gmail SMTP. Runs in background thread."""
    if not all([EMAIL_TO, EMAIL_FROM, EMAIL_PASSWORD]):
        return

    try:
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart

        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"🚨 Verity Alert: {subject}"
        msg["From"]    = EMAIL_FROM
        msg["To"]      = EMAIL_TO

        # Plain text version
        text_part = MIMEText(body, "plain")
        msg.attach(text_part)

        # HTML version (looks better on phone)
        html_body = f"""
        <div style="font-family: -apple-system, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background: #1a1a2e; color: #fff; padding: 16px 20px; border-radius: 8px 8px 0 0;">
                <h2 style="margin: 0; font-size: 18px;">🚨 Verity Pipeline Alert</h2>
            </div>
            <div style="background: #16213e; color: #e0e0e0; padding: 20px; border-radius: 0 0 8px 8px; font-size: 14px;">
                <p style="margin: 0 0 12px 0;"><strong>Subject:</strong> {subject}</p>
                <p style="margin: 0 0 12px 0;"><strong>Time:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')}</p>
                <pre style="background: #0f3460; padding: 12px; border-radius: 6px; overflow-x: auto; font-size: 12px; color: #ff6b6b; white-space: pre-wrap;">{body}</pre>
            </div>
        </div>
        """
        html_part = MIMEText(html_body, "html")
        msg.attach(html_part)

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_FROM, EMAIL_PASSWORD)
            server.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())

        print(f"[notifier] Email sent to {EMAIL_TO}")
    except Exception as e:
        print(f"[notifier] Email failed: {e}")


# ─── Public API ───────────────────────────────────────────────────────────────

def notify_error(subject: str, error: Exception | str, context: str = ""):
    """
    Send an error notification to configured email.
    
    Args:
        subject:  Short description (e.g. "Pipeline Crash", "Ingestion Failed")
        error:    The exception or error message string
        context:  Optional extra context (e.g. which file was being processed)
    """
    # Build the alert key for rate-limiting
    alert_key = f"{subject}:{str(error)[:100]}"
    if not _should_send(alert_key):
        print(f"[notifier] Rate-limited: {subject}")
        return

    # Build detailed body
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S IST")
    if isinstance(error, Exception):
        error_text = f"{type(error).__name__}: {str(error)}"
        tb = traceback.format_exception(type(error), error, error.__traceback__)
        stack_trace = "".join(tb)
    else:
        error_text = str(error)
        stack_trace = ""

    body = f"Time: {timestamp}\n"
    if context:
        body += f"Context: {context}\n"
    body += f"Error: {error_text}\n"
    if stack_trace:
        body += f"\nStack Trace:\n{stack_trace}"

    # Fire email channel in background thread (non-blocking)
    threading.Thread(target=_send_email, args=(subject, body), daemon=True).start()


def notify_info(subject: str, message: str):
    """
    Send an informational notification (e.g. ingestion complete).
    """
    alert_key = f"info:{subject}"
    if not _should_send(alert_key):
        return

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S IST")
    body = (
        f"Time: {timestamp}\n\n"
        f"Message:\n{message}"
    )
    
    threading.Thread(target=_send_email, args=(subject, body), daemon=True).start()
