"""Coleta de editais nas três fontes (tudo em um módulo — sem subpastas)."""

from __future__ import annotations

import logging
import re
from datetime import datetime
from zoneinfo import ZoneInfo
from urllib.parse import urljoin, urlparse

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


def is_study_or_article(title: str, slug: str) -> bool:
    t_lower = title.lower()
    s_lower = slug.lower()

    study_indicators = (
        "resumo para",
        "como estudar",
        "o que cai",
        "o que e",
        "dicas de",
        "dicas para",
        "questoes de",
        "simulado de",
        "simulados",
        "aula gratis",
        "aula gratuita",
        "aulas gratuitas",
        "revisao para",
        "revisao de",
        "cronograma de estudos",
        "plano de estudos",
        "guia de estudos",
        "lei esquematizada",
        "materias cobradas",
        "assuntos mais cobrados",
        "quadro de estudos",
        "apostila gratis",
        "apostila gratuita",
        "resumos de",
        "guia completo",
        "maratona de",
    )

    for indicator in study_indicators:
        if indicator in t_lower or indicator.replace(" ", "-") in s_lower:
            return True

    if "para concursos" in t_lower:
        contest_indicators = (
            "edital",
            "vagas",
            "inscric",
            "autorizado",
            "retificad",
            "comissao",
            "banca",
            "abert",
            "salario",
            "saiu",
            "publicado",
        )
        if not any(ci in t_lower or ci in s_lower for ci in contest_indicators):
            return True

    return False


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
        p = urlparse(full)
        segments = [s for s in p.path.split("/") if s]
        slug = segments[-1] if segments else ""
        if is_study_or_article(titulo, slug):
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
        p = urlparse(full)
        segments = [s for s in p.path.split("/") if s]
        slug = segments[-1] if segments else ""
        if is_study_or_article(titulo, slug):
            continue
        seen.add(key)
        editais.append(Edital(titulo=titulo, url=key, fonte="folhadirigida"))

    return editais


GRAN_BASE = "https://blog.grancursosonline.com.br"
ESTRATEGIA_BASE = "https://www.estrategiaconcursos.com.br"


def is_generic_page(slug: str) -> bool:
    slug = slug.strip().lower()
    if slug in (
        "concursos-abertos",
        "concursos-2026",
        "concursos-em-destaque",
        "mapa-concursos",
        "lp",
        "depoimentos",
        "professores",
        "artigos",
        "como-estudar",
        "como-passar",
        "category",
        "tag",
        "page",
        "contato",
    ):
        return True
    if re.match(r"^concursos-[a-z]{2}$", slug):
        return True
    if slug.startswith("concursos-") and any(
        r in slug
        for r in (
            "sudeste",
            "nordeste",
            "centro-oeste",
            "norte",
            "sul",
            "administrativos",
            "legislativos",
            "policiais",
        )
    ):
        return True
    return False


def fetch_gran() -> list[Edital]:
    soup = get_soup(GRAN_BASE)
    editais: list[Edital] = []
    seen: set[str] = set()
    keywords = ("concurso", "edital", "vagas", "inscricoes", "inscricao", "retificacao", "aberto")
    skip_terms = ("depoimentos", "professores", "artigos", "concurseiro-iniciante", "como-passar", "category", "tag", "page", "contato")

    for a in soup.find_all("a", href=True):
        href = a.get("href", "").strip()
        titulo = a.get_text(" ", strip=True)
        if not href.startswith("http"):
            href = urljoin(GRAN_BASE, href)
        if "blog.grancursosonline.com.br" not in normalize_url(href):
            continue
        p = urlparse(href)
        segments = [s for s in p.path.split("/") if s]
        if len(segments) == 1:
            slug = segments[0].lower()
            if any(kw in slug or kw in titulo.lower() for kw in keywords):
                if not any(skip in slug for skip in skip_terms) and not is_generic_page(slug):
                    if is_study_or_article(titulo, slug):
                        continue
                    if len(titulo) < 12:
                        continue
                    key = normalize_url(href)
                    if key in seen:
                        continue
                    seen.add(key)
                    editais.append(Edital(titulo=titulo, url=key, fonte="grancursos"))
    return editais


def fetch_estrategia() -> list[Edital]:
    blog_url = urljoin(ESTRATEGIA_BASE, "/blog/")
    soup = get_soup(blog_url)
    editais: list[Edital] = []
    seen: set[str] = set()
    keywords = ("concurso", "edital", "vagas", "inscricoes", "inscricao", "retificacao", "aberto")
    skip_terms = ("depoimentos", "professores", "artigos", "como-estudar", "category", "tag", "page", "contato", "mapa-concursos", "lp")

    for a in soup.find_all("a", href=True):
        href = a.get("href", "").strip()
        titulo = a.get_text(" ", strip=True)
        if not href.startswith("http"):
            href = urljoin(blog_url, href)
        if "estrategiaconcursos.com.br/blog" not in normalize_url(href):
            continue
        p = urlparse(href)
        segments = [s for s in p.path.split("/") if s]
        if len(segments) == 2 and segments[0] == "blog":
            slug = segments[1].lower()
            if any(kw in slug or kw in titulo.lower() for kw in keywords):
                if not any(skip in slug for skip in skip_terms) and not is_generic_page(slug):
                    if is_study_or_article(titulo, slug):
                        continue
                    if len(titulo) < 12:
                        continue
                    key = normalize_url(href)
                    if key in seen:
                        continue
                    seen.add(key)
                    editais.append(Edital(titulo=titulo, url=key, fonte="estrategiaconcursos"))
    return editais


def collect_all() -> list[Edital]:
    merged: dict[str, Edital] = {}
    for fetch in (fetch_ache, fetch_pci, fetch_folha, fetch_gran, fetch_estrategia):
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
