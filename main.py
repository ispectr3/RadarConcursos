"""Orquestra scrapers, enriquecimento, duplicação e notificações (Telegram + e-mail)."""

from __future__ import annotations

import asyncio
import logging
import sys
import re
import unicodedata
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore[import-untyped]
from apscheduler.triggers.cron import CronTrigger  # type: ignore[import-untyped]
from apscheduler.triggers.interval import IntervalTrigger  # type: ignore[import-untyped]

from calendar_integration import criar_evento_edital
from config import settings
from digest import send_digest
from enrich import AIRateLimitError, enrich_edital
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


STATE_MAP = {
    "ACRE": "AC", "ALAGOAS": "AL", "AMAPA": "AP", "AMAZONAS": "AM", "BAHIA": "BA",
    "CEARA": "CE", "DISTRITO FEDERAL": "DF", "ESPIRITO SANTO": "ES", "GOIAS": "GO",
    "MARANHAO": "MA", "MATO GROSSO": "MT", "MATO GROSSO DO SUL": "MS", "MINAS GERAIS": "MG",
    "PARA": "PA", "PARAIBA": "PB", "PARANA": "PR", "PERNAMBUCO": "PE", "PIAUI": "PI",
    "RIO DE JANEIRO": "RJ", "RIO GRANDE DO NORTE": "RN", "RIO GRANDE DO SUL": "RS",
    "RONDONIA": "RO", "RORAIMA": "RR", "SANTA CATARINA": "SC", "SAO PAULO": "SP",
    "SERGIPE": "SE", "TOCANTINS": "TO"
}


def normalize_text(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", text)
        if unicodedata.category(c) != "Mn"
    ).upper()


def matches_state(edital: Edital, filter_states: list[str]) -> bool:
    if not filter_states:
        return True

    est = normalize_text(edital.estado or "")
    tit = normalize_text(edital.titulo)

    found_ufs = set()
    for term in [est, tit]:
        for uf in filter_states:
            if re.search(rf"\b{re.escape(uf)}\b", term):
                found_ufs.add(uf)
        for full_name, uf in STATE_MAP.items():
            if full_name in term:
                found_ufs.add(uf)

    for uf in filter_states:
        if uf in found_ufs:
            return True
    return False


def extract_max_salary(salary_str: str | None) -> float | None:
    if not salary_str:
        return None

    matches = re.findall(r"\d+(?:\.\d+)*(?:,\d+)?", salary_str)
    values = []
    for m in matches:
        try:
            clean = m
            if "," in clean and "." in clean:
                clean = clean.replace(".", "").replace(",", ".")
            elif "," in clean:
                parts = clean.split(",")
                if len(parts[-1]) <= 2:
                    clean = clean.replace(".", "").replace(",", ".")
                else:
                    clean = clean.replace(".", "").replace(",", "")
            elif "." in clean:
                parts = clean.split(".")
                if len(parts[-1]) == 3:
                    clean = clean.replace(".", "")
            val = float(clean)
            values.append(val)
        except ValueError:
            continue
    return max(values) if values else None


async def run_cycle() -> None:
    tz = _scheduler_tz()
    items = await asyncio.to_thread(collect_all)
    await asyncio.to_thread(touch_url_discoveries, [e.url for e in items])
    logger.info("Coletados %s itens (dedup entre fontes).", len(items))

    # Prevenção de estouro de cota da IA em cargas iniciais/novos scrapers (seeding)
    novos_itens = [e for e in items if not was_notified(e.url)]
    if len(novos_itens) > 15:
        logger.warning(
            "Detectados %s novos editais (provável carga inicial/novos scrapers). "
            "Registrando todos no banco para evitar estouro de cota de IA e silenciando este lote.",
            len(novos_itens)
        )
        for edital in novos_itens:
            mark_notified(edital)
        return

    sent = 0
    digest_items: list[Edital] = []

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
            try:
                edital = await asyncio.to_thread(enrich_edital, edital)
            except AIRateLimitError as e:
                logger.warning(
                    "Cota das IAs (Gemini e Groq) esgotada. Abortando este ciclo para tentar novamente na próxima rodada. Detalhe: %s",
                    e,
                )
                break
            except Exception as e:
                logger.exception("Erro inesperado no enriquecimento do edital: %s", e)
                continue

        if settings.filter_states and not matches_state(edital, settings.filter_states):
            logger.info("Ignorado (filtro de estado): %s", edital.titulo[:80])
            continue

        if settings.min_salary:
            val = extract_max_salary(edital.salario)
            if val is not None and val < settings.min_salary:
                logger.info(
                    "Ignorado (filtro de salário: R$ %s < R$ %s): %s",
                    val,
                    settings.min_salary,
                    edital.titulo[:80],
                )
                continue

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
            digest_items.append(edital)
            if settings.google_calendar_creds:
                await asyncio.to_thread(criar_evento_edital, edital)
            logger.info("Notificado e registrado: %s", edital.url)
        else:
            logger.warning(
                "Item não registrado para deduplicação (falha em canal ativo): %s",
                edital.url,
            )

    if sent:
        logger.info(
            "Ciclo concluído: %s notificados. Execute o dashboard com: python dashboard.py",
            sent,
        )


async def _digest_job() -> None:
    items = await asyncio.to_thread(collect_all)
    novos = [e for e in items if not was_notified(e.url)]
    if novos:
        await asyncio.to_thread(send_digest, novos)
    else:
        logger.info("Digest: nenhum edital novo.")


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

    scheduler.add_job(  # type: ignore[no-untyped-call]
        _digest_job,
        CronTrigger(hour=settings.digest_hour, minute=0, timezone=tz),
        id="digest_diario",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=600,
    )
    logger.info(
        "Digest diário agendado às %s:00.", settings.digest_hour,
    )

    scheduler.start()
    logger.info(
        "Monitor no ar — FETCH_FULL_ARTICLE=%s. RUN_ON_START=%s. Dashboard: python dashboard.py",
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