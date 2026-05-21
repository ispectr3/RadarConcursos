"""Coleta de editais nas três fontes (tudo em um módulo — sem subpastas)."""

from __future__ import annotations

import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from urllib.parse import urljoin

from http_util import get_soup
from models import Edital
from urlnorm import normalize_url

logger = logging.getLogger(__name__)

ACHE_BASE = "https://www.acheconcursos.com.br"
ACHE_ATUALIZADOS = "https://www.acheconcursos.com.br/concursos-atualizados-recentemente"

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
    soup = get_soup(ACHE_ATUALIZADOS)
    editais: list[Edital] = []
    seen: set[str] = set()

    # Procurar a tabela de concursos atualizados
    tbl = soup.find("table", class_="tbl-conc")
    if not tbl:
        logger.warning("Tabela .tbl-conc não encontrada em acheconcursos")
        return editais

    for row in tbl.find_all("tr"):
        cols = row.find_all("td", class_="tbl-data")
        if not cols or len(cols) < 4:
            continue
            
        link_tag = cols[0].find("a")
        if not link_tag:
            continue
            
        titulo_tag = link_tag.find("span", class_="titulo")
        titulo = titulo_tag.get_text(strip=True) if titulo_tag else link_tag.get_text(strip=True)
        
        href = link_tag.get("href", "").strip()
        if href.startswith("/"):
            href = ACHE_BASE + href
        if not href.startswith("http"):
            continue
            
        key = normalize_url(href)
        if key in seen:
            continue
        seen.add(key)
        
        vagas_tag = cols[0].find("span", class_="vagas")
        vagas = vagas_tag.get_text(strip=True) if vagas_tag else ""
        
        data_tag = cols[1].find("span", class_="atualizacao_data_hora")
        data_atualizacao = data_tag.get_text(strip=True) if data_tag else ""
        
        # Filtro: somente editais atualizados hoje
        hoje_str = datetime.now(ZoneInfo('America/Sao_Paulo')).strftime("%d/%m/%Y")
        if not data_atualizacao.startswith(hoje_str):
            continue
        
        salario_tag = cols[3].find("span", class_="sal_max")
        salario = salario_tag.get_text(strip=True) if salario_tag else ""
        
        num_vagas_tag = cols[2].find("span", class_="numero_vagas")
        num_vagas = num_vagas_tag.get_text(strip=True) if num_vagas_tag else ""
        
        if num_vagas and vagas:
            vagas_full = f"{num_vagas} vagas ({vagas})"
        else:
            vagas_full = vagas or num_vagas
            
        editais.append(Edital(
            titulo=titulo, 
            url=key, 
            fonte="acheconcursos",
            vagas=vagas_full,
            data_atualizacao=data_atualizacao,
            salario=salario
        ))

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
