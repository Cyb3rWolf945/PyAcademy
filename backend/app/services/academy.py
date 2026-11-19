# Academia: estado dos módulos e secções (desbloqueio híbrido), vista pública sem respostas, correção das atividades
# no servidor, verificação da secção e pontos (livro user_points, idempotente). As respostas nunca saem do servidor.
import random
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import ApiError
from app.models._base import utcnow
from app.models.academy import AcademyActivityLog, AcademyProgress
from app.models.points import UserPoints
from app.models.user import Role, User
from app.services import academy_content as ac
from app.services import points as pts
from app.services.leaderboard import LISBON
from app.services.problems import curriculum

BADGE_POINTS = 25
STREAK_POINTS = 2
REASONS = ("academy_section", "academy_badge", "academy_streak")


# ---------------- regras de pontos e desbloqueio ----------------
def section_points(module: ac.Module) -> int:
    """M0–M1: 3 · M2–M3: 5 · M4 em diante (e a caça aos bugs): 8."""
    return 3 if module.ordem <= 1 else 5 if module.ordem <= 3 else 8


def open_blocks() -> set[str]:
    """Blocos marcados como abertos no currículo (o painel do professor edita este ficheiro)."""
    return {str(b["id"]) for b in curriculum()["blocos"] if b.get("aberto")}


def today_lisbon() -> date:
    return utcnow().astimezone(LISBON).date()


async def completed_ids(db: AsyncSession, user_id: int) -> set[str]:
    return set((await db.execute(select(AcademyProgress.section_id).where(
        AcademyProgress.user_id == user_id, AcademyProgress.completed_at.is_not(None)))).scalars())


def module_states(content: ac.Content, done: set[str]) -> dict[str, dict]:
    """id -> {estado, motivo, em_breve, concluidas, n}. Um módulo abre se for o M0, se o anterior estiver concluído
    ou se o seu bloco estiver aberto no currículo."""
    blocks = open_blocks()
    out: dict[str, dict] = {}
    prev_done = True
    for m in content.modules:
        secs = content.by_module.get(m.id, [])
        n, k = len(secs), sum(1 for s in secs if s.id in done)
        soon = n == 0
        motivo = None
        if m.sempre_aberto:
            motivo = "always"
        elif prev_done and not soon and out and out[prev_id]["n"] > 0:
            motivo = "prev_done"
        elif m.bloco in blocks:
            motivo = "teacher"
        unlocked = motivo is not None and not soon
        estado = "locked" if not unlocked else "done" if k == n else "in_progress" if k > 0 else "open"
        out[m.id] = {"estado": estado, "motivo": motivo if unlocked else None, "em_breve": soon, "concluidas": k, "n": n}
        prev_done, prev_id = (k == n and n > 0), m.id
    return out


def section_states(content: ac.Content, module_id: str, done: set[str], module_unlocked: bool) -> dict[str, str]:
    """secção -> locked|current|done. A primeira não concluída é a atual; as seguintes ficam bloqueadas."""
    out, current_found = {}, False
    for s in content.by_module.get(module_id, []):
        if s.id in done:
            out[s.id] = "done"
        elif module_unlocked and not current_found:
            out[s.id], current_found = "current", True
        else:
            out[s.id] = "locked"
    return out


def get_module(content: ac.Content, module_id: str) -> ac.Module:
    m = next((x for x in content.modules if x.id == module_id), None)
    if m is None:
        raise ApiError(404, "academy.module_not_found")
    return m


def get_section(content: ac.Content, section_id: str) -> ac.Section:
    s = content.sections.get(section_id)
    if s is None:
        raise ApiError(404, "academy.section_not_found")
    return s


