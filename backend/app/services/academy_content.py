# Conteúdos da Academia (backend/content/academy): esquema pydantic, carregador com cache por mtime e verificação
# semântica (ids, respostas, stmt ids, slides). É usado pela API e pelo validador (app.tools.validate_academy).
# O modelo de programa (`exemplo`) é o mesmo do frontend: sequência de instruções e blocos aninhados.
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated, Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from app.config import settings
from app.services.problems import block_ids


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Bi(Strict):
    pt: str = Field(min_length=1)
    en: str = Field(min_length=1)


SIMPLE = ("definir", "ler", "calcular", "escrever", "chamar", "devolver")
FUNC_NAME_RE = r"^[A-Za-z_][A-Za-z0-9_]{0,40}$"
ID_RE = r"^[a-z0-9][a-z0-9_-]{0,79}$"
STMT_RE = r"^[A-Za-z0-9_-]{1,40}$"


class Stmt(Strict):
    id: str = Field(pattern=STMT_RE)
    tipo: Literal["definir", "ler", "calcular", "escrever", "chamar", "devolver", "se", "enquanto", "para"]
    texto: Bi | None = None
    cond: Bi | None = None
    py: str | None = None  # None: bloco só do fluxograma (não tem linha de Python)
    sim: list["Stmt"] = []
    nao: list["Stmt"] = []
    corpo: list["Stmt"] = []

    @model_validator(mode="after")
    def _by_tipo(self):
        if self.tipo in SIMPLE or self.tipo == "para":
            if self.texto is None:
                raise ValueError(f"'{self.id}': {self.tipo} precisa de texto")
        else:
            if self.cond is None:
                raise ValueError(f"'{self.id}': {self.tipo} precisa de cond")
        if self.tipo in ("se", "enquanto", "para") and not self.py:
            raise ValueError(f"'{self.id}': {self.tipo} precisa de py")
        if self.tipo == "se" and not self.sim:
            raise ValueError(f"'{self.id}': 'se' precisa do ramo sim")
        if self.tipo in ("enquanto", "para") and not self.corpo:
            raise ValueError(f"'{self.id}': {self.tipo} precisa de corpo")
        return self


Stmt.model_rebuild()


class Funcao(Strict):
    """Função do programa (def). `params` é o texto exato entre parênteses (type hints e valores por omissão incluídos)."""
    id: str = Field(pattern=STMT_RE)
    nome: str = Field(pattern=FUNC_NAME_RE)
    params: str = Field(default="", max_length=200, pattern=r"^[^\n]*$")
    texto: Bi | None = None
    devolve_tipo: str | None = Field(default=None, max_length=40)
    corpo: list[Stmt] = Field(min_length=1)


class Program(Strict):
    id: str = Field(pattern=STMT_RE)
    titulo: Bi
    funcoes: list[Funcao] = []
    corpo: list[Stmt] = Field(min_length=1)
    demoPath: list[str] | None = None

    @model_validator(mode="after")
    def _functions(self):
        names = [f.nome for f in self.funcoes]
        if len(set(names)) != len(names):
            raise ValueError("funcoes: nomes repetidos")
        ids = [s.id for s in all_stmts(self)] + [f.id for f in self.funcoes]
        if len(set(ids)) != len(ids):
            raise ValueError("exemplo: ids repetidos (stmts e funções partilham o mesmo espaço de ids)")
        if any(s.tipo == "devolver" for s in walk(self.corpo)):
            raise ValueError("'devolver' só pode estar dentro de uma função")
        return self


def walk(stmts: list[Stmt]):
    for s in stmts:
        yield s
        yield from walk(s.sim)
        yield from walk(s.nao)
        yield from walk(s.corpo)


def all_stmts(p: "Program"):
    """Todas as instruções do programa: principal e corpos das funções."""
    yield from walk(p.corpo)
    for f in p.funcoes:
        yield from walk(f.corpo)


def scope_body(p: "Program", alvo: str | None) -> list[Stmt]:
    """Corpo onde a atividade trabalha: o do programa principal ou o da função `alvo`."""
    return next(f for f in p.funcoes if f.id == alvo).corpo if alvo else p.corpo


class SlideRef(Strict):
    deck: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,39}$")
    de: int = Field(ge=1)
    ate: int = Field(ge=1)

    @model_validator(mode="after")
    def _range(self):
        if self.ate < self.de:
            raise ValueError("slides: 'ate' < 'de'")
        return self


