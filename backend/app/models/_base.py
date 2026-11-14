# Utilitários comuns dos modelos: hora UTC e colunas de data com fuso horário.
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime


def utcnow() -> datetime:
    return datetime.now(UTC)


def ts_column(**kw) -> Column:
    return Column(DateTime(timezone=True), nullable=False, **kw)
