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
_gemini_blocked_until: float = 0.0
_groq_blocked_until: float = 0.0


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
    global _groq_blocked_until
    if not groq_client:
        logger.error("Groq API key não configurada no .env. Impossível usar o fallback.")
        return {}

    if time.time() < _groq_blocked_until:
        logger.warning("Groq está em cooldown de rate limit. Ignorando chamada.")
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
            model="llama-3.3-70b-versatile",
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content.strip()
        content = re.sub(r"```json|```", "", content)
        return json.loads(content)
    except Exception as e:
        logger.error("Erro no Groq: %s", e)
        # Se for erro de rate limit/quota, define cooldown de 5 min (300 segundos)
        err_msg = str(e).lower()
        if "exhausted" in err_msg or "limit" in err_msg or "429" in err_msg:
            logger.warning("Groq atingiu limite de cota. Definindo cooldown de 5 min.")
            _groq_blocked_until = time.time() + 300
        return {}


def resumo_ia(texto: str) -> dict:
    global _gemini_blocked_until

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

    if time.time() < _gemini_blocked_until:
        logger.info("Gemini está em cooldown de rate limit. Usando Groq diretamente.")
        _throttle()
        return resumo_ia_groq(texto)

    _throttle()
    try:
        response = model.generate_content(prompt)
        content = response.text.strip()
        content = re.sub(r"```json|```", "", content)
        return json.loads(content)

    except google.api_core.exceptions.ResourceExhausted as e:
        logger.warning("Quota do Gemini esgotada (Rate Limit). Ativando cooldown de 5 min e fallback para Groq...")
        _gemini_blocked_until = time.time() + 300
        return resumo_ia_groq(texto)

    except Exception as e:
        logger.warning("Erro no Gemini: %s. Tentando fallback para Groq...", e)
        err_msg = str(e).lower()
        if "exhausted" in err_msg or "quota" in err_msg or "429" in err_msg:
            _gemini_blocked_until = time.time() + 300
        return resumo_ia_groq(texto)


def enrich_edital(edital: Edital) -> Edital:
    html = ""
    try:
        html = fetch_text(edital.url)
    except Exception as e:
        logger.warning("Erro ao baixar página do edital %s: %s", edital.url, e)

    texto_extraido = ""
    if html:
        soup = BeautifulSoup(html, "html.parser")
        texto_extraido = limpar_texto(soup.get_text(" ", strip=True))

    if len(texto_extraido) < 200:
        logger.warning(
            "Texto extraído muito curto (%s caracteres) ou falha no download. Usando o título para IA.",
            len(texto_extraido),
        )
        texto = f"Título do edital: {edital.titulo}"
    else:
        texto = texto_extraido

    dados = resumo_ia(texto)

    edital.organizacao = dados.get("organizacao") or edital.organizacao or edital.titulo
    edital.cargo = dados.get("cargo") or edital.cargo
    edital.salario = dados.get("salario") or edital.salario
    edital.estado = dados.get("estado") or edital.estado
    edital.inscricoes = dados.get("inscricoes") or edital.inscricoes
    edital.isencao = dados.get("isencao") or edital.isencao
    edital.data_prova = dados.get("data_prova") or edital.data_prova
    edital.resumo = dados.get("resumo") or edital.resumo

    return edital