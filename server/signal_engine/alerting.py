import os
import asyncio
import smtplib
from email.message import EmailMessage
from signal_engine.models import SignalSchema
from signal_engine.logger import get_structured_logger

logger = get_structured_logger("signal_engine.alerting")

class NotificationService:
    """
    Alerting Engine to send high-conviction signals via Email.
    """
    def __init__(self):
        self.email_to = os.getenv("ALERT_EMAIL_TO")
        self.email_from = os.getenv("ALERT_EMAIL_FROM")
        self.email_password = os.getenv("ALERT_EMAIL_PASSWORD")
        self.dashboard_url = os.getenv("DASHBOARD_URL", "http://localhost:5173/signals")

    async def send_alert(self, signal: SignalSchema) -> bool:
        """Formats and sends the alert payload via Email."""
        if not self.email_to or not self.email_from or not self.email_password:
            logger.warning("Email credentials not found. Skipping alert dispatch.")
            return False

        subject = f"✨ Verity Alert: {signal.symbol} ({signal.strength_score:.1f}/100)"
        
        # Determine color based on score
        color = "#22c55e" if signal.strength_score >= 85 else "#eab308"
        label = "CRITICAL BUY" if signal.strength_score >= 85 else "HIGH BUY"
        
        # Parse content
        technical_reason = signal.expert_summary.split('Analyst Verdict:')[0].strip()
        verdict = ""
        if "Analyst Verdict:" in signal.expert_summary:
            verdict = signal.expert_summary.split("Analyst Verdict:")[1].strip()

        # Build HTML
        html_body = f"""
        <html>
            <body style="font-family: Arial, sans-serif; background-color: #f9f9f9; padding: 20px; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                    <div style="background-color: #0f172a; padding: 20px; text-align: center;">
                        <h1 style="color: white; margin: 0; font-size: 24px;">Verity Engine</h1>
                    </div>
                    
                    <div style="padding: 30px;">
                        <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #eee; padding-bottom: 15px; margin-bottom: 20px;">
                            <h2 style="margin: 0; color: #1e293b; font-size: 28px;">{signal.symbol}</h2>
                            <div style="background-color: {color}; color: white; padding: 6px 12px; border-radius: 20px; font-weight: bold; font-size: 14px;">
                                {label} ({signal.strength_score:.1f})
                            </div>
                        </div>
                        
                        <h3 style="color: #475569; margin-bottom: 10px; font-size: 16px;">📊 Quantitative Triggers</h3>
                        <div style="background-color: #f8fafc; padding: 15px; border-radius: 6px; border-left: 4px solid #3b82f6; margin-bottom: 25px; line-height: 1.6;">
                            {technical_reason.replace(chr(10), '<br>')}
                        </div>
        """
        
        if verdict:
            # Format bullets
            verdict_html = verdict.replace('•', '<br>•').replace(chr(10), '<br>')
            if verdict_html.startswith('<br>'): verdict_html = verdict_html[4:]
            
            html_body += f"""
                        <h3 style="color: #475569; margin-bottom: 10px; font-size: 16px;">🧠 AI Context (Fundamental Alignment)</h3>
                        <div style="background-color: #f8fafc; padding: 15px; border-radius: 6px; border-left: 4px solid #8b5cf6; margin-bottom: 25px; line-height: 1.6;">
                            {verdict_html}
                        </div>
            """
            
        html_body += f"""
                        <div style="text-align: center; margin-top: 30px;">
                            <a href="{self.dashboard_url}" style="background-color: #0f172a; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold; display: inline-block;">View in Command Center</a>
                        </div>
                    </div>
                    <div style="background-color: #f1f5f9; text-align: center; padding: 15px; font-size: 12px; color: #64748b;">
                        Automated by Verity Signal Engine. Not financial advice.
                    </div>
                </div>
            </body>
        </html>
        """

        msg = EmailMessage()
        msg['Subject'] = subject
        msg['From'] = self.email_from
        msg['To'] = self.email_to
        
        # Set plain text fallback first
        fallback_text = f"Symbol: {signal.symbol}\nScore: {signal.strength_score}\nReason:\n{technical_reason}\n\nAI Context:\n{verdict}"
        msg.set_content(fallback_text)
        
        # Then add HTML
        msg.add_alternative(html_body, subtype='html')

        # Run SMTP operations in a separate thread so it doesn't block the async event loop
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(None, self._send_smtp_email, msg)
            logger.info(f"Email alert dispatched for {signal.symbol}")
            return True
        except Exception as e:
            logger.error(f"Failed to send Email alert", extra={"extra_info": {"error": str(e)}})
            return False
            
    def _send_smtp_email(self, msg: EmailMessage):
        """Blocking function to handle SMTP connection."""
        # Using Gmail SMTP settings as default (can be adapted if using another provider)
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(self.email_from, self.email_password)
            smtp.send_message(msg)
