from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo

from config import settings
from formatter import format_telegram_message, get_saudacao
from models import Edital
from notifications import send_edital_email, send_telegram_html

logger = logging.getLogger(__name__)


def send_digest(editais: list[Edital]) -> None:
    if not editais:
        logger.info("Nenhum edital para o digest.")
        return

    filtrados = _filtrar_por_fonte(editais)
    if not filtrados:
        logger.info("Nenhum edital após filtro de fontes.")
        return

    hoje = datetime.now(ZoneInfo("America/Sao_Paulo")).strftime("%d/%m/%Y")
    titulo = f"📋 <b>Resumo Radar Concursos — {hoje}</b>"
    subtitulo = f"\n<i>{len(filtrados)} novo(s) edital(is) encontrado(s)</i>\n\n"

    por_fonte: dict[str, list[Edital]] = defaultdict(list)
    for e in filtrados:
        por_fonte[e.fonte].append(e)

    linhas: list[str] = [titulo, subtitulo]

    for fonte, items in sorted(por_fonte.items()):
        linhas.append(f"📡 <b>{fonte.upper()}</b> ({len(items)}):\n")
        for e in items:
            org = e.organizacao or e.titulo[:60]
            cargo = f" — {e.cargo}" if e.cargo else ""
            salario = f" | 💰 {e.salario}" if e.salario else ""
            estado = f" | 📍 {e.estado}" if e.estado else ""
            linhas.append(
                f"• <b>{org}</b>{cargo}{salario}{estado}\n"
                f"  <a href='{e.url}'>Abrir</a>"
            )
        linhas.append("")

    resumo = _formatar_resumo(editais)
    if resumo:
        linhas.append(f"📊 <b>Resumo rápido</b>\n{resumo}")

    body = "\n".join(linhas)

    if settings.telegram_bot_token and settings.telegram_chat_id:
        try:
            send_telegram_html(body)
        except Exception:
            logger.exception("Falha ao enviar digest via Telegram")

    send_edital_email(Edital(
        titulo=f"Resumo Radar Concursos - {hoje}",
        url="",
        fonte="digest",
        resumo=body,
    ))


def _filtrar_por_fonte(editais: list[Edital]) -> list[Edital]:
    if not settings.digest_sources:
        return editais
    return [e for e in editais if e.fonte in settings.digest_sources]


def _formatar_resumo(editais: list[Edital]) -> str:
    with_salary = [e for e in editais if e.salario]
    by_state: dict[str, int] = defaultdict(int)
    for e in editais:
        by_state[e.estado or "Não informado"] += 1

    parts: list[str] = []
    if with_salary:
        parts.append(f"💰 {len(with_salary)} com salário informado")
    top_state = max(by_state, key=by_state.get) if by_state else ""
    if top_state:
        parts.append(f"📍 {top_state}: {by_state[top_state]} editais")
    parts.append(f"📡 {len(set(e.fonte for e in editais))} fontes")

    return " | ".join(parts)
