"""Formatação das mensagens Telegram e e-mail."""

from __future__ import annotations

import html
import re
from datetime import datetime
from zoneinfo import ZoneInfo

from models import Edital


def esc(valor: object) -> str:

    if valor is None:
        return "Não informado"

    texto = str(valor).strip()

    if not texto:
        return "Não informado"

    return html.escape(texto)


def format_telegram_message(edital: Edital) -> str:
    salario_raw = edital.salario or "Não informado"
    destaque = ""

    try:
        nums = re.findall(r"\d+", salario_raw.replace(".", ""))
        if nums:
            valor = int(nums[0])
            if valor >= 15000:
                destaque = "🔥 <b>REMUNERAÇÃO HISTÓRICA</b>\n\n"
            elif valor >= 8000:
                destaque = "💰 <b>ALTA REMUNERAÇÃO</b>\n\n"
            elif valor >= 4000:
                destaque = "💵 <b>BOA REMUNERAÇÃO</b>\n\n"
    except Exception:
        pass

    org = edital.organizacao or edital.titulo
    cargos = edital.cargo or "Não informado"
    vagas = edital.vagas or "Não informado"
    estado = edital.estado or "Não informado"
    salario = salario_raw

    inscricoes = edital.inscricoes or "Não informado"
    isencao = edital.isencao or "Não informado"
    data_prova = edital.data_prova or "Não informado"

    resumo = edital.resumo or ""

    saudacao = get_saudacao()

    msg = (
        f"{saudacao}\n\n"
        f"{destaque}"
        f"🎯 <b>RADAR CONCURSOS</b>\n\n"
        f"🏛️ <b>Órgão:</b> {esc(org)}\n"
        f"📍 <b>Estado:</b> {esc(estado)}\n"
        f"💼 <b>Cargo:</b> {esc(cargos)}\n"
        f"💰 <b>Salário:</b> {esc(salario)}\n"
        f"👥 <b>Vagas:</b> {esc(vagas)}\n\n"
        f"📅 <b>Cronograma:</b>\n"
        f"• Inscrições: {esc(inscricoes)}\n"
        f"• Isenção: {esc(isencao)}\n"
        f"• Prova: {esc(data_prova)}\n"
    )

    if resumo.strip():
        msg += f"\n📝 <b>Resumo:</b>\n<i>{esc(resumo)}</i>\n"

    msg += f"\n🔗 <a href='{edital.url}'>Acessar Notícia / Edital</a>"
    return msg

def get_saudacao() -> str:
    hora = datetime.now(ZoneInfo('America/Sao_Paulo')).hour
    if hora < 12:
        return "Bom dia ☀️"
    elif hora < 18:
        return "Boa tarde ☕"
    else:
        return "Boa noite 🌙"


def truncate_telegram(
    text: str,
    max_len: int = 3900
) -> str:

    if len(text) <= max_len:
        return text

    return text[:max_len]


def email_subject_for(edital: Edital) -> str:

    org = edital.organizacao or edital.titulo

    return f"Novo edital - {org}"


def format_email_bodies(
    edital: Edital
) -> tuple[str, str]:

    html_body = format_telegram_message(edital)

    plain = re.sub(
        r"<[^>]+>",
        "",
        html_body
    )

    return plain, html_body