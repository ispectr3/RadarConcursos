from __future__ import annotations

import json
import re
import time
import logging

from google import genai
import google.api_core.exceptions
import groq
from openai import OpenAI
from bs4 import BeautifulSoup

from config import settings
from http_util import fetch_text
from models import Edital

logger = logging.getLogger(__name__)


class AIRateLimitError(Exception):
    pass

_gemini_client = genai.Client(api_key=settings.gemini_api_key) if settings.gemini_api_key else None

# Groq Client (Fallback)
try:
    groq_client = groq.Groq(api_key=settings.groq_api_key) if settings.groq_api_key else None
except Exception:
    groq_client = None

# Free API Key Pool (fallback final — https://github.com/alistaitsacle/free-llm-api-keys)
_free_entries: list[dict] = []

if settings.free_api_entries:
    _free_entries = list(settings.free_api_entries)
elif settings.free_api_key:
    _free_entries = [
        {"key": k.strip(), "base_url": settings.free_api_base_url, "model": settings.free_api_model}
        for k in settings.free_api_key.split(",")
        if k.strip()
    ]
_free_entry_index = 0

def _next_free_entry() -> dict | None:
    global _free_entry_index
    if not _free_entries:
        return None
    entry = _free_entries[_free_entry_index % len(_free_entries)]
    _free_entry_index = (_free_entry_index + 1) % len(_free_entries)
    return entry

# Free tier: 5 req/min → 1 req a cada 12.5s
_MIN_INTERVAL = 12.5
_last_call: float = 0.0
_gemini_blocked_until: float = 0.0
_groq_blocked_until: float = 0.0
_free_blocked_until: float = 0.0


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
        # Se for erro de rate limit/quota, define cooldown de 25 min (1500 segundos)
        err_msg = str(e).lower()
        if "exhausted" in err_msg or "limit" in err_msg or "429" in err_msg:
            logger.warning("Groq atingiu limite de cota. Definindo cooldown de 25 min.")
            _groq_blocked_until = time.time() + 1500
        return {}


def resumo_ia_free(texto: str) -> dict:
    global _free_blocked_until

    if not _free_entries:
        logger.debug("Nenhuma FREE_API_KEY / FREE_API_ENTRIES configurada; pulando fallback free.")
        return {}

    if time.time() < _free_blocked_until:
        logger.warning("Free API em cooldown. Ignorando chamada.")
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

    tentativas = len(_free_entries)
    for attempt in range(tentativas):
        entry = _next_free_entry()
        if not entry:
            continue
        try:
            client = OpenAI(api_key=entry["key"], base_url=entry.get("base_url", settings.free_api_base_url))
            response = client.chat.completions.create(
                model=entry["model"],
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content.strip()
            content = re.sub(r"```json|```", "", content)
            return json.loads(content)
        except Exception as e:
            logger.warning(
                "Free entry %d/%d (model=%s) falhou: %s",
                attempt + 1, tentativas, entry["model"], e,
            )
            continue

    _free_blocked_until = time.time() + 600
    logger.warning("Todas as %d entries da Free API falharam. Cooldown de 10 min.", tentativas)
    return {}


def resumo_ia(texto: str) -> dict:
    global _gemini_blocked_until, _groq_blocked_until

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

    def _tentar_com_fallback() -> dict | None:
        gemini_cooldown = time.time() < _gemini_blocked_until
        groq_cooldown = time.time() < _groq_blocked_until

        if not _gemini_client:
            res = resumo_ia_groq(texto)
            if res:
                return res
            res = resumo_ia_free(texto)
            if res:
                return res
            raise AIRateLimitError("Gemini não configurado, Groq e Free API falharam.")

        if gemini_cooldown:
            if not groq_cooldown:
                logger.info("Gemini em cooldown. Tentando Groq...")
                _throttle()
                res = resumo_ia_groq(texto)
                if res:
                    return res
            logger.info("Groq falhou ou também em cooldown. Tentando Free API...")
            res = resumo_ia_free(texto)
            if res:
                return res
            raise AIRateLimitError("Gemini, Groq e Free API falharam / estão em cooldown.")

        _throttle()
        try:
            response = _gemini_client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
            )
            content = response.text.strip()
            content = re.sub(r"```json|```", "", content)
            return json.loads(content)
        except google.api_core.exceptions.ResourceExhausted as e:
            logger.warning("Quota do Gemini esgotada. Ativando cooldown de 25 min e fallback...")
            _gemini_blocked_until = time.time() + 1500
        except Exception as e:
            logger.warning("Erro no Gemini: %s. Tentando fallback...", e)
            err_msg = str(e).lower()
            if "exhausted" in err_msg or "quota" in err_msg or "429" in err_msg:
                _gemini_blocked_until = time.time() + 1500

        res = resumo_ia_groq(texto)
        if res:
            return res

        res = resumo_ia_free(texto)
        if res:
            return res

        raise AIRateLimitError("Gemini, Groq e Free API falharam.")

    return _tentar_com_fallback() or {}


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