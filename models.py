"""Modelo de dados de um edital / processo seletivo."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Edital:
    titulo: str
    url: str
    fonte: str
    organizacao: str | None = None
    cargo: str | None = None
    salario: str | None = None
    estado: str | None = None
    cronograma: str | None = None
    inscricoes: str | None = None
    isencao: str | None = None
    data_prova: str | None = None
    local_prova: str | None = None
    link_edital: str | None = None
    link_inscricao: str | None = None
    resumo: str | None = None
    data_atualizacao: str | None = None
    vagas: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_json_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d
