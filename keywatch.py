from __future__ import annotations

import base64
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

logger = logging.getLogger("keywatch")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")

README_URL = "https://raw.githubusercontent.com/alistaitsacle/free-llm-api-keys/main/README.md"
DB_PATH = Path(__file__).resolve().parent / "data" / "keywatch.db"
BASE_URL = "https://aiapiv2.pekpik.com/v1"

_KEY_PATTERN = re.compile(r"`(sk-[a-zA-Z0-9]+)`")
_TABLE_PATTERN = re.compile(
    r"###\s+(.+?)\s+`[\d\-\s:]+`.*?\n(\|.+\|.+\|.+\|.+\|.+\|.+\|.+\|\n)+",
    re.DOTALL,
)


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


def _extract_smart_chat_keys(text: str) -> list[dict]:
    entries = []
    lines = text.split("\n")
    current_section = ""
    for line in lines:
        m = re.match(r"^###\s+(.+)$", line)
        if m:
            current_section = m.group(1).strip().lower()
        if "smart-chat" in current_section:
            for match in _KEY_PATTERN.finditer(line):
                key = match.group(1)
                entries.append({
                    "key": key,
                    "base_url": BASE_URL,
                    "model": "smart-chat",
                })
    return entries


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


def _update_github_secret(entries: list[dict]) -> None:
    gh_token = os.getenv("GH_TOKEN")
    repo = os.getenv("GITHUB_REPOSITORY")
    if not gh_token or not repo:
        logger.info("GH_TOKEN ou GITHUB_REPOSITORY não definidos; pulando auto-update.")
        return

    headers = {
        "Authorization": f"Bearer {gh_token}",
        "Accept": "application/vnd.github.v3+json",
    }

    try:
        pubkey_resp = requests.get(
            f"https://api.github.com/repos/{repo}/actions/secrets/public-key",
            headers=headers,
            timeout=15,
        )
        pubkey_resp.raise_for_status()
        pubkey_data = pubkey_resp.json()
        public_key = pubkey_data["key"]
        key_id = pubkey_data["key_id"]

        import nacl.bindings
        public_key_bytes = base64.b64decode(public_key)
        sealed = nacl.bindings.crypto_box_seal(
            json.dumps(entries).encode(), public_key_bytes
        )
        encrypted_value = base64.b64encode(sealed).decode()

        resp = requests.put(
            f"https://api.github.com/repos/{repo}/actions/secrets/FREE_API_ENTRIES",
            headers=headers,
            json={
                "encrypted_value": encrypted_value,
                "key_id": key_id,
            },
            timeout=15,
        )
        resp.raise_for_status()
        logger.info("FREE_API_ENTRIES atualizado automaticamente!")
    except Exception as e:
        logger.warning("Erro ao atualizar secret: %s", e)


def check() -> None:
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

    current_hash = _compute_hash(keys)
    last_hash = _get_last_hash()

    if current_hash == last_hash:
        logger.info("Chaves inalteradas (hash: %s...)", current_hash[:12])
        return

    _save_snapshot(keys, current_hash)
    logger.info("Novas chaves detectadas! Hash: %s...", current_hash[:12])

    smart_entries = _extract_smart_chat_keys(readme)
    if smart_entries:
        logger.info("Encontradas %d chaves smart-chat. Atualizando FREE_API_ENTRIES...", len(smart_entries))
        _update_github_secret(smart_entries)

    target_chat = os.getenv("KEYWATCH_CHAT_ID") or config.settings.telegram_chat_id
    if config.settings.telegram_bot_token and target_chat:
        from telegram import Bot
        bot = Bot(token=config.settings.telegram_bot_token)
        msg = (
            f"🔄 <b>Free API Keys atualizadas!</b>\n"
            f"📡 {len(keys)} chaves disponíveis"
        )
        if smart_entries:
            msg += f"\n🤖 {len(smart_entries)} smart-chat keys → FREE_API_ENTRIES atualizado"
        msg += (
            f"\n\n<a href='https://github.com/alistaitsacle/free-llm-api-keys'>Ver todas</a>"
        )
        try:
            bot.send_message(chat_id=target_chat, text=msg, parse_mode="HTML")
        except Exception as e:
            logger.warning("Erro ao enviar notificação: %s", e)


if __name__ == "__main__":
    check()