class Module(Strict):
    id: str = Field(pattern=ID_RE)
    ordem: int = Field(ge=0)
    titulo: Bi
    descricao: Bi
    icone: str
    peca: str
    dificuldade: int = Field(ge=1, le=5)
    bloco: str
    sempre_aberto: bool = False

    @field_validator("bloco", mode="before")
    @classmethod
    def _bloco(cls, v):
        v = str(v)
        if v not in block_ids():
            raise ValueError(f"bloco inválido '{v}' (válidos: {', '.join(block_ids())})")
        return v


class Verificacao(Strict):
    pergunta: Bi
    opcoes: list[Bi] = Field(min_length=2)
    resposta: list[int] = Field(min_length=1)

    @model_validator(mode="after")
    def _idx(self):
        if any(not 0 <= i < len(self.opcoes) for i in self.resposta) or len(set(self.resposta)) != len(self.resposta):
            raise ValueError("resposta: índices inválidos ou repetidos")
        return self


class Base(Strict):
    enunciado: Bi
    explicacao: Bi


class Ligar(Base):
    tipo: Literal["ligar"]
    ids: list[str] | None = None
    alvo: str | None = None


class OrdenarFluxo(Base):
    tipo: Literal["ordenar_fluxograma"]
    ids: list[str] | None = None
    alvo: str | None = None


class OrdenarPython(Base):
    tipo: Literal["ordenar_python"]
    ids: list[str] | None = None
    alvo: str | None = None


class Item(Strict):
    id: str = Field(pattern=STMT_RE)
    texto: Bi


class OrdenarLista(Base):
    tipo: Literal["ordenar_lista"]
    itens: list[Item] = Field(min_length=2)


class Lacuna(Strict):
    stmt: str
    lado: Literal["py", "fluxo"]
    modelo: Bi
    respostas: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def _blank(self):
        if "___" not in self.modelo.pt or "___" not in self.modelo.en:
            raise ValueError("lacuna: o modelo precisa de '___' nas duas línguas")
        return self


class Completar(Base):
    tipo: Literal["completar"]
    lacunas: list[Lacuna] = Field(min_length=1)
    alvo: str | None = None


class Pergunta(Base):
    tipo: Literal["pergunta"]
    pergunta: Bi
    opcoes: list[Bi] = Field(min_length=2)
    resposta: list[int] = Field(min_length=1)

    @model_validator(mode="after")
    def _idx(self):
        if any(not 0 <= i < len(self.opcoes) for i in self.resposta) or len(set(self.resposta)) != len(self.resposta):
            raise ValueError("resposta: índices inválidos ou repetidos")
        return self


Atividade = Annotated[Ligar | OrdenarFluxo | OrdenarPython | OrdenarLista | Completar | Pergunta, Field(discriminator="tipo")]
USES_EXEMPLO = ("ligar", "ordenar_fluxograma", "ordenar_python", "completar")


class Section(Strict):
    id: str = Field(pattern=ID_RE)
    modulo: str
    ordem: int = Field(ge=1)
    titulo: Bi
    aprender: Bi
    exemplo: Program | None = None
    slides: list[SlideRef] = []
    leitura: Bi | None = None
    pistas: list[Bi] = Field(default=[], max_length=2)
    atividades: list[Atividade] = Field(min_length=1, max_length=3)
    verificacao: Verificacao

    @model_validator(mode="after")
    def _semantics(self):
        ex = self.exemplo
        for n, a in enumerate(self.atividades):
            if a.tipo in USES_EXEMPLO and ex is None:
                raise ValueError(f"atividade {n} ({a.tipo}) precisa de 'exemplo' na secção")
            if a.tipo not in USES_EXEMPLO:
                continue
            fids = {f.id for f in ex.funcoes}
            if a.alvo is not None and a.alvo not in fids:
                raise ValueError(f"atividade {n}: alvo '{a.alvo}' não é uma função do exemplo")
            body = scope_body(ex, a.alvo)
            if a.tipo in ("ligar", "ordenar_fluxograma", "ordenar_python") and a.ids is not None:
                top = {s.id for s in body}
                with_py = {s.id for s in walk(body) if s.py}
                allowed = {"ligar": with_py | (fids if a.alvo is None else set()), "ordenar_python": top & with_py, "ordenar_fluxograma": top}[a.tipo]
                bad = [i for i in a.ids if i not in allowed]
                if bad or len(set(a.ids)) != len(a.ids) or len(a.ids) < 2:
                    raise ValueError(f"atividade {n}: ids inválidos {bad}")
            if a.tipo == "completar":
                scope = {s.id: s for s in walk(body)}
                for lac in a.lacunas:
                    if lac.stmt not in scope:
                        raise ValueError(f"atividade {n}: stmt '{lac.stmt}' não existe no exemplo (alvo={a.alvo})")
                    if lac.lado == "py" and not scope[lac.stmt].py:
                        raise ValueError(f"atividade {n}: stmt '{lac.stmt}' não tem py (lado py)")
        if ex is not None:
            valid = {s.id for s in all_stmts(ex)} | {f.id for f in ex.funcoes}
            for sid in ex.demoPath or []:
                if sid not in valid:
                    raise ValueError(f"demoPath: stmt '{sid}' não existe")
        for n, a in enumerate(self.atividades):
            if a.tipo == "ordenar_lista" and len({i.id for i in a.itens}) != len(a.itens):
                raise ValueError(f"atividade {n}: ids de itens repetidos")
        return self


