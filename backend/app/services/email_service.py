import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any, Dict, Optional

import aiosmtplib
from jinja2 import Environment, FileSystemLoader, select_autoescape

from backend.app.core.config import settings

logger = logging.getLogger("sec_crag.email_service")

# Path to email template directory
TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates" / "emails"


class EmailService:
    """Asynchronous SMTP email delivery service with developmental console fallback."""

    def __init__(self, template_dir: Optional[Path] = None) -> None:
        self.template_dir = template_dir or TEMPLATES_DIR
        self._jinja_env: Optional[Environment] = None

    @property
    def jinja_env(self) -> Environment:
        """Lazy-loaded Jinja2 template environment."""
        if self._jinja_env is None:
            if not self.template_dir.exists():
                self.template_dir.mkdir(parents=True, exist_ok=True)
            self._jinja_env = Environment(
                loader=FileSystemLoader(str(self.template_dir)),
                autoescape=select_autoescape(["html", "xml"]),
            )
        return self._jinja_env

    def render_template(self, template_name: str, context: Dict[str, Any]) -> str:
        """Render a Jinja2 template by filename with provided context variables."""
        template = self.jinja_env.get_template(template_name)
        return template.render(**context)

    async def send_magic_link_email(self, email: str, token: str) -> bool:
        """Compose and dispatch a passwordless magic link verification email.

        In dev mode (SMTP_DEV_MODE=True), logs the link and formatted dispatch to stdout.
        In live mode, negotiates an async SMTP connection and delivers via aiosmtplib.
        """
        verify_url = f"{settings.FRONTEND_URL}/auth/verify?token={token}"
        backup_code = token[:8].upper()

        context = {
            "email": email,
            "verify_url": verify_url,
            "backup_code": backup_code,
            "token": token,
            "expire_minutes": settings.MAGIC_LINK_EXPIRE_MINUTES,
            "project_name": settings.PROJECT_NAME,
        }

        # Render plain-text and brutalist HTML templates
        text_content = self.render_template("magic_link.txt", context)
        html_content = self.render_template("magic_link.html", context)

        subject = f"[{settings.PROJECT_NAME}] Analyst Access Verification"

        # 1. Developmental Console Fallback Mode
        if settings.SMTP_DEV_MODE:
            logger.info("SMTP_DEV_MODE is ACTIVE. Bypassing live mail server dispatch.")
            print("\n" + "=" * 70)
            print("SEC CRAG TERMINAL // TRANSACTIONAL EMAIL DISPATCH (DEV MODE)")
            print("=" * 70)
            print(f"TO:      {email}")
            print(f"FROM:    {settings.SMTP_FROM_EMAIL}")
            print(f"SUBJECT: {subject}")
            print("-" * 70)
            print(text_content.strip())
            print("-" * 70)
            print(f"[DIRECT VERIFY URL] -> {verify_url}")
            print("=" * 70 + "\n")
            return True

        # 2. Live SMTP Dispatch
        if not settings.SMTP_HOST or not settings.SMTP_USERNAME:
            logger.error(
                "SMTP_DEV_MODE is FALSE but SMTP_HOST or SMTP_USERNAME is not configured."
            )
            return False

        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = settings.SMTP_FROM_EMAIL
        message["To"] = email

        part_text = MIMEText(text_content, "plain", "utf-8")
        part_html = MIMEText(html_content, "html", "utf-8")
        message.attach(part_text)
        message.attach(part_html)

        try:
            logger.info(f"Connecting to SMTP host {settings.SMTP_HOST}:{settings.SMTP_PORT}...")
            await aiosmtplib.send(
                message,
                hostname=settings.SMTP_HOST,
                port=settings.SMTP_PORT,
                username=settings.SMTP_USERNAME or None,
                password=settings.SMTP_PASSWORD or None,
                start_tls=settings.SMTP_USE_TLS,
                timeout=15.0,
            )
            logger.info(f"Successfully dispatched verification email to {email}")
            return True
        except Exception as exc:
            logger.error(f"Failed to deliver verification email to {email}: {exc}", exc_info=True)
            return False


email_service = EmailService()
