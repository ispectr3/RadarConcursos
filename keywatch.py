from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import requests

import config
from notifications import send_telegram_html

logger = logging.getLogger("keywatch")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")

README_URL = "https://raw.githubusercontent.com/alistaitsacle/free-llm-api-keys/main/README.md"
DB_PATH = Path(__file__).resolve().parent / "data" / "keywatch.db"

_KEY_PATTERN = re.compile(r"`(sk-[a-zA-Z0-9]+)`")


def _init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS key_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hash TEXT NOT NULL,
            keys_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


def _fetch_readme() -> str:
    resp = requests.get(README_URL, timeout=30)
    resp.raise_for_status()
    return resp.text


def _extract_keys(text: str) -> list[str]:
    return list(dict.fromkeys(_KEY_PATTERN.findall(text)))


def _compute_hash(keys: list[str]) -> str:
    return hashlib.sha256("".join(sorted(keys)).encode()).hexdigest()


def _get_last_hash() -> str | None:
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT hash FROM key_snapshots ORDER BY id DESC LIMIT 1"
    ).fetchone()
    conn.close()
    return row[0] if row else None


def _save_snapshot(keys: list[str], hash_val: str) -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO key_snapshots (hash, keys_json, created_at) VALUES (?, ?, ?)",
        (hash_val, json.dumps(keys), datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    conn.close()


def _format_telegram_alert(keys: list[str]) -> str:
    gemini = [k for k in keys if k in _last_keys]
    smart = [k for k in keys if k in _last_keys]

    msg = (
        "🔄 <b>Chaves Free API Atualizadas!</b>\n\n"
        f"Total: {len(keys)} chaves disponíveis\n\n"
    )

    gemini_keys = [k for k in keys if "gemini" in _last_keys_raw.get(k, "").lower()]
    smart_keys = [k for k in keys if "smart-chat" in _last_keys_raw.get(k, "").lower()]

    if gemini_keys:
        msg += f"🧠 <b>Gemini 2.5 Flash</b> ({len(gemini_keys)}):\n"
        msg += "\n".join(f"  <code>{k}</code>" for k in gemini_keys[:3])
        msg += "\n\n"

    if smart_keys:
        msg += f"🤖 <b>Smart-Chat</b> ({len(smart_keys)}):\n"
        msg += "\n".join(f"  <code>{k}</code>" for k in smart_keys[:3])
        msg += "\n\n"

    msg += "<a href='https://github.com/alistaitsacle/free-llm-api-keys'>Ver todas</a>"
    return msg


_last_keys: list[str] = []
_last_keys_raw: dict[str, str] = {}


def check() -> None:
    global _last_keys, _last_keys_raw

    _init_db()

    try:
        readme = _fetch_readme()
    except Exception as e:
        logger.warning("Erro ao buscar README: %s", e)
        return

    keys = _extract_keys(readme)
    if not keys:
        logger.info("Nenhuma chave encontrada no README.")
        return

    _last_keys = keys

    current_hash = _compute_hash(keys)
    last_hash = _get_last_hash()

    if current_hash == last_hash:
        logger.info("Chaves inalteradas (hash: %s...)", current_hash[:12])
        return

    _save_snapshot(keys, current_hash)
    logger.info("Novas chaves detectadas! Hash: %s...", current_hash[:12])

    if settings.telegram_bot_token and settings.telegram_chat_id:
        msg = (
            f"🔄 <b>Free API Keys atualizadas!</b>\n"
            f"📡 {len(keys)} chaves disponíveis\n\n"
            f"💡 Copie as keys em:\n"
            f"<a href='https://github.com/alistaitsacle/free-llm-api-keys'>github.com/alistaitsacle/free-llm-api-keys</a>"
        )
        try:
            send_telegram_html(msg)
        except Exception as e:
            logger.warning("Erro ao enviar notificação: %s", e)


if __name__ == "__main__":
    check()
