"""Persistência em SQLite para evitar notificações duplicadas."""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from models import Edital
from urlnorm import normalize_url

DB_PATH = Path(__file__).resolve().parent / "data" / "monitor.db"
LEGACY_JSON = Path(__file__).resolve().parent / "enviados.json"


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS editais_notificados (
                url TEXT PRIMARY KEY,
                fonte TEXT,
                titulo TEXT,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS url_discovery (
                url TEXT PRIMARY KEY,
                first_seen_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS email_subscribers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO url_discovery (url, first_seen_at)
            SELECT url, created_at FROM editais_notificados
            """
        )
        conn.commit()


def was_notified(url: str) -> bool:
    with _connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM editais_notificados WHERE url = ? LIMIT 1", (url,)
        ).fetchone()
    return row is not None


def mark_notified(edital: Edital) -> None:
    payload = json.dumps(edital.to_json_dict(), ensure_ascii=False)
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO editais_notificados
            (url, fonte, titulo, payload_json, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (edital.url, edital.fonte, edital.titulo, payload, now),
        )
        conn.commit()


def touch_url_discoveries(urls: list[str]) -> None:
    """Registra a primeira vez que cada URL aparece na coleta (UTC)."""
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        for u in urls:
            conn.execute(
                "INSERT OR IGNORE INTO url_discovery (url, first_seen_at) VALUES (?, ?)",
                (u, now),
            )
        conn.commit()


def is_url_first_seen_today(url: str, tz: ZoneInfo) -> bool:
    with _connect() as conn:
        row = conn.execute(
            "SELECT first_seen_at FROM url_discovery WHERE url = ?",
            (url,),
        ).fetchone()
    if not row:
        return False
    dt = datetime.fromisoformat(row[0])
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    local = dt.astimezone(tz)
    return local.date() == datetime.now(tz).date()


_EMAIL_OK = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def add_email_subscriber(address: str) -> bool:
    address = address.strip().lower()
    if not _EMAIL_OK.match(address):
        return False
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO email_subscribers (email, active, created_at)
            VALUES (?, 1, ?)
            ON CONFLICT(email) DO UPDATE SET active = 1
            """,
            (address, now),
        )
        conn.commit()
    return True


def remove_email_subscriber(address: str) -> None:
    address = address.strip().lower()
    with _connect() as conn:
        conn.execute("DELETE FROM email_subscribers WHERE email = ?", (address,))
        conn.commit()


def set_subscriber_active(address: str, active: bool) -> None:
    address = address.strip().lower()
    with _connect() as conn:
        conn.execute(
            "UPDATE email_subscribers SET active = ? WHERE email = ?",
            (1 if active else 0, address),
        )
        conn.commit()


def list_email_subscribers() -> list[tuple[str, bool, str]]:
    """Lista (email, active, created_at)."""
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT email, active, created_at FROM email_subscribers ORDER BY email"
        ).fetchall()
    return [(str(r[0]), bool(r[1]), str(r[2])) for r in rows]


def list_active_subscriber_emails() -> list[str]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT email FROM email_subscribers WHERE active = 1 ORDER BY email"
        ).fetchall()
    return [str(r[0]) for r in rows]


def migrate_json_if_exists() -> None:
    if not LEGACY_JSON.is_file():
        return
    try:
        raw = json.loads(LEGACY_JSON.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return
    if not isinstance(raw, list):
        return
    init_db()
    with _connect() as conn:
        for item in raw:
            if not isinstance(item, str) or not item.strip():
                continue
            key = normalize_url(item) if item.startswith("http") else item.strip()
            placeholder: dict[str, Any] = {
                "titulo": "(migrado de enviados.json)",
                "url": key,
                "fonte": "legacy",
            }
            conn.execute(
                """
                INSERT OR IGNORE INTO editais_notificados
                (url, fonte, titulo, payload_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    key,
                    "legacy",
                    placeholder["titulo"],
                    json.dumps(placeholder, ensure_ascii=False),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
        conn.commit()