async def access(db: AsyncSession, user: User, section_id: str) -> tuple[ac.Content, ac.Section, ac.Module, dict[str, str], set[str]]:
    """Devolve a secção se o utilizador a puder abrir; senão 403 academy.locked (professores veem tudo)."""
    content = ac.get_content()
    sec = get_section(content, section_id)
    module = get_module(content, sec.modulo)
    done = await completed_ids(db, user.id)
    ms = module_states(content, done)
    states = section_states(content, module.id, done, ms[module.id]["estado"] != "locked")
    if states[sec.id] == "locked" and user.role != Role.teacher:
        raise ApiError(403, "academy.locked")
    return content, sec, module, states, done


# ---------------- vista pública (sem respostas) ----------------
def _shuffled(items: list, seed: str) -> list:
    out = list(items)
    for k in range(10):
        random.Random(f"{seed}:{k}").shuffle(out)
        if len(out) < 2 or out != items:
            break
    return out


def _stmt_ids(sec: ac.Section, a) -> list[str]:
    """Ids da atividade por ordem do programa, no âmbito certo (programa principal ou função `alvo`):
    ligar = stmts com py (e, sem alvo, também as funções: pílula ↔ linha def); ordenar_python = 1.º nível com py;
    ordenar_fluxograma = 1.º nível."""
    ex = sec.exemplo
    body = ac.scope_body(ex, a.alvo)
    if a.tipo == "ligar":
        pool = ([f.id for f in ex.funcoes] if a.alvo is None else []) + [s.id for s in ac.walk(body) if s.py]
    elif a.tipo == "ordenar_python":
        pool = [s.id for s in body if s.py]
    else:
        pool = [s.id for s in body]
    return [i for i in pool if a.ids is None or i in a.ids]


def activity_public(sec: ac.Section, idx: int, user_id: int) -> dict:
    a = sec.atividades[idx]
    seed = f"{user_id}:{sec.id}:{idx}"
    base = {"idx": idx, "tipo": a.tipo, "enunciado": a.enunciado.model_dump()}
    if getattr(a, "alvo", None):
        base["alvo"] = a.alvo  # função onde a atividade trabalha
    if a.tipo == "ligar":
        ids = _stmt_ids(sec, a)
        base["ids"], base["linhas"] = ids, _shuffled(ids, seed)  # a coluna do Python nunca vem por ordem
    elif a.tipo in ("ordenar_fluxograma", "ordenar_python"):
        base["itens"] = _shuffled(_stmt_ids(sec, a), seed)
    elif a.tipo == "ordenar_lista":
        base["itens"] = _shuffled([{"id": i.id, "texto": i.texto.model_dump()} for i in a.itens], seed)
    elif a.tipo == "completar":
        base["lacunas"] = [{"stmt": l.stmt, "lado": l.lado, "modelo": l.modelo.model_dump()} for l in a.lacunas]
    else:  # pergunta
        base.update(pergunta=a.pergunta.model_dump(), opcoes=[o.model_dump() for o in a.opcoes], multipla=len(a.resposta) > 1,
                    mostrar_exemplo=sec.exemplo is not None)
    return base


def section_public(sec: ac.Section, module: ac.Module, state: str, user_id: int, prog: AcademyProgress | None,
                   solved: set[int], next_id: str | None) -> dict:
    return {
        "id": sec.id, "modulo": sec.modulo, "ordem": sec.ordem, "titulo": sec.titulo.model_dump(), "aprender": sec.aprender.model_dump(),
        "exemplo": sec.exemplo.model_dump(exclude_none=True) if sec.exemplo else None,
        "slides": [r.model_dump() for r in sec.slides], "leitura": sec.leitura.model_dump() if sec.leitura else None,
        "n_pistas": len(sec.pistas), "hints_used": prog.hints_used if prog else 0,
        "atividades": [activity_public(sec, i, user_id) for i in range(len(sec.atividades))], "atividades_resolvidas": sorted(solved),
        "verificacao": {
            "pergunta": sec.verificacao.pergunta.model_dump(), "opcoes": [o.model_dump() for o in sec.verificacao.opcoes],
            "multipla": len(sec.verificacao.resposta) > 1, "mostrar_exemplo": sec.exemplo is not None,
        },
        "estado": state, "concluida": bool(prog and prog.completed_at), "pontos": section_points(module), "proxima": next_id,
    }


