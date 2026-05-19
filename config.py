"""Carrega configuração a partir de variáveis de ambiente (.env opcional)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parent

load_dotenv(_PROJECT_ROOT / ".env")


def _env_bool(key: str, default: bool = False) -> bool:

    v = os.getenv(key)

    if v is None:
        return default

    return v.strip().lower() in {
        "1",
        "true",
        "yes",
        "on"
    }


def _env_int(key: str, default: int) -> int:

    v = os.getenv(key)

    if v is None or not v.strip():
        return default

    try:
        return int(v)

    except ValueError:
        return default


def _parse_schedule_hours(raw: str | None) -> tuple[int, ...] | None:

    if raw is None or not raw.strip():
        return None

    parts: list[int] = []

    for piece in raw.split(","):

        piece = piece.strip()

        if not piece:
            continue

        try:

            h = int(piece)

        except ValueError:

            continue

        if 0 <= h <= 23:
            parts.append(h)

    return tuple(dict.fromkeys(parts)) if parts else None


@dataclass(frozen=True)
class Settings:

    telegram_bot_token: str | None
    telegram_chat_id: str | None

    smtp_host: str | None
    smtp_port: int
    smtp_user: str | None
    smtp_password: str | None

    email_from: str | None
    email_to: str | None

    interval_minutes: int

    schedule_hours: tuple[int, ...] | None

    scheduler_timezone: str

    only_discovered_today: bool

    run_on_start: bool

    fetch_full_article: bool

    try_pdf_extract: bool

    user_agent: str

    log_level: str

    alert_footer: str

    gemini_api_key: str | None

    groq_api_key: str | None

    telegram_delay_seconds: int

    max_notifications_per_cycle: int


def load_settings() -> Settings:

    _sched_raw = os.getenv("SCHEDULE_HOURS")

    if _sched_raw is None:

        sched = _parse_schedule_hours("8,15,22")

    else:

        sched = _parse_schedule_hours(_sched_raw)

    return Settings(

        telegram_bot_token=os.getenv(
            "TELEGRAM_BOT_TOKEN"
        ),

        telegram_chat_id=os.getenv(
            "TELEGRAM_CHAT_ID"
        ),

        smtp_host=os.getenv(
            "SMTP_HOST"
        ),

        smtp_port=_env_int(
            "SMTP_PORT",
            587
        ),

        smtp_user=os.getenv(
            "SMTP_USER"
        ),

        smtp_password=os.getenv(
            "SMTP_PASSWORD"
        ),

        email_from=os.getenv(
            "EMAIL_FROM"
        ),

        email_to=os.getenv(
            "EMAIL_TO"
        ),

        interval_minutes=max(
            1,
            _env_int(
                "SCAN_INTERVAL_MINUTES",
                10
            )
        ),

        schedule_hours=sched,

        scheduler_timezone=os.getenv(
            "SCHEDULER_TIMEZONE",
            "America/Sao_Paulo"
        ),

        only_discovered_today=_env_bool(
            "ONLY_DISCOVERED_TODAY",
            True
        ),

        run_on_start=_env_bool(
            "RUN_ON_START",
            True
        ),

        fetch_full_article=_env_bool(
            "FETCH_FULL_ARTICLE",
            True
        ),

        try_pdf_extract=_env_bool(
            "TRY_PDF_EXTRACT",
            False
        ),

        user_agent=os.getenv(
            "HTTP_USER_AGENT",
            "Mozilla/5.0 (compatible; RadarConcursos/2.0)"
        ),

        log_level=os.getenv(
            "LOG_LEVEL",
            "INFO"
        ),

        alert_footer=os.getenv(
            "ALERT_FOOTER",
            "Radar Concursos"
        ),

        gemini_api_key=os.getenv(
            "GEMINI_API_KEY"
        ),

        groq_api_key=os.getenv(
            "GROQ_API_KEY"
        ),

        telegram_delay_seconds=max(
            1,
            _env_int(
                "TELEGRAM_DELAY_SECONDS",
                5
            )
        ),

        max_notifications_per_cycle=max(
            1,
            _env_int(
                "MAX_NOTIFICATIONS_PER_CYCLE",
                5
            )
        ),
    )


settings = load_settings()