"""HTTP helpers compartilhados pelos scrapers."""

from __future__ import annotations

import requests
from bs4 import BeautifulSoup

from config import settings


def get_soup(url: str, timeout: int = 30) -> BeautifulSoup:
    headers = {"User-Agent": settings.user_agent}
    response = requests.get(url, headers=headers, timeout=timeout)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def fetch_text(url: str, timeout: int = 30) -> str:
    headers = {"User-Agent": settings.user_agent}
    response = requests.get(url, headers=headers, timeout=timeout)
    response.raise_for_status()
    response.encoding = response.apparent_encoding
    return response.text