# ---------------- correção ----------------
def _norm(v) -> tuple:
    s = " ".join(str(v).split()).casefold()
    try:
        return ("n", float(s.replace(",", ".")))
    except ValueError:
        return ("s", s)


def check(sec: ac.Section, a, resposta: dict) -> tuple[bool, dict | None]:
    """(correta, detalhe). O detalhe diz o que está errado sem revelar a solução."""
    try:
        if a.tipo == "ligar":
            ids, pares = _stmt_ids(sec, a), resposta["pares"]
            wrong = [i for i in ids if pares.get(i) != i]
            return not wrong and set(pares) == set(ids), {"erradas": wrong}
        if a.tipo in ("ordenar_fluxograma", "ordenar_python"):
            want, got = _stmt_ids(sec, a), resposta["ordem"]
            return got == want, {"erradas": [i for i, w in enumerate(want) if i >= len(got) or got[i] != w]}
        if a.tipo == "ordenar_lista":
            want, got = [i.id for i in a.itens], resposta["ordem"]
            return got == want, {"erradas": [i for i, w in enumerate(want) if i >= len(got) or got[i] != w]}
        if a.tipo == "completar":
            vals = resposta["valores"]
            wrong = [i for i, lac in enumerate(a.lacunas) if i >= len(vals) or _norm(vals[i]) not in {_norm(r) for r in lac.respostas}]
            return not wrong and len(vals) == len(a.lacunas), {"erradas": wrong}
        return set(resposta["escolha"]) == set(a.resposta), None
    except (KeyError, TypeError, AttributeError):
        raise ApiError(422, "academy.invalid_answer") from None


def valid_shape(a, resposta) -> bool:
    if not isinstance(resposta, dict):
        return False
    if a.tipo == "ligar":
        p = resposta.get("pares")
        return isinstance(p, dict) and len(p) <= 60 and all(isinstance(k, str) and isinstance(v, str) for k, v in p.items())
    if a.tipo in ("ordenar_fluxograma", "ordenar_python", "ordenar_lista"):
        o = resposta.get("ordem")
        return isinstance(o, list) and len(o) <= 60 and all(isinstance(i, str) for i in o)
    if a.tipo == "completar":
        v = resposta.get("valores")
        return isinstance(v, list) and len(v) <= 20 and all(isinstance(i, (str, int, float)) and len(str(i)) <= 200 for i in v)
    e = resposta.get("escolha")
    return isinstance(e, list) and len(e) <= 20 and all(isinstance(i, int) and not isinstance(i, bool) for i in e)


async def answer_activity(db: AsyncSession, user: User, section_id: str, idx: int, resposta) -> dict:
    content, sec, _module, _states, _done = await access(db, user, section_id)
    if not 0 <= idx < len(sec.atividades):
        raise ApiError(404, "academy.activity_not_found")
    a = sec.atividades[idx]
    if not valid_shape(a, resposta):
        raise ApiError(422, "academy.invalid_answer")
    ok, detail = check(sec, a, resposta)
    await db.execute(insert(AcademyActivityLog).values(user_id=user.id, section_id=sec.id, activity_idx=idx, attempts=0).on_conflict_do_nothing())
    log = await db.get(AcademyActivityLog, (user.id, sec.id, idx), with_for_update=True)
    log.attempts += 1
    if ok and log.solved_at is None:
        log.solved_at = utcnow()
    attempts = log.attempts
    await db.commit()
    out: dict = {"correta": ok}
    if not ok and detail:
        out["detalhe"] = detail
    if ok or attempts >= 2:
        out["explicacao"] = a.explicacao.model_dump()
    return out


