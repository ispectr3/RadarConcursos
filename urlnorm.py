"""Normalização de URL para deduplicação estável."""

from __future__ import annotations

from urllib.parse import urldefrag, urlparse, urlunparse


def normalize_url(url: str) -> str:
    raw = url.strip()
    raw, _frag = urldefrag(raw)
    p = urlparse(raw)
    if not p.scheme or not p.netloc:
        return raw
    path = p.path or "/"
    if len(path) > 1:
        path = path.rstrip("/")
    netloc = p.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    scheme = p.scheme.lower()
    if scheme == "http":
        scheme = "https"
    return urlunparse((scheme, netloc, path, "", "", ""))
