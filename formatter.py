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

    salario = esc(edital.salario)

    destaque = ""

    try:

        nums = re.findall(
            r"\d+",
            salario.replace(".", "")
        )

        if nums:

            valor = int(nums[0])

            if valor >= 10000:

                destaque = "🔥 <b>ALTA REMUNERAÇÃO</b>\n\n"

            elif valor >= 5000:

                destaque = "💰 <b>BOA REMUNERAÇÃO</b>\n\n"

    except Exception:
        pass

    # Usamos o título como organização se não tiver
    org = edital.organizacao or edital.titulo
    
    saudacao = get_saudacao()
    
    return (
        f"{saudacao}\n\n"
        "🇷 <b>Radar Concursos</b>\n\n"

        f"📌 {esc(org)}\n"
        f"💰 {salario} · {esc(edital.vagas)}\n"
        f"🔗 <a href='{edital.url}'>Acessar Edital</a>"
    )

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