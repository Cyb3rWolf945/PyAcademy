# Problemas: esquema pydantic do YAML, carregador (YAML -> BD) e vista pública sem segredos.
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models._base import utcnow
from app.models.problem import Problem

log = logging.getLogger("pyarena.problems")

CODE_TIPOS = ("programa", "funcao", "bug")
QUESTION_TIPOS = ("quiz", "decomposicao", "tracar")
REQUISITOS_KEYS = {"usa", "proibe", "define_funcao", "recursiva"}
SECRET_QUESTION_KEYS = ("resposta", "resposta_texto")


@lru_cache(maxsize=1)
def curriculum() -> dict:
    """Carrega backend/content/curriculum.yaml (ids de blocos e regiões válidos)."""
    path = Path(__file__).resolve().parents[2] / "content" / "curriculum.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def block_ids() -> list[str]:
    return [str(b["id"]) for b in curriculum()["blocos"]]


def region_ids() -> list[str]:
    return [r["id"] for r in curriculum()["regioes"]]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Bi(Strict):
    """Texto bilingue: as duas línguas são obrigatórias e não vazias."""
    pt: str = Field(min_length=1)
    en: str = Field(min_length=1)


Text = str | Bi  # outputs: iguais nas duas línguas (str) ou diferentes ({pt, en})


class Case(Strict):
    """Um caso de teste/exemplo: programa (stdin/stdout) ou função (args/devolve).
    Nos testes de funções, `args_gerador` (expressão Python) substitui `args` e `devolve`: ambos são
    calculados no runner pela solução de referência."""
    stdin: str | None = None
    stdout: Text | None = None
    args: list[Any] | None = None
    args_gerador: str | None = None
    devolve: Any | None = None

    @model_validator(mode="after")
    def _generator(self):
        if self.args_gerador is not None and (self.args is not None or self.devolve is not None):
            raise ValueError("args_gerador nao pode ser combinado com args/devolve")
        return self


class Pergunta(Strict):
    """Pergunta de quiz / decomposição / traçar: opcoes+resposta (índices) ou resposta_texto."""
    pergunta: Bi
    codigo: str | None = None
    opcoes: list[str | Bi] | None = None
    resposta: list[int] | None = None
    resposta_texto: str | Bi | None = None

    @model_validator(mode="after")
    def _one_answer(self):
        if (self.resposta is None) == (self.resposta_texto is None):
            raise ValueError("exatamente um de resposta / resposta_texto")
        if self.resposta is not None:
            if not self.opcoes or not self.resposta or any(not 0 <= i < len(self.opcoes) for i in self.resposta):
                raise ValueError("resposta precisa de opcoes e de indices validos")
        elif self.opcoes:
            raise ValueError("resposta_texto nao leva opcoes")
        return self


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
    bloco: str
    regiao: str
    dificuldade: int = Field(ge=1, le=5)
    origem: Literal["variacao_aula", "novo", "mais_alem", "boss"] = "novo"
    estado: Literal["rascunho", "aprovado"]
    enunciado: Bi
    codigo_inicial: str | Bi | None = None  # editor pré-preenchido; OBRIGATÓRIO no tipo bug
    assinatura: str | None = None  # tipo funcao, ex. "calcular_media(notas)"
    exemplos: list[Case] = []  # obrigatórios nos tipos com código
    testes: list[Case] = []
    perguntas: list[Pergunta] = []  # tipos quiz / decomposicao / tracar
    comparacao: Literal["texto", "numeros", "exato"] = "texto"
    ordem_importa: bool = True  # funcao: False = listas comparadas como multiconjuntos
    requisitos: dict[str, Any] | None = None
    pistas: list[Bi] = []
    erros_comuns: list[ErroComum] = []
    limite_tempo_s: float = Field(default=2, gt=0, le=10)
    solucao_referencia: str | Bi | None = None  # uma por língua só se o texto do output mudar
    # Algoritmia (opcional)
    nivel_algo: Literal["hard", "extra_hard", "hardcore_insane"] | None = None
    restricoes: Text | None = None
    solucao_ingenua: str | None = None
    editorial: Bi | None = None

    @field_validator("bloco", mode="before")
    @classmethod
    def _bloco_str(cls, v):
        v = str(v)
        if v not in block_ids():
            raise ValueError(f"bloco invalido '{v}' (validos: {', '.join(block_ids())})")
        return v

    @field_validator("regiao")
    @classmethod
    def _regiao(cls, v):
        if v not in region_ids():
            raise ValueError(f"regiao invalida '{v}' (validas: {', '.join(region_ids())})")
        return v

    @field_validator("requisitos")
    @classmethod
    def _requisitos(cls, v):
        if v is None:
            return v
        extra = set(v) - REQUISITOS_KEYS
        if extra:
            raise ValueError(f"requisitos desconhecidos: {sorted(extra)}")
        df = v.get("define_funcao")
        if df is not None and not (isinstance(df, dict) and isinstance(df.get("nome"), str)):
            raise ValueError("define_funcao precisa de {nome, parametros}")
        return v

    @model_validator(mode="after")
    def _by_tipo(self):
        if self.tipo in CODE_TIPOS:
            if not self.exemplos or not self.testes:
                raise ValueError("exemplos e testes sao obrigatorios neste tipo")
            if not self.solucao_referencia:
                raise ValueError("solucao_referencia e obrigatoria neste tipo")
            if self.perguntas:
                raise ValueError("perguntas so existem em quiz/decomposicao/tracar")
            if self.tipo == "bug" and not self.codigo_inicial:
                raise ValueError("codigo_inicial e obrigatorio no tipo bug")
            if self.tipo == "funcao" and not self.assinatura:
                raise ValueError("assinatura e obrigatoria no tipo funcao")
            if self.exemplos and any(c.args_gerador is not None for c in self.exemplos):
                raise ValueError("exemplos nao podem usar args_gerador")
            if any(c.args_gerador is not None for c in self.testes) and not self.assinatura:
                raise ValueError("args_gerador so em problemas com assinatura (funcao)")
        else:
            if self.exemplos or self.testes or self.solucao_referencia or self.solucao_ingenua:
                raise ValueError("quiz/decomposicao/tracar nao levam exemplos, testes nem solucoes")
            if not self.perguntas:
                raise ValueError("perguntas sao obrigatorias neste tipo")
        if self.nivel_algo:
            if self.tipo != "funcao":
                raise ValueError("nivel_algo exige tipo funcao")
            if not self.solucao_ingenua or not self.editorial:
                raise ValueError("nivel_algo exige solucao_ingenua e editorial")
        return self

    def public_perguntas(self) -> list[dict]:
        return [{k: v for k, v in p.model_dump(mode="json").items() if k not in SECRET_QUESTION_KEYS} for p in self.perguntas]

    def public(self) -> dict:
        """Vista pública: SÓ campos da lista branca. Nunca testes, soluções nem editorial."""
        d = self.model_dump(mode="json")
        out = {k: d[k] for k in (
            "id", "titulo", "tipo", "bloco", "regiao", "dificuldade", "origem", "enunciado",
            "codigo_inicial", "assinatura", "exemplos", "comparacao", "requisitos", "limite_tempo_s",
            "nivel_algo", "restricoes",
        )}
        out["perguntas"] = self.public_perguntas()
        out["exemplos"] = [{k: v for k, v in e.items() if k != "args_gerador"} for e in out["exemplos"]]
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
