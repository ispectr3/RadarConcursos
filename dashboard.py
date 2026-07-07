from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, unquote

from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse
from jinja2 import Environment, FileSystemLoader

DB_PATH = Path(__file__).resolve().parent / "data" / "monitor.db"
app = FastAPI(title="Radar Concursos Dashboard")

_jinja_env = Environment(
    loader=FileSystemLoader(str(Path(__file__).resolve().parent / "templates")),
    auto_reload=False,
)
_jinja_env.cache = None  # type: ignore[assignment]

logger = logging.getLogger("dashboard")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")

PAGE_SIZE = 25


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _parse_edital(row: sqlite3.Row) -> dict:
    d = dict(row)
    payload = d.get("payload_json")
    if payload:
        try:
            data = json.loads(payload)
            d.update(data)
        except (json.JSONDecodeError, TypeError):
            pass
    return d


def _render(request: Request, name: str, context: dict | None = None) -> HTMLResponse:
    tpl = _jinja_env.get_template(name)
    ctx = {"request": request, "current_path": request.url.path, "SITE_BASE": "", **(context or {})}
    html = tpl.render(ctx)
    return HTMLResponse(html)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    conn = _connect()
    hoje = datetime.now(timezone.utc).isoformat()[:10]

    total = conn.execute("SELECT COUNT(*) FROM editais_notificados").fetchone()[0]
    hoje_count = conn.execute(
        "SELECT COUNT(*) FROM editais_notificados WHERE date(created_at) = ?", (hoje,)
    ).fetchone()[0]
    semana = conn.execute(
        "SELECT COUNT(*) FROM editais_notificados WHERE created_at >= datetime('now', '-7 days')"
    ).fetchone()[0]

    fontes_raw = conn.execute(
        "SELECT fonte, COUNT(*) as c FROM editais_notificados GROUP BY fonte ORDER BY c DESC"
    ).fetchall()
    por_fonte = [(r["fonte"], r["c"]) for r in fontes_raw]

    estados_count: dict[str, int] = {}
    for row in conn.execute("SELECT payload_json FROM editais_notificados WHERE payload_json IS NOT NULL"):
        try:
            data = json.loads(row[0])
            est = data.get("estado") or "Não informado"
            estados_count[est] = estados_count.get(est, 0) + 1
        except (json.JSONDecodeError, TypeError):
            pass
    por_estado = sorted(estados_count.items(), key=lambda x: -x[1])

    conn.close()

    stats = {
        "total": total,
        "hoje": hoje_count,
        "fontes": len(por_fonte),
        "estados": len(estados_count),
        "esta_semana": semana,
        "por_fonte": por_fonte,
        "por_estado": por_estado,
    }

    conn = _connect()
    recentes_raw = conn.execute(
        "SELECT * FROM editais_notificados ORDER BY created_at DESC LIMIT 10"
    ).fetchall()
    conn.close()
    recentes = [_parse_edital(r) for r in recentes_raw]

    return _render(request, "dashboard/index.html", {"stats": stats, "recentes": recentes})


@app.get("/editais", response_class=HTMLResponse)
async def list_editais(
    request: Request,
    q: str = Query(""),
    fonte: str = Query(""),
    estado: str = Query(""),
    pagina: int = Query(1, ge=1),
):
    conn = _connect()

    conditions: list[str] = []
    params: list[str] = []

    if q:
        conditions.append("(titulo LIKE ? OR payload_json LIKE ?)")
        params.extend([f"%{q}%", f"%{q}%"])
    if fonte:
        conditions.append("fonte = ?")
        params.append(fonte)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    count = conn.execute(
        f"SELECT COUNT(*) FROM editais_notificados {where}", params
    ).fetchone()[0]

    offset = (pagina - 1) * PAGE_SIZE
    rows = conn.execute(
        f"SELECT * FROM editais_notificados {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
        [*params, PAGE_SIZE, offset],
    ).fetchall()

    total_paginas = max(1, (count + PAGE_SIZE - 1) // PAGE_SIZE)

    fontes = [
        r[0]
        for r in conn.execute(
            "SELECT DISTINCT fonte FROM editais_notificados ORDER BY fonte"
        ).fetchall()
    ]
    conn.close()

    editais = [_parse_edital(r) for r in rows]

    if estado:
        editais = [e for e in editais if e.get("estado") == estado]

    conn = _connect()
    estados_all = sorted(
        set(
            r[0]
            for r in conn.execute(
                "SELECT DISTINCT payload_json FROM editais_notificados WHERE payload_json IS NOT NULL"
            ).fetchall()
        )
    )
    conn.close()
    estados_set: set[str] = set()
    for raw in estados_all:
        try:
            data = json.loads(raw)
            if data.get("estado"):
                estados_set.add(data["estado"])
        except (json.JSONDecodeError, TypeError):
            pass

    return _render(
        request, "dashboard/list.html",
        {
            "editais": editais, "q": q, "fonte": fonte, "estado": estado,
            "pagina": pagina, "total_paginas": total_paginas,
            "fontes": fontes, "estados": sorted(estados_set),
            "pagina_url_prefix": f"?pagina=",
            "pagina_url_suffix": "",
        },
    )


@app.get("/editais/{url:path}", response_class=HTMLResponse)
async def detail_edital(request: Request, url: str):
    decoded = unquote(url)
    conn = _connect()
    row = conn.execute(
        "SELECT * FROM editais_notificados WHERE url = ?", (decoded,)
    ).fetchone()
    conn.close()

    if not row:
        return HTMLResponse("<h1>Edital não encontrado</h1>", status_code=404)

    return _render(request, "dashboard/detail.html", {"edital": _parse_edital(row)})


def run():
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8765, log_level="info")


if __name__ == "__main__":
    run()
