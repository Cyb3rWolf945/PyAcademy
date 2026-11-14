# Problemas: esquema pydantic do YAML, carregador (YAML -> BD) e vista pública sem segredos.
import logging
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models._base import utcnow
from app.models.problem import Problem

log = logging.getLogger("pyarena.problems")


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Bi(Strict):
    """Texto bilingue: as duas línguas são obrigatórias e não vazias."""
    pt: str = Field(min_length=1)
    en: str = Field(min_length=1)


Text = str | Bi  # outputs: iguais nas duas línguas (str) ou diferentes ({pt, en})


class Case(Strict):
    """Um caso de teste/exemplo: programa (stdin/stdout) ou função (args/devolve)."""
    stdin: str | None = None
    stdout: Text | None = None
    args: list[Any] | None = None
    devolve: Any | None = None


class ErroComum(Strict):
    stdout: Text | None = None
    devolve: Any | None = None
    quando_stdin: str | None = None
    quando_args: list[Any] | None = None
    mensagem: Bi


class ProblemSpec(Strict):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,78}$")
    titulo: Bi
    tipo: Literal["programa", "funcao", "decomposicao", "tracar", "bug", "quiz"]
    bloco: str = Field(pattern=r"^[1-7]b?$")
    regiao: str | None = None
    dificuldade: int = Field(ge=1, le=5)
    origem: Literal["variacao_aula", "novo", "mais_alem", "boss"] = "novo"
    estado: Literal["rascunho", "aprovado"]
    enunciado: Bi
    assinatura: str | None = None  # tipo funcao, ex. "calcular_media(notas)"
    exemplos: list[Case] = Field(min_length=1)
    testes: list[Case] = Field(min_length=1)
    comparacao: Literal["texto", "numeros", "exato"] = "texto"
    requisitos: dict[str, Any] | None = None
    pistas: list[Bi] = []
    erros_comuns: list[ErroComum] = []
    limite_tempo_s: float = Field(default=2, gt=0, le=10)
    solucao_referencia: str | Bi  # uma por língua só se o texto do output mudar
    # Algoritmia (opcional)
    nivel_algo: Literal["hard", "extra_hard", "hardcore_insane"] | None = None
    restricoes: Text | None = None
    solucao_ingenua: str | None = None
    editorial: Bi | None = None

    @field_validator("bloco", mode="before")
    @classmethod
    def _bloco_str(cls, v):
        return str(v)

    def public(self) -> dict:
        """Vista pública: SÓ campos da lista branca. Nunca testes, soluções nem editorial."""
        d = self.model_dump(mode="json")
        out = {k: d[k] for k in (
            "id", "titulo", "tipo", "bloco", "regiao", "dificuldade", "origem", "enunciado",
            "assinatura", "exemplos", "comparacao", "requisitos", "limite_tempo_s",
            "nivel_algo", "restricoes",
        )}
        out["pistas_count"] = len(self.pistas)
        return out


def parse_yaml(path: Path) -> ProblemSpec:
    return ProblemSpec.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


def iter_problem_files(root: Path):
    return sorted(root.rglob("*.yaml"))


async def sync_problems(db: AsyncSession, root: Path) -> int:
    """Lê backend/problems/**/*.yaml e faz upsert na BD. Ficheiros inválidos são ignorados e registados."""
    n = 0
    for path in iter_problem_files(root):
        try:
            spec = parse_yaml(path)
        except Exception as exc:  # noqa: BLE001 - um YAML mau não pode impedir a app de arrancar
            log.error("problema invalido %s: %s", path, exc)
            continue
        values = dict(
            slug=spec.id, data=spec.model_dump(mode="json"), estado=spec.estado,
            bloco=spec.bloco, tipo=spec.tipo, updated_at=utcnow(),
        )
        stmt = insert(Problem).values(**values)
        stmt = stmt.on_conflict_do_update(index_elements=["slug"], set_={k: v for k, v in values.items() if k != "slug"})
        await db.execute(stmt)
        n += 1
    await db.commit()
    return n
