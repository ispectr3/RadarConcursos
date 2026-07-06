from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from config import settings
from models import Edital

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]

_SERVICE = None


def _get_service():
    global _SERVICE
    if _SERVICE:
        return _SERVICE

    creds_path = settings.google_calendar_creds
    if not creds_path:
        logger.debug("GOOGLE_CALENDAR_CREDS não configurado.")
        return None

    token_path = Path(creds_path).parent / "token_calendar.json"
    creds = None

    if token_path.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
        except Exception:
            creds = None

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception:
                creds = None
        if not creds:
            try:
                flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
                creds = flow.run_local_server(port=0)
            except Exception as e:
                logger.warning("Falha na autenticação Google Calendar: %s", e)
                return None
        token_path.parent.mkdir(parents=True, exist_ok=True)
        with open(token_path, "w") as f:
            f.write(creds.to_json())

    try:
        _SERVICE = build("calendar", "v3", credentials=creds)
        return _SERVICE
    except Exception as e:
        logger.warning("Falha ao criar serviço Calendar: %s", e)
        return None


def _parse_date(text: str | None) -> tuple[datetime | None, datetime | None]:
    if not text:
        return None, None

    patterns = [
        r"(\d{2})/(\d{2})/(\d{4})\s*a\s*(\d{2})/(\d{2})/(\d{4})",
        r"(\d{2})/(\d{2})/(\d{4})\s*-\s*(\d{2})/(\d{2})/(\d{4})",
        r"(\d{2})/(\d{2})/(\d{4})",
        r"(\d{4})-(\d{2})-(\d{2})",
    ]

    for pat in patterns:
        m = re.search(pat, text)
        if m:
            groups = m.groups()
            if len(groups) == 6:
                start = datetime(int(groups[2]), int(groups[1]), int(groups[0]), 10, 0)
                end = datetime(int(groups[5]), int(groups[4]), int(groups[3]), 23, 59)
                return start, end
            elif len(groups) == 3:
                if len(groups[0]) == 4:
                    dt = datetime(int(groups[0]), int(groups[1]), int(groups[2]), 23, 59)
                else:
                    dt = datetime(int(groups[2]), int(groups[1]), int(groups[0]), 23, 59)
                return dt - timedelta(days=30), dt
    return None, None


def criar_evento_edital(edital: Edital) -> bool:
    service = _get_service()
    if not service:
        return False

    calendar_id = settings.google_calendar_id or "primary"

    title = f"📝 {edital.organizacao or edital.titulo}"
    if edital.cargo:
        title += f" — {edital.cargo}"

    start_dt, end_dt = _parse_date(edital.inscricoes)

    if not start_dt and edital.data_prova:
        start_dt, end_dt = _parse_date(edital.data_prova)

    if not start_dt:
        logger.debug("Nenhuma data encontrada para: %s", edital.titulo[:60])
        return False

    description_parts = [
        f"🏛️ Órgão: {edital.organizacao or edital.titulo}",
        f"📍 Estado: {edital.estado or 'Não informado'}",
        f"💼 Cargo: {edital.cargo or 'Não informado'}",
        f"💰 Salário: {edital.salario or 'Não informado'}",
        f"👥 Vagas: {edital.vagas or 'Não informado'}",
        "",
        f"📄 Fonte: {edital.fonte}",
        f"🔗 {edital.url}",
    ]
    if edital.resumo:
        description_parts.insert(3, f"\n📝 Resumo: {edital.resumo}")

    description = "\n".join(description_parts)

    event = {
        "summary": title,
        "description": description,
        "start": {
            "dateTime": start_dt.isoformat(),
            "timeZone": "America/Sao_Paulo",
        },
        "end": {
            "dateTime": end_dt.isoformat() if end_dt else (start_dt + timedelta(hours=1)).isoformat(),
            "timeZone": "America/Sao_Paulo",
        },
        "reminders": {
            "useDefault": False,
            "overrides": [
                {"method": "email", "minutes": 24 * 60},
                {"method": "popup", "minutes": 60},
            ],
        },
    }

    try:
        created = service.events().insert(calendarId=calendar_id, body=event).execute()
        logger.info("Evento criado no Google Calendar: %s", created.get("htmlLink"))
        return True
    except HttpError as e:
        logger.warning("Erro ao criar evento no Calendar: %s", e)
        return False
