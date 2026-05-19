"""Extração leve de texto de PDFs (editais publicados como .pdf)."""

from __future__ import annotations

import io

import requests
from pypdf import PdfReader

from config import settings


def extract_text_from_pdf_url(url: str, max_pages: int = 4, timeout: int = 45) -> str:
    headers = {"User-Agent": settings.user_agent}
    response = requests.get(url, headers=headers, timeout=timeout)
    response.raise_for_status()
    reader = PdfReader(io.BytesIO(response.content))
    chunks: list[str] = []
    for i, page in enumerate(reader.pages):
        if i >= max_pages:
            break
        text = page.extract_text() or ""
        if text.strip():
            chunks.append(text)
    return "\n".join(chunks)
