"""
Email Agent - Personalized email sequence generation and sending
Supports Resend, SendGrid, and Gmail SMTP
Steps 48-58: Email generation, sequences, follow-ups, tracking
"""
import httpx
import json
import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

# Email provider config
EMAIL_PROVIDER = os.getenv("EMAIL_PROVIDER", "resend")  # resend | sendgrid | smtp
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", "")
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
FROM_EMAIL = os.getenv("FROM_EMAIL", "")
FROM_NAME = os.getenv("FROM_NAME", "GTM Engineer")

# LLM for email personalization
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

EMAIL_SYSTEM_PROMPT = """
You are an expert B2B sales email writer. Write concise, personalized cold emails that:
- Open with a specific insight about the prospect's company
- Clearly state the value proposition in 1-2 sentences
- End with a single low-friction CTA (e.g., "Worth a 15-min call?")
- Are under 150 words
- Sound human, not automated
Return JSON with keys: subject, body
"""


class EmailAgent:
  """Generates personalized emails and sends them via Resend, SendGrid, or SMTP"""

  def __init__(self):
    self.provider = EMAIL_PROVIDER
    self.from_email = FROM_EMAIL
    self.from_name = FROM_NAME

  # ── Email Generation ────────────────────────────────────────────────────────

  async def generate_email(self, prospect: Dict, company_research: Dict) -> Dict[str, str]:
    """Use LLM to generate a personalized cold email"""
    if not OPENAI_API_KEY:
      return {
        "subject": f"Quick question for {prospect.get('name', 'you')}",
        "body": f"Hi {prospect.get('name', 'there')},\n\nI came across {company_research.get('company', 'your company')} and wanted to reach out.\n\nWould you be open to a quick call?\n\nBest,\n{FROM_NAME}"
      }

    context = f"""
Prospect: {prospect.get('name')} - {prospect.get('title')} at {prospect.get('company')}
Company Research Summary:
- Overview: {company_research.get('analysis', {}).get('overview', 'N/A')}
- Pain Points: {company_research.get('analysis', {}).get('pain_points', 'N/A')}
- Tech Stack: {company_research.get('analysis', {}).get('tech_stack', 'N/A')}
- Recent News: {company_research.get('analysis', {}).get('recent_news', 'N/A')}
Sender: {FROM_NAME}
"""
    messages = [
      {"role": "system", "content": EMAIL_SYSTEM_PROMPT},
      {"role": "user", "content": context}
    ]
    async with httpx.AsyncClient(timeout=60) as client:
      resp = await client.post(
        f"{OPENAI_BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
        json={"model": OPENAI_MODEL, "messages": messages, "temperature": 0.7, "max_tokens": 500}
      )
      content = resp.json()["choices"][0]["message"]["content"]
      try:
        clean = content.strip()
        if clean.startswith("```"):
          clean = clean.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        return json.loads(clean)
      except Exception:
        return {"subject": "Quick question", "body": content}

  async def generate_sequence(self, prospect: Dict, company_research: Dict, num_emails: int = 3) -> List[Dict]:
    """Generate a multi-step email sequence (initial + follow-ups)"""
    sequence = []
    for step in range(1, num_emails + 1):
      if step == 1:
        email = await self.generate_email(prospect, company_research)
      else:
        email = {
          "subject": f"Re: {sequence[0].get('subject', 'Quick question')}",
          "body": f"Hi {prospect.get('name', 'there')},\n\nJust following up on my previous email.\n\nWould love to find 15 minutes to connect.\n\nBest,\n{FROM_NAME}"
        }
      sequence.append({"step": step, "delay_days": (step - 1) * 3, **email})
    return sequence

  # ── Email Sending ─────────────────────────────────────────────────────────────

  async def send_via_resend(self, to_email: str, subject: str, body: str) -> Dict:
    """Send email via Resend API"""
    async with httpx.AsyncClient(timeout=30) as client:
      resp = await client.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"},
        json={
          "from": f"{self.from_name} <{self.from_email}>",
          "to": [to_email],
          "subject": subject,
          "text": body
        }
      )
      data = resp.json()
      return {"provider": "resend", "id": data.get("id"), "status": "sent" if resp.status_code == 200 else "failed"}

  async def send_via_sendgrid(self, to_email: str, subject: str, body: str) -> Dict:
    """Send email via SendGrid API"""
    async with httpx.AsyncClient(timeout=30) as client:
      resp = await client.post(
        "https://api.sendgrid.com/v3/mail/send",
        headers={"Authorization": f"Bearer {SENDGRID_API_KEY}", "Content-Type": "application/json"},
        json={
          "personalizations": [{"to": [{"email": to_email}]}],
          "from": {"email": self.from_email, "name": self.from_name},
          "subject": subject,
          "content": [{"type": "text/plain", "value": body}]
        }
      )
      return {"provider": "sendgrid", "status": "sent" if resp.status_code == 202 else "failed"}

  def send_via_smtp(self, to_email: str, subject: str, body: str) -> Dict:
    """Send email via SMTP (Gmail or other)"""
    try:
      msg = MIMEMultipart("alternative")
      msg["Subject"] = subject
      msg["From"] = f"{self.from_name} <{SMTP_USER}>"
      msg["To"] = to_email
      msg.attach(MIMEText(body, "plain"))
      with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(SMTP_USER, to_email, msg.as_string())
      return {"provider": "smtp", "status": "sent"}
    except Exception as e:
      logger.error(f"SMTP send failed: {e}")
      return {"provider": "smtp", "status": "failed", "error": str(e)}

  async def send_email(self, to_email: str, subject: str, body: str) -> Dict:
    """Route to configured email provider"""
    if self.provider == "resend" and RESEND_API_KEY:
      return await self.send_via_resend(to_email, subject, body)
    elif self.provider == "sendgrid" and SENDGRID_API_KEY:
      return await self.send_via_sendgrid(to_email, subject, body)
    elif self.provider == "smtp" and SMTP_USER:
      return self.send_via_smtp(to_email, subject, body)
    else:
      logger.warning("No email provider configured - email not sent")
      return {"status": "not_sent", "reason": "No email provider configured"}

  async def run(self, task: str, context: Optional[Dict] = None) -> Dict[str, Any]:
    """Entry point called by Manager Agent"""
    action = context.get("action", "generate_and_send") if context else "generate_and_send"
    prospect = context.get("prospect", {}) if context else {}
    company_research = context.get("company_research", {}) if context else {}
    to_email = context.get("to_email") or prospect.get("email") if context else None

    if action == "generate":
      email = await self.generate_email(prospect, company_research)
      return {"email": email, "status": "generated"}

    elif action == "generate_sequence":
      sequence = await self.generate_sequence(prospect, company_research)
      return {"sequence": sequence, "status": "generated"}

    elif action == "generate_and_send" and to_email:
      email = await self.generate_email(prospect, company_research)
      result = await self.send_email(to_email, email["subject"], email["body"])
      return {"email": email, "send_result": result, "status": "completed"}

    elif action == "send" and to_email:
      subject = context.get("subject", "")
      body = context.get("body", "")
      result = await self.send_email(to_email, subject, body)
      return {"send_result": result, "status": "completed"}

    return {"status": "error", "reason": "Missing required context (action, prospect, or to_email)"}
