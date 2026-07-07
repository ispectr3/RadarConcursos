from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
from collections import Counter
from datetime import datetime, date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("static_site")

DB_PATH = Path(__file__).resolve().parent / "data" / "monitor.db"
TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
OUTPUT_DIR = Path(__file__).resolve().parent / "_site"


def url_id(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:12]


def get_stats(cursor) -> dict:
    cursor.execute("SELECT COUNT(*) FROM editais_notificados")
    total = cursor.fetchone()[0]

    hoje = date.today().isoformat()
    cursor.execute(
        "SELECT COUNT(*) FROM editais_notificados WHERE date(created_at) = ?", (hoje,)
    )
    total_hoje = cursor.fetchone()[0]

    from datetime import timedelta
    semana = (date.today() - timedelta(days=7)).isoformat()
    cursor.execute(
        "SELECT COUNT(*) FROM editais_notificados WHERE date(created_at) >= ?", (semana,)
    )
    total_semana = cursor.fetchone()[0]

    cursor.execute(
        "SELECT fonte, COUNT(*) FROM editais_notificados GROUP BY fonte ORDER BY COUNT(*) DESC"
    )
    por_fonte = cursor.fetchall()

    estados = Counter()
    cursor.execute("SELECT payload_json FROM editais_notificados")
    for row in cursor.fetchall():
        try:
            data = json.loads(row[0])
            e = data.get("estado")
            if e:
                estados[e.strip().upper()] += 1
        except (json.JSONDecodeError, TypeError):
            pass

    return {
        "total": total,
        "hoje": total_hoje,
        "esta_semana": total_semana,
        "por_fonte": por_fonte,
        "por_estado": sorted(estados.items(), key=lambda x: -x[1]),
        "fontes": len(por_fonte),
        "estados": len(estados),
    }


def get_all_editais(cursor) -> list[dict]:
    cursor.execute(
        "SELECT rowid, url, fonte, titulo, payload_json, created_at "
        "FROM editais_notificados ORDER BY created_at DESC"
    )
    rows = []
    for row in cursor.fetchall():
        try:
            payload = json.loads(row[4])
        except (json.JSONDecodeError, TypeError):
            payload = {}
        rows.append({
            "rowid": row[0],
            "url": row[1],
            "url_id": url_id(row[1]),
            "detail_url": f"/RadarConcursos/edital/{url_id(row[1])}.html",
            "fonte": row[2],
            "titulo": row[3],
            "created_at": row[5],
            **payload,
        })
    return rows


def render() -> None:
    if not DB_PATH.exists():
        logger.warning("Banco de dados não encontrado em %s", DB_PATH)
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))

    stats = get_stats(cursor)
    editais = get_all_editais(cursor)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "editais").mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "edital").mkdir(parents=True, exist_ok=True)

    fonts_disponiveis = sorted(set(e["fonte"] for e in editais))
    estados_disponiveis = sorted(
        set(e.get("estado", "").strip().upper() for e in editais if e.get("estado"))
    )

    SITE_BASE = "/RadarConcursos"

    # Index
    index_tpl = env.get_template("dashboard/index.html")
    index_html = index_tpl.render(
        stats=stats,
        recentes=editais[:10],
        request=None,
        current_path="/",
        SITE_BASE=SITE_BASE,
    )
    (OUTPUT_DIR / "index.html").write_text(index_html)
    logger.info("Gerado index.html")

    # List (paginated)
    list_tpl = env.get_template("dashboard/list.html")
    page_size = 25
    total_pages = max(1, (len(editais) + page_size - 1) // page_size)
    for page in range(1, total_pages + 1):
        start = (page - 1) * page_size
        end = start + page_size
        page_editais = editais[start:end]
        list_html = list_tpl.render(
            editais=page_editais,
            pagina=page,
            total_paginas=total_pages,
            fonte="",
            estado="",
            q="",
            fontes=fonts_disponiveis,
            estados=estados_disponiveis,
            static_mode=True,
            pagina_url_prefix=f"{SITE_BASE}/editais/page-",
            pagina_url_suffix=".html",
            request=None,
            current_path="/editais",
            SITE_BASE=SITE_BASE,
        )
        (OUTPUT_DIR / "editais" / f"page-{page}.html").write_text(list_html)
    logger.info("Geradas %d páginas de listagem", total_pages)

    # Detail
    detail_tpl = env.get_template("dashboard/detail.html")
    for edital in editais:
        edital["SITE_BASE"] = SITE_BASE
        detail_html = detail_tpl.render(
            edital=edital,
            request=None,
            current_path="/edital",
            SITE_BASE=SITE_BASE,
        )
        (OUTPUT_DIR / "edital" / f"{edital['url_id']}.html").write_text(detail_html)
    logger.info("Gerados %d detalhes", len(editais))

    conn.close()
    logger.info("Site estático gerado em %s", OUTPUT_DIR)


if __name__ == "__main__":
    render()
