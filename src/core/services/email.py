"""Email service abstraction layer for email providers."""

import logging
from abc import ABC, abstractmethod
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List, Optional

import aioboto3
import aiosmtplib
from botocore.exceptions import ClientError

from src.core.infrastructure.config import settings

logger = logging.getLogger(__name__)

# (filename, raw_bytes, mimetype)
Attachment = tuple[str, bytes, str]


class EmailProvider(ABC):
    """Abstract base class for email providers."""

    @abstractmethod
    async def send_email(
        self,
        to: str | List[str],
        subject: str,
        body: str,
        html_body: Optional[str] = None,
        attachments: Optional[List[Attachment]] = None,
        from_email: Optional[str] = None,
    ) -> bool:
        pass


class SESEmailProvider(EmailProvider):
    """AWS SES email provider implementation."""

    def __init__(
        self,
        region: str,
        from_email: str,
        access_key_id: Optional[str] = None,
        secret_access_key: Optional[str] = None,
    ):
        self.region = region
        self.from_email = from_email
        self.access_key_id = access_key_id
        self.secret_access_key = secret_access_key
        self.session = aioboto3.Session()

    async def send_email(
        self,
        to: str | List[str],
        subject: str,
        body: str,
        html_body: Optional[str] = None,
        attachments: Optional[List[Attachment]] = None,
        from_email: Optional[str] = None,
    ) -> bool:
        recipients = [to] if isinstance(to, str) else to
        sender = from_email or self.from_email

        if html_body or attachments:
            return await self._send_raw(
                recipients, sender, subject, body, html_body, attachments or []
            )

        async with self.session.client(  # type: ignore[attr-defined]  # aioboto3 session.client() is untyped; stubs incomplete
            "ses",
            region_name=self.region,
            aws_access_key_id=self.access_key_id,
            aws_secret_access_key=self.secret_access_key,
        ) as ses:
            try:
                await ses.send_email(
                    Source=sender,
                    Destination={"ToAddresses": recipients},
                    Message={
                        "Subject": {"Data": subject, "Charset": "UTF-8"},
                        "Body": {"Text": {"Data": body, "Charset": "UTF-8"}},
                    },
                )
                return True
            except ClientError as e:
                logger.error(f"SES error sending email: {e}")
                return False

    async def _send_raw(
        self,
        recipients: List[str],
        sender: str,
        subject: str,
        body: str,
        html_body: Optional[str],
        attachments: List[Attachment],
    ) -> bool:
        msg = _build_mime_message(
            sender, recipients, subject, body, html_body, attachments
        )
        async with self.session.client(  # type: ignore[attr-defined]  # aioboto3 session.client() is untyped; stubs incomplete
            "ses",
            region_name=self.region,
            aws_access_key_id=self.access_key_id,
            aws_secret_access_key=self.secret_access_key,
        ) as ses:
            try:
                await ses.send_raw_email(
                    Source=sender,
                    Destinations=recipients,
                    RawMessage={"Data": msg.as_bytes()},
                )
                return True
            except ClientError as e:
                logger.error(f"SES raw email error: {e}")
                return False


class SMTPEmailProvider(EmailProvider):
    """SMTP email provider."""

    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        smtp_user: Optional[str] = None,
        smtp_password: Optional[str] = None,
        from_email: Optional[str] = None,
        use_tls: bool = True,
    ):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_password = smtp_password
        self.from_email = from_email or smtp_user
        self.use_tls = use_tls

    async def send_email(
        self,
        to: str | List[str],
        subject: str,
        body: str,
        html_body: Optional[str] = None,
        attachments: Optional[List[Attachment]] = None,
        from_email: Optional[str] = None,
    ) -> bool:
        recipients = [to] if isinstance(to, str) else to
        sender = from_email or self.from_email

        if not sender:
            raise ValueError("No sender email address configured")

        msg = _build_mime_message(
            sender, recipients, subject, body, html_body, attachments or []
        )
        try:
            await aiosmtplib.send(
                msg,
                hostname=self.smtp_host,
                port=self.smtp_port,
                username=self.smtp_user or None,
                password=self.smtp_password or None,
                start_tls=self.use_tls,
                timeout=30,
            )
            return True
        except Exception as e:
            logger.error(f"SMTP error sending email: {e}")
            return False


def _build_mime_message(
    sender: str,
    recipients: List[str],
    subject: str,
    body: str,
    html_body: Optional[str],
    attachments: List[Attachment],
) -> MIMEMultipart:
    """Build a MIME message supporting plain text, HTML, and attachments."""
    outer = MIMEMultipart("mixed")
    outer["From"] = sender
    outer["To"] = ", ".join(recipients)
    outer["Subject"] = subject

    alt = MIMEMultipart("alternative")
    alt.attach(MIMEText(body, "plain", "utf-8"))
    if html_body:
        alt.attach(MIMEText(html_body, "html", "utf-8"))
    outer.attach(alt)

    for filename, data, mimetype in attachments:
        part = MIMEApplication(data, Name=filename)
        part["Content-Disposition"] = f'attachment; filename="{filename}"'
        part["Content-Type"] = f'{mimetype}; name="{filename}"'
        outer.attach(part)

    return outer


def get_email_provider() -> EmailProvider:
    """Factory function to get email provider based on configuration."""
    if settings.email_provider == "ses":
        if not settings.aws_ses_from_email:
            raise ValueError("AWS_SES_FROM_EMAIL must be set when using SES")
        return SESEmailProvider(
            region=settings.aws_region,
            from_email=settings.aws_ses_from_email,
            access_key_id=settings.aws_access_key_id,
            secret_access_key=settings.aws_secret_access_key,
        )
    else:  # smtp
        return SMTPEmailProvider(
            smtp_host=settings.smtp_host,
            smtp_port=settings.smtp_port,
            smtp_user=settings.smtp_user,
            smtp_password=settings.smtp_password,
            from_email=settings.smtp_from_email,
            use_tls=settings.smtp_use_tls,
        )