async def open_hint(db: AsyncSession, user: User, section_id: str, n: int) -> dict:
    _c, sec, _m, _s, _d = await access(db, user, section_id)
    if not 1 <= n <= len(sec.pistas):
        raise ApiError(404, "academy.hint_not_found")
    prog = await ensure_progress(db, user.id, sec.id)
    prog.hints_used = max(prog.hints_used, n)
    await db.commit()
    return {"n": n, "texto": sec.pistas[n - 1].model_dump()}


async def ensure_progress(db: AsyncSession, user_id: int, section_id: str) -> AcademyProgress:
    await db.execute(insert(AcademyProgress).values(user_id=user_id, section_id=section_id, started_at=utcnow(),
                                                    verify_attempts=0, hints_used=0, first_try=False).on_conflict_do_nothing())
    return await db.get(AcademyProgress, (user_id, section_id), with_for_update=True)


# ---------------- verificação, pontos, badge, streak ----------------
async def verify(db: AsyncSession, user: User, section_id: str, resposta) -> dict:
    content, sec, module, states, done = await access(db, user, section_id)
    v = sec.verificacao
    if not (isinstance(resposta, dict) and isinstance(resposta.get("escolha"), list)
            and all(isinstance(i, int) and not isinstance(i, bool) for i in resposta["escolha"]) and len(resposta["escolha"]) <= 20):
        raise ApiError(422, "academy.invalid_answer")
    ok = set(resposta["escolha"]) == set(v.resposta)
    prog = await ensure_progress(db, user.id, sec.id)
    siblings = content.by_module[module.id]
    pos = next(i for i, s in enumerate(siblings) if s.id == sec.id)
    next_id = siblings[pos + 1].id if pos + 1 < len(siblings) else None
    out = {"correta": ok, "concluida": prog.completed_at is not None, "pontos": 0, "proxima": next_id}
    if not ok:
        prog.verify_attempts += 1
        await db.commit()
        out["explicacao"] = None
        return out
    if prog.completed_at is not None:  # já concluída: rever não dá pontos
        await db.commit()
        return out
    first_try = prog.verify_attempts == 0
    prog.completed_at, prog.first_try = utcnow(), first_try
    base = section_points(module)
    amount = max(1, base // 2) if prog.hints_used > 0 else base
    await db.flush()
    got = await pts.award(db, None, user.id, amount, "academy_section", None, sec.id, notify=False)
    out.update(concluida=True, pontos=amount if got else 0)
    if await pts.award(db, None, user.id, STREAK_POINTS, "academy_streak", None, today_lisbon().isoformat(), notify=False):
        out["streak"] = STREAK_POINTS
    done_now = done | {sec.id}
    if all(s.id in done_now for s in siblings):
        if await pts.award(db, None, user.id, BADGE_POINTS, "academy_badge", None, module.id, notify=False):
            out["badge"] = {"modulo": module.id, "pontos": BADGE_POINTS}
    await db.commit()
    return out


# ---------------- vistas agregadas ----------------
async def earned_by_module(db: AsyncSession, user_id: int, content: ac.Content) -> dict[str, int]:
    sec_to_mod = {s.id: s.modulo for s in content.sections.values()}
    rows = (await db.execute(select(UserPoints.reason, UserPoints.problem_slug, UserPoints.points).where(
        UserPoints.user_id == user_id, UserPoints.reason.in_(("academy_section", "academy_badge"))))).all()
    out: dict[str, int] = {}
    for reason, slug, p in rows:
        mod = sec_to_mod.get(slug) if reason == "academy_section" else slug
        if mod:
            out[mod] = out.get(mod, 0) + p
    return out


async def streak_days(db: AsyncSession, user_id: int) -> int:
    days = set((await db.execute(select(UserPoints.problem_slug).where(
        UserPoints.user_id == user_id, UserPoints.reason == "academy_streak"))).scalars())
    d, n = today_lisbon(), 0
    if d.isoformat() not in days:
        d -= timedelta(days=1)  # ainda dá para manter a sequência hoje
    while d.isoformat() in days:
        n, d = n + 1, d - timedelta(days=1)
    return n


async def overview(db: AsyncSession, user: User) -> dict:
    content = ac.get_content()
    done = await completed_ids(db, user.id)
    states = module_states(content, done)
    earned = await earned_by_module(db, user.id, content)
    mods, finished = [], 0
    for m in content.modules:
        st = states[m.id]
        n, k = st["n"], st["concluidas"]
        finished += 1 if st["estado"] == "done" else 0
        mods.append({
            "id": m.id, "titulo": m.titulo.model_dump(), "descricao": m.descricao.model_dump(), "icone": m.icone, "peca": m.peca,
            "dificuldade": m.dificuldade, "n_secoes": n, "concluidas": k, "pct": round(100 * k / n) if n else 0,
            "pontos_ganhos": earned.get(m.id, 0), "pontos_possiveis": n * section_points(m) + (BADGE_POINTS if n else 0),
            "estado": st["estado"], "motivo": st["motivo"], "em_breve": st["em_breve"],
        })
    total = int((await db.execute(select(func.coalesce(func.sum(UserPoints.points), 0)).where(
        UserPoints.user_id == user.id, UserPoints.reason.in_(REASONS)))).scalar_one())
    return {"modules": mods, "resumo": {"modulos_concluidos": finished, "pontos_academia": total, "sequencia_dias": await streak_days(db, user.id)}, "missao": None}


async def module_view(db: AsyncSession, user: User, module_id: str) -> dict:
    content = ac.get_content()
    m = get_module(content, module_id)
    done = await completed_ids(db, user.id)
    st = module_states(content, done)[m.id]
    secs = section_states(content, m.id, done, st["estado"] != "locked")
    n, k = st["n"], st["concluidas"]
    return {
        "id": m.id, "titulo": m.titulo.model_dump(), "descricao": m.descricao.model_dump(), "icone": m.icone, "peca": m.peca,
        "dificuldade": m.dificuldade, "bloco": m.bloco, "estado": st["estado"], "motivo": st["motivo"], "em_breve": st["em_breve"],
        "n_secoes": n, "concluidas": k, "pct": round(100 * k / n) if n else 0,
        "pontos_ganhos": (await earned_by_module(db, user.id, content)).get(m.id, 0),
        "pontos_possiveis": n * section_points(m) + (BADGE_POINTS if n else 0),
        "secoes": [{"id": s.id, "ordem": s.ordem, "titulo": s.titulo.model_dump(), "estado": secs[s.id], "pontos": section_points(m)}
                   for s in content.by_module.get(m.id, [])],
    }


async def section_view(db: AsyncSession, user: User, section_id: str) -> dict:
    content, sec, module, states, _done = await access(db, user, section_id)
    prog = await ensure_progress(db, user.id, sec.id)
    solved = set((await db.execute(select(AcademyActivityLog.activity_idx).where(
        AcademyActivityLog.user_id == user.id, AcademyActivityLog.section_id == sec.id, AcademyActivityLog.solved_at.is_not(None)))).scalars())
    await db.commit()
    siblings = content.by_module[module.id]
    pos = next(i for i, s in enumerate(siblings) if s.id == sec.id)
    view = section_public(sec, module, states[sec.id], user.id, prog, solved, siblings[pos + 1].id if pos + 1 < len(siblings) else None)
    from app.services import documents  # importação tardia: documents usa o conteúdo da Academia
    view["leitura_doc"] = await documents.reading_for(db, user) if sec.leitura else None
    return view


_recent: dict[int, list[float]] = {}


def rate_limit(user_id: int, limit: int) -> None:
    """Máximo `limit` respostas por minuto e por utilizador (por worker)."""
    import time
    now = time.monotonic()
    hits = [t for t in _recent.get(user_id, []) if now - t < 60]
    if len(hits) >= limit:
        _recent[user_id] = hits
        raise ApiError(429, "academy.rate_limited")
    hits.append(now)
    _recent[user_id] = hits