@dataclass
class Content:
    modules: list[Module] = field(default_factory=list)
    sections: dict[str, Section] = field(default_factory=dict)
    by_module: dict[str, list[Section]] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _read(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _fmt(exc: ValidationError) -> str:
    return "; ".join(f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()[:6])


def slide_decks_available(slides_dir: Path | None = None) -> dict[str, int]:
    root = slides_dir or settings.slides_dir
    out = {}
    if root.is_dir():
        for m in root.glob("*/manifest.json"):
            try:
                out[m.parent.name] = int(json.loads(m.read_text(encoding="utf-8"))["n_slides"])
            except (ValueError, KeyError, OSError):
                pass
    return out


def load(root: Path | None = None, slides_dir: Path | None = None) -> Content:
    """Carrega e verifica tudo. Não levanta exceções: os problemas ficam em content.errors / content.warnings."""
    root = root or settings.academy_dir
    c = Content()
    mods_file = root / "modules.yaml"
    if not mods_file.exists():
        return c
    try:
        raw = _read(mods_file) or []
        mods = [Module.model_validate(m) for m in raw]
    except (ValidationError, yaml.YAMLError, TypeError) as exc:
        c.errors.append(f"{mods_file}: {_fmt(exc) if isinstance(exc, ValidationError) else exc}")
        return c
    ids = [m.id for m in mods]
    if len(set(ids)) != len(ids):
        c.errors.append(f"{mods_file}: ids de módulos repetidos")
    if len({m.ordem for m in mods}) != len(mods):
        c.errors.append(f"{mods_file}: 'ordem' repetida")
    c.modules = sorted(mods, key=lambda m: m.ordem)
    decks = slide_decks_available(slides_dir)
    for path in sorted(root.glob("*/*.yaml")):
        try:
            sec = Section.model_validate(_read(path))
        except (ValidationError, yaml.YAMLError, TypeError) as exc:
            c.errors.append(f"{path}: {_fmt(exc) if isinstance(exc, ValidationError) else exc}")
            continue
        if path.parent.name != sec.modulo:
            c.errors.append(f"{path}: a secção diz modulo '{sec.modulo}' mas está na pasta '{path.parent.name}'")
        if sec.modulo not in ids:
            c.errors.append(f"{path}: módulo '{sec.modulo}' não existe em modules.yaml")
            continue
        if sec.id in c.sections:
            c.errors.append(f"{path}: id de secção repetido '{sec.id}'")
            continue
        for ref in sec.slides:
            if ref.deck not in decks:
                c.warnings.append(f"{path}: deck '{ref.deck}' ainda não foi importado")
            elif ref.ate > decks[ref.deck]:
                c.errors.append(f"{path}: slides {ref.de}-{ref.ate} fora do deck '{ref.deck}' ({decks[ref.deck]} slides)")
        c.sections[sec.id] = sec
    for m in c.modules:
        secs = sorted((s for s in c.sections.values() if s.modulo == m.id), key=lambda s: s.ordem)
        if len({s.ordem for s in secs}) != len(secs):
            c.errors.append(f"módulo {m.id}: 'ordem' de secções repetida")
        c.by_module[m.id] = secs
    return c


_cache: dict[tuple, tuple[tuple, Content]] = {}


def _stamp(root: Path) -> tuple:
    files = [root / "modules.yaml", *sorted(root.glob("*/*.yaml"))] if root.is_dir() else []
    return tuple((str(p), p.stat().st_mtime_ns) for p in files if p.exists())


def get_content() -> Content:
    """Conteúdo em cache, recarregado quando algum ficheiro muda (mtime). Secções inválidas ficam de fora."""
    root = settings.academy_dir
    stamp = _stamp(root)
    hit = _cache.get((str(root),))
    if hit and hit[0] == stamp:
        return hit[1]
    content = load(root)
    _cache[(str(root),)] = (stamp, content)
    return content
