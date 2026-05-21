"""Orquestra scrapers, enriquecimento, duplicação e notificações (Telegram + e-mail)."""

from __future__ import annotations

import asyncio
import logging
import sys
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore[import-untyped]
from apscheduler.triggers.cron import CronTrigger  # type: ignore[import-untyped]
from apscheduler.triggers.interval import IntervalTrigger  # type: ignore[import-untyped]

from config import settings
from enrich import enrich_edital
from formatter import format_telegram_message
from notifications import send_edital_email, send_telegram_html
from scraping import collect_all
from storage import (
    init_db,
    is_url_first_seen_today,
    mark_notified,
    migrate_json_if_exists,
    touch_url_discoveries,
    was_notified,
)

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("monitor")


def _scheduler_tz() -> ZoneInfo:
    try:
        return ZoneInfo(settings.scheduler_timezone)
    except Exception:
        logger.warning(
            "SCHEDULER_TIMEZONE inválido (%s); usando America/Sao_Paulo.",
            settings.scheduler_timezone,
        )
        return ZoneInfo("America/Sao_Paulo")


async def run_cycle() -> None:
    tz = _scheduler_tz()
    items = await asyncio.to_thread(collect_all)
    await asyncio.to_thread(touch_url_discoveries, [e.url for e in items])
    logger.info("Coletados %s itens (dedup entre fontes).", len(items))

    sent = 0

    for edital in items:
        if was_notified(edital.url):
            continue

        if settings.only_discovered_today and not is_url_first_seen_today(
            edital.url, tz
        ):
            logger.debug("Ignorado (não descoberto hoje): %s", edital.url[:80])
            continue

        logger.info("Novo item [%s]: %s", edital.fonte, edital.titulo[:100])

        if settings.fetch_full_article:
            edital = await asyncio.to_thread(enrich_edital, edital)

        body = format_telegram_message(edital)
        telegram_ok = True

        if settings.telegram_bot_token and settings.telegram_chat_id:
            try:
                await send_telegram_html(body)
            except Exception:
                logger.exception("Falha ao enviar Telegram")
                telegram_ok = False
        elif settings.telegram_bot_token or settings.telegram_chat_id:
            logger.warning("Telegram parcialmente configurado; mensagem não enviada.")
            telegram_ok = False

        mail_ok = await asyncio.to_thread(send_edital_email, edital)

        if telegram_ok and mail_ok:
            mark_notified(edital)
            sent += 1
            logger.info("Notificado e registrado: %s", edital.url)
        else:
            logger.warning(
                "Item não registrado para deduplicação (falha em canal ativo): %s",
                edital.url,
            )


async def main() -> None:
    init_db()
    migrate_json_if_exists()
    tz = _scheduler_tz()
    scheduler = AsyncIOScheduler(timezone=tz)

    if settings.schedule_hours:
        hour_expr = ",".join(str(h) for h in settings.schedule_hours)
        trigger = CronTrigger(hour=hour_expr, minute=0, timezone=tz)
        scheduler.add_job(  # type: ignore[no-untyped-call]
            run_cycle,
            trigger,
            id="concursos_cron",
            max_instances=1,
            coalesce=True,
            misfire_grace_time=300,
        )
        logger.info(
            "Agendado: %s horário %s (ONLY_DISCOVERED_TODAY=%s).",
            settings.schedule_hours,
            settings.scheduler_timezone,
            settings.only_discovered_today,
        )
    else:
        scheduler.add_job(  # type: ignore[no-untyped-call]
            run_cycle,
            IntervalTrigger(minutes=settings.interval_minutes, timezone=tz),
            id="concursos_interval",
            max_instances=1,
            coalesce=True,
            misfire_grace_time=120,
        )
        logger.info(
            "Agendado: a cada %s min (use SCHEDULE_HOURS=8,15,22 para horários fixos).",
            settings.interval_minutes,
        )

    scheduler.start()
    logger.info(
        "Monitor no ar — FETCH_FULL_ARTICLE=%s. RUN_ON_START=%s. Ctrl+C para parar.",
        settings.fetch_full_article,
        settings.run_on_start,
    )

    if settings.run_on_start:
        await run_cycle()

    stop = asyncio.Event()
    await stop.wait()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Encerrado pelo usuário.")