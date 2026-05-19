from __future__ import annotations

import json
import re
import time
import logging

import google.generativeai as genai
import google.api_core.exceptions
import groq
from bs4 import BeautifulSoup

from config import settings
from http_util import fetch_text
from models import Edital

logger = logging.getLogger(__name__)

genai.configure(api_key=settings.gemini_api_key)

model = genai.GenerativeModel("gemini-2.5-flash")

# Groq Client (Fallback)
try:
    groq_client = groq.Groq(api_key=settings.groq_api_key) if settings.groq_api_key else None
except Exception:
    groq_client = None

# Free tier: 5 req/min → 1 req a cada 12.5s
_MIN_INTERVAL = 12.5
_last_call: float = 0.0


def limpar_texto(texto: str) -> str:
    texto = re.sub(r"\s+", " ", texto)
    return texto.strip()


def _throttle() -> None:
    global _last_call
    elapsed = time.time() - _last_call
    if elapsed < _MIN_INTERVAL:
        wait = _MIN_INTERVAL - elapsed
        logger.debug("Throttle: aguardando %.1fs", wait)
        time.sleep(wait)
    _last_call = time.time()


def resumo_ia_groq(texto: str) -> dict:
    if not groq_client:
        logger.error("Groq API key não configurada no .env. Impossível usar o fallback.")
        return {}

    prompt = f"""
    Leia este edital.

    Responda SOMENTE JSON válido.

    {{
      "organizacao": "",
      "cargo": "",
      "salario": "",
      "estado": "",
      "inscricoes": "",
      "isencao": "",
      "data_prova": "",
      "resumo": ""
    }}

    Regras:
    - resumo curto
    - máximo 3 linhas
    - não invente informações
    - destaque salário se existir

    Edital:
    {texto[:15000]}
    """

    try:
        response = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama3-8b-8192",
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content.strip()
        content = re.sub(r"```json|```", "", content)
        return json.loads(content)
    except Exception as e:
        logger.error("Erro no Groq: %s", e)
        return {}


def resumo_ia(texto: str, max_retries: int = 5) -> dict:
    prompt = f"""
    Leia este edital.

    Responda SOMENTE JSON válido.

    {{
      "organizacao": "",
      "cargo": "",
      "salario": "",
      "estado": "",
      "inscricoes": "",
      "isencao": "",
      "data_prova": "",
      "resumo": ""
    }}

    Regras:
    - resumo curto
    - máximo 3 linhas
    - não invente informações
    - destaque salário se existir

    Edital:
    {texto[:15000]}
    """

    for attempt in range(max_retries):
        _throttle()
        try:
            response = model.generate_content(prompt)
            content = response.text.strip()
            content = re.sub(r"```json|```", "", content)
            return json.loads(content)

        except google.api_core.exceptions.ResourceExhausted as e:
            logger.warning("Quota do Gemini esgotada (Rate Limit). Acionando IA de fallback (Groq)...")
            return resumo_ia_groq(texto)

        except (json.JSONDecodeError, Exception) as e:
            logger.warning("Erro ao processar resposta da IA: %s", e)
            return {}

    return {}


def enrich_edital(edital: Edital) -> Edital:
    try:
        html = fetch_text(edital.url)
    except Exception:
        return edital

    soup = BeautifulSoup(html, "html.parser")
    texto = limpar_texto(soup.get_text(" ", strip=True))

    dados = resumo_ia(texto)

    edital.organizacao = dados.get("organizacao")
    edital.cargo = dados.get("cargo")
    edital.salario = dados.get("salario")
    edital.estado = dados.get("estado")
    edital.inscricoes = dados.get("inscricoes")
    edital.isencao = dados.get("isencao")
    edital.data_prova = dados.get("data_prova")
    edital.resumo = dados.get("resumo")

    return edital