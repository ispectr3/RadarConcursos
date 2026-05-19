"""Formatação das mensagens Telegram e e-mail."""

from __future__ import annotations

import html
import re

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

    return (
        "🚨 <b>NOVO EDITAL PUBLICADO</b>\n\n"

        f"🏛 <b>{esc(edital.organizacao)}</b>\n"
        f"💼 {esc(edital.cargo)}\n"
        f"📍 {esc(edital.estado)}\n\n"

        f"{destaque}"

        f"💰 <b>{salario}</b>\n\n"

        "🗓 <b>CRONOGRAMA</b>\n"
        f"• Inscrições: {esc(edital.inscricoes)}\n"
        f"• Isenção: {esc(edital.isencao)}\n"
        f"• Prova: {esc(edital.data_prova)}\n\n"

        "📌 <b>RESUMO</b>\n"
        f"{esc(edital.resumo)}\n\n"

        f"🔗 <a href='{edital.url}'>Acessar edital</a>"
    )


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