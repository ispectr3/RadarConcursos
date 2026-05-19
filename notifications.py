"""Telegram e e-mail — um arquivo só."""

from __future__ import annotations

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from telegram import Bot

from config import settings
from formatter import email_subject_for, format_email_bodies, truncate_telegram
from models import Edital
from storage import list_active_subscriber_emails

logger = logging.getLogger(__name__)


def _all_recipient_emails() -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for addr in list_active_subscriber_emails():
        a = addr.strip().lower()
        if a and a not in seen:
            seen.add(a)
            out.append(addr.strip())
    if settings.email_to:
        a = settings.email_to.strip().lower()
        if a and a not in seen:
            out.append(settings.email_to.strip())
    return out


async def send_telegram_html(text: str) -> None:
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        logger.warning("Telegram desativado: defina TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID.")
        return
    bot = Bot(token=settings.telegram_bot_token)
    payload = truncate_telegram(text)
    await bot.send_message(
        chat_id=settings.telegram_chat_id,
        text=payload,
        parse_mode="HTML",
        disable_web_page_preview=False,
    )


def send_edital_email(edital: Edital) -> bool:
    """Envia para assinantes no SQLite + EMAIL_TO. True se SMTP desligado ou todos receberam."""
    recipients = _all_recipient_emails()
    needed = (
        settings.smtp_host,
        settings.email_from,
        settings.smtp_user,
        settings.smtp_password,
    )
    if not all(needed):
        logger.debug(
            "E-mail desativado (preencha SMTP_HOST, EMAIL_FROM, SMTP_USER, SMTP_PASSWORD)."
        )
        return True
    if not recipients:
        logger.debug("Nenhum destinatário: cadastre e-mails com python emails_cli.py add ...")
        return True

    subject = email_subject_for(edital)
    plain, html_body = format_email_bodies(edital)

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=45) as smtp:
            smtp.starttls()
            smtp.login(settings.smtp_user, settings.smtp_password)
            for to_addr in recipients:
                msg = MIMEMultipart("alternative")
                msg["Subject"] = subject
                msg["From"] = settings.email_from
                msg["To"] = to_addr
                msg.attach(MIMEText(plain, "plain", "utf-8"))
                msg.attach(MIMEText(html_body, "html", "utf-8"))
                smtp.sendmail(settings.email_from, [to_addr], msg.as_string())
    except Exception:
        logger.exception("Falha ao enviar e-mail")
        return False
    return True
