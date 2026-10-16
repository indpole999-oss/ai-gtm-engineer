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
from backend.config import settings


logger = logging.getLogger(__name__)


# Email provider config
EMAIL_PROVIDER = os.getenv("EMAIL_PROVIDER", "resend")

RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", "")

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")

FROM_EMAIL = os.getenv("FROM_EMAIL", "")
FROM_NAME = os.getenv("FROM_NAME", "GTM Engineer")


# LLM config
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv(
    "OPENAI_BASE_URL",
    "https://api.openai.com/v1"
)

OPENAI_MODEL = os.getenv(
    "OPENAI_MODEL",
    "gpt-4o-mini"
)


EMAIL_SYSTEM_PROMPT = """
You are an expert B2B sales email writer.

Write concise personalized cold emails.

Rules:
- Open with a specific company insight
- Explain value clearly
- End with one low friction CTA
- Under 150 words
- Sound human
- Never use an empty prospect name
- If the prospect name is unavailable, use "there" in the greeting
- If the prospect name is unavailable, do not put an empty name in the subject
- Use the company name when a prospect name is unavailable

Return JSON:
{
    "subject": "",
    "body": ""
}
"""


class EmailAgent:
    """
    Generates personalized emails and sends them
    through Resend, SendGrid, or SMTP.
    """

    def __init__(self):
        self.provider = EMAIL_PROVIDER
        self.from_email = FROM_EMAIL
        self.from_name = FROM_NAME

    @staticmethod
    def _get_prospect_name(prospect: Dict) -> str:
        """
        Return a safe prospect name.

        If the enrichment source does not provide a name,
        return an empty string so the caller can use "there".
        """

        if not isinstance(prospect, dict):
            return ""

        name = (
            prospect.get("name")
            or prospect.get("full_name")
            or prospect.get("first_name")
            or ""
        )

        return str(name).strip()

    @staticmethod
    def _get_company_name(
        prospect: Dict,
        company_research: Dict
    ) -> str:
        """
        Return the best available company name.
        """

        company = ""

        if isinstance(prospect, dict):
            company = (
                prospect.get("company")
                or prospect.get("company_name")
                or ""
            )

        if not company and isinstance(company_research, dict):
            company = (
                company_research.get("company")
                or company_research.get("company_name")
                or ""
            )

        return str(company).strip() or "your company"

    async def generate_email(
        self,
        prospect: Dict,
        company_research: Dict
    ) -> Dict[str, str]:

        prospect_name = self._get_prospect_name(prospect)
        greeting_name = prospect_name or "there"

        company_name = self._get_company_name(
            prospect,
            company_research
        )

        # Local fallback when no OpenAI API key is configured
        if not OPENAI_API_KEY:

            if prospect_name:
                subject = f"Quick question for {prospect_name}"
            else:
                subject = f"Quick question about {company_name}"

            body = (
                f"Hi {greeting_name},\n\n"
                f"I came across {company_name} and wanted to connect.\n\n"
                "Would you be open to a quick conversation?\n\n"
                f"Best,\n{FROM_NAME}"
            )

            return {
                "subject": subject,
                "body": body
            }

        context = f"""
Prospect:
Name: {prospect_name or "Not available"}
Title: {
    prospect.get("title", "")
    if isinstance(prospect, dict)
    else ""
}

Company:
{company_name}

Research:
{company_research}

Sender:
{FROM_NAME}

Important:
If the prospect name is not available, address the prospect as "there".
Do not create an empty name in the greeting or subject.
"""

        messages = [
            {
                "role": "system",
                "content": EMAIL_SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": context
            }
        ]

        async with httpx.AsyncClient(timeout=60) as client:

            resp = await client.post(
                f"{OPENAI_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENAI_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": OPENAI_MODEL,
                    "messages": messages,
                    "temperature": 0.7,
                    "max_tokens": 500
                }
            )

            # Safely parse OpenAI response
            try:
                response_json = resp.json()

            except ValueError:

                raise RuntimeError(
                    f"OpenAI API returned non-JSON response "
                    f"(HTTP {resp.status_code}): {resp.text}"
                )

            # Handle HTTP errors explicitly
            if not resp.is_success:

                error_detail = response_json.get(
                    "error",
                    {}
                ).get(
                    "message",
                    resp.text
                )

                raise RuntimeError(
                    f"OpenAI API error "
                    f"(HTTP {resp.status_code}): "
                    f"{error_detail}"
                )

            # Validate expected OpenAI response format
            if (
                "choices" not in response_json
                or not response_json["choices"]
            ):

                raise RuntimeError(
                    "Unexpected OpenAI response format: "
                    "missing 'choices' field."
                )

            if (
                "message" not in response_json["choices"][0]
                or "content"
                not in response_json["choices"][0]["message"]
            ):

                raise RuntimeError(
                    "Unexpected OpenAI response format: "
                    "missing message content."
                )

            content = response_json["choices"][0]["message"]["content"]

        try:

            clean = content.strip()

            if clean.startswith("```"):

                clean = (
                    clean.split("\n", 1)[-1]
                    .rsplit("```", 1)[0]
                    .strip()
                )

            generated = json.loads(clean)

            subject = str(
                generated.get("subject", "")
            ).strip()

            body = str(
                generated.get("body", "")
            ).strip()

            # Protect against empty subject
            if not subject:

                if prospect_name:
                    subject = f"Quick question for {prospect_name}"
                else:
                    subject = f"Quick question about {company_name}"

            # Protect against empty body
            if not body:

                body = (
                    f"Hi {greeting_name},\n\n"
                    f"I came across {company_name} and wanted to connect.\n\n"
                    "Would you be open to a quick conversation?\n\n"
                    f"Best,\n{FROM_NAME}"
                )

            return {
                "subject": subject,
                "body": body
            }

        except Exception:

            if prospect_name:
                fallback_subject = (
                    f"Quick question for {prospect_name}"
                )
            else:
                fallback_subject = (
                    f"Quick question about {company_name}"
                )

            return {
                "subject": fallback_subject,
                "body": content
            }

    async def generate_sequence(
        self,
        prospect: Dict,
        company_research: Dict,
        num_emails: int = 3
    ) -> List[Dict]:

        sequence = []

        prospect_name = self._get_prospect_name(prospect)
        greeting_name = prospect_name or "there"

        for step in range(1, num_emails + 1):

            if step == 1:

                email = await self.generate_email(
                    prospect,
                    company_research
                )

            else:

                email = {
                    "subject": (
                        f"Re: {sequence[0].get('subject')}"
                    ),
                    "body": (
                        f"Hi {greeting_name},\n\n"
                        "Following up on my previous email.\n\n"
                        "Would love to connect.\n\n"
                        f"Best,\n{FROM_NAME}"
                    )
                }

            sequence.append(
                {
                    "step": step,
                    "delay_days": (step - 1) * 3,
                    **email
                }
            )

        return sequence

    async def send_via_resend(
        self,
        to_email: str,
        subject: str,
        body: str
    ) -> Dict:

        async with httpx.AsyncClient(timeout=30) as client:

            resp = await client.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {RESEND_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "from": f"{self.from_name} <{self.from_email}>",
                    "to": [to_email],
                    "subject": subject,
                    "text": body
                }
            )

            data = resp.json()

            return {
                "provider": "resend",
                "id": data.get("id"),
                "status": (
                    "sent"
                    if resp.status_code == 200
                    else "failed"
                )
            }

    async def send_via_sendgrid(
        self,
        to_email: str,
        subject: str,
        body: str
    ) -> Dict:

        async with httpx.AsyncClient(timeout=30) as client:

            resp = await client.post(
                "https://api.sendgrid.com/v3/mail/send",
                headers={
                    "Authorization": f"Bearer {SENDGRID_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "personalizations": [
                        {
                            "to": [
                                {
                                    "email": to_email
                                }
                            ]
                        }
                    ],
                    "from": {
                        "email": self.from_email,
                        "name": self.from_name
                    },
                    "subject": subject,
                    "content": [
                        {
                            "type": "text/plain",
                            "value": body
                        }
                    ]
                }
            )

            return {
                "provider": "sendgrid",
                "status": (
                    "sent"
                    if resp.status_code == 202
                    else "failed"
                )
            }

    def send_via_smtp(
        self,
        to_email: str,
        subject: str,
        body: str
    ) -> Dict:

        try:

            msg = MIMEMultipart("alternative")

            msg["Subject"] = subject
            msg["From"] = f"{self.from_name} <{SMTP_USER}>"
            msg["To"] = to_email

            msg.attach(
                MIMEText(
                    body,
                    "plain"
                )
            )

            with smtplib.SMTP(
                SMTP_HOST,
                SMTP_PORT
            ) as server:

                server.starttls()

                server.login(
                    SMTP_USER,
                    SMTP_PASS
                )

                server.sendmail(
                    SMTP_USER,
                    to_email,
                    msg.as_string()
                )

            return {
                "provider": "smtp",
                "status": "sent"
            }

        except Exception as e:

            logger.error(
                f"SMTP send failed: {e}"
            )

            return {
                "provider": "smtp",
                "status": "failed",
                "error": str(e)
            }

    async def send_email(
        self,
        to_email: str,
        subject: str,
        body: str
    ) -> Dict:

        if not settings.ALLOW_LEGACY_ENV_CREDENTIALS:
            logger.warning("Environment email credential fallback is disabled")
            return {
                "status": "not_sent",
                "reason": "Workspace email integration required",
            }

        if (
            self.provider == "resend"
            and RESEND_API_KEY
        ):

            return await self.send_via_resend(
                to_email,
                subject,
                body
            )

        elif (
            self.provider == "sendgrid"
            and SENDGRID_API_KEY
        ):

            return await self.send_via_sendgrid(
                to_email,
                subject,
                body
            )

        elif (
            self.provider == "smtp"
            and SMTP_USER
        ):

            return await self.send_via_smtp(
                to_email,
                subject,
                body
            )

        else:

            logger.warning(
                "No email provider configured"
            )

            return {
                "status": "not_sent",
                "reason": "No email provider configured"
            }

    async def run(
        self,
        task: str,
        context: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Entry point called by Manager Agent.

        Supports workflow flat context:
        {
            company,
            contact,
            email
        }

        Also supports direct email context:
        {
            prospect,
            to_email,
            action
        }
        """

        context = context or {}

        # Normalize email
        to_email = (
            context.get("to_email")
            or context.get("email")
        )

        # Normalize prospect
        prospect = context.get("prospect")

        if not prospect:

            prospect = {
                "name": context.get(
                    "contact",
                    "Prospect"
                ),
                "email": to_email,
                "company": context.get(
                    "company",
                    context.get("company_name", "")
                )
            }

        # Normalize action
        action = context.get(
            "action",
            "generate_and_send"
        )

        company_research = context.get(
            "company_research",
            {}
        )

        # Generate only
        if action == "generate":

            email = await self.generate_email(
                prospect,
                company_research
            )

            return {
                "email": email,
                "status": "generated"
            }

        # Generate sequence
        elif action == "generate_sequence":

            sequence = await self.generate_sequence(
                prospect,
                company_research
            )

            return {
                "sequence": sequence,
                "status": "generated"
            }

        # Send / Outreach flow
        elif action in [
            "generate_and_send",
            "send",
            "outreach"
        ]:

            if not to_email:

                return {
                    "status": "error",
                    "reason": "No recipient email found"
                }

            email = await self.generate_email(
                prospect,
                company_research
            )

            subject = context.get(
                "subject",
                email.get(
                    "subject",
                    "Quick question"
                )
            )

            body = context.get(
                "body",
                email.get(
                    "body",
                    ""
                )
            )

            send_result = await self.send_email(
                to_email,
                subject,
                body
            )

            return {
                "email": {
                    "subject": subject,
                    "body": body
                },
                "send_result": send_result,
                "status": "completed"
            }

        return {
            "status": "error",
            "reason": f"Unknown action: {action}"
        }
