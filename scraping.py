"""Coleta de editais nas três fontes (tudo em um módulo — sem subpastas)."""

from __future__ import annotations

import logging
from urllib.parse import urljoin

from http_util import get_soup
from models import Edital
from urlnorm import normalize_url

logger = logging.getLogger(__name__)

ACHE_BASE = "https://www.acheconcursos.com.br"
ACHE_PALAVRAS = ("edital", "concurso", "processo seletivo")
ACHE_IGNORAR = (
    "concursos abertos",
    "concursos previstos",
    "busca concursos",
    "seu concurso",
    "cadastre-se",
    "login",
)

PCI_BASE = "https://www.pciconcursos.com.br"
PCI_SKIP = ("/apostilas/", "/pedido/", "compra?", "/login", "google", "facebook")

FOLHA_BASE = "https://www.folhadirigida.com.br"
FOLHA_PALAVRAS = (
    "concurso",
    "edital",
    "processo seletivo",
    "processo sele",
    "vagas",
    "seleção simplificada",
    "cadastro reserva",
)


def fetch_ache() -> list[Edital]:
    soup = get_soup(ACHE_BASE)
    editais: list[Edital] = []
    seen: set[str] = set()

    for link in soup.find_all("a", href=True):
        texto = link.get_text(strip=True)
        href = link.get("href", "").strip()
        if not texto or not href:
            continue
        tl = texto.lower()
        if any(i in tl for i in ACHE_IGNORAR):
            continue
        if not any(p in tl for p in ACHE_PALAVRAS):
            continue
        if href.startswith("/"):
            href = ACHE_BASE + href
        if not href.startswith("http"):
            continue
        key = normalize_url(href)
        if key in seen:
            continue
        seen.add(key)
        editais.append(Edital(titulo=texto, url=key, fonte="acheconcursos"))

    return editais


def fetch_pci() -> list[Edital]:
    soup = get_soup(PCI_BASE)
    editais: list[Edital] = []
    seen: set[str] = set()

    for a in soup.find_all("a", href=True):
        href = a.get("href", "").strip()
        if "/noticias/" not in href:
            continue
        if any(s in href.lower() for s in PCI_SKIP):
            continue
        titulo = a.get_text(" ", strip=True)
        if len(titulo) < 12:
            continue
        full = href if href.startswith("http") else urljoin(PCI_BASE, href)
        key = normalize_url(full)
        if key in seen:
            continue
        seen.add(key)
        editais.append(Edital(titulo=titulo, url=key, fonte="pciconcursos"))

    return editais


def fetch_folha() -> list[Edital]:
    soup = get_soup(FOLHA_BASE)
    editais: list[Edital] = []
    seen: set[str] = set()

    for a in soup.find_all("a", href=True):
        href = a.get("href", "").strip()
        if "/n/" not in href:
            continue
        titulo = a.get_text(" ", strip=True)
        if len(titulo) < 16:
            continue
        tl = titulo.lower()
        if not any(p in tl for p in FOLHA_PALAVRAS):
            continue
        full = href if href.startswith("http") else urljoin(FOLHA_BASE, href)
        if "folhadirigida.com.br" not in normalize_url(full):
            continue
        key = normalize_url(full)
        if key in seen:
            continue
        seen.add(key)
        editais.append(Edital(titulo=titulo, url=key, fonte="folhadirigida"))

    return editais


def collect_all() -> list[Edital]:
    merged: dict[str, Edital] = {}
    for fetch in (fetch_ache, fetch_pci):
        try:
            items = fetch()
        except Exception:
            logger.exception("Falha no scraper %s", fetch.__name__)
            continue
        for edital in items:
            key = normalize_url(edital.url)
            edital.url = key
            merged[key] = edital
    return list(merged.values())
