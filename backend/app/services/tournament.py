# Lógica do torneio "Formato Aula": preset de 5 rondas + boss com escolha automática de problemas, agências,
# controlo das rondas (iniciar/pausar/prolongar/fechar/terminar), validação das submissões e snapshot do estado.
# O snapshot nunca inclui testes, soluções, respostas nem (para alunos) o código de entrada.
import random
from datetime import timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.errors import ApiError
from app.models._base import utcnow
from app.models.problem import Problem
from app.models.submission import Submission
from app.models.tournament import (
    DEFAULT_CONFIG, Tournament, TournamentHintUse, TournamentPlayer, TournamentRound, TournamentSolve,
    TournamentSubmission, TournamentTeam,
)
from app.models.user import Role, SchoolClass, User
from app.realtime import presence
from app.services import elimination, security, tournament_events as events, tournament_scoring as scoring
from app.services import points as points_svc
from app.services import tournament_anticheat as anticheat
from app.services.problems import ProblemSpec, curriculum

JOIN_KEY = "__tjoin__"
MODES = ("individual", "agencias")
MAX_TEAM = 4
TEAM_COLORS = 8

# idx, título {pt,en}, pontos, multiplicador, duração (s), boss, dificuldades, tipos
_NORMAL = ("programa", "funcao", "bug")
_EASY = _NORMAL + ("quiz", "decomposicao")
PRESET = [
    (1, {"pt": "Fácil", "en": "Easy"}, 10, 1, 600, False, (1, 2), _EASY),
    (2, {"pt": "Fácil-Médio", "en": "Easy-Medium"}, 10, 1, 600, False, (2,), _EASY),
    (3, {"pt": "Médio", "en": "Medium"}, 15, 1, 720, False, (3,), _NORMAL),
    (4, {"pt": "Médio-Difícil", "en": "Medium-Hard"}, 15, 1, 720, False, (3, 4), _NORMAL),
    (5, {"pt": "Difícil", "en": "Hard"}, 15, 2, 900, False, (4, 5), _NORMAL),
    (6, {"pt": "Boss Battle", "en": "Boss Battle"}, 30, 1, 600, True, (1, 2, 3, 4, 5), _NORMAL),
]
MISSIONS_PER_ROUND = 3


# ---------------- escolha automática de problemas ----------------
def _block_priority() -> dict[str, int]:
    """Quanto maior, mais prioritário: o bloco aberto mais alto primeiro; o extra 'mais_alem' fica em último."""
    blocks = [str(b["id"]) for b in curriculum()["blocos"] if b.get("aberto") and str(b["id"]) != "mais_alem"]
    prio = {b: i + 1 for i, b in enumerate(blocks)}
    prio["mais_alem"] = 0
    return prio


async def pick_problems(db: AsyncSession, rng: random.Random | None = None) -> dict[int, list[str]]:
    """{idx da ronda: [slugs]}. Inclui rascunhos (o professor pode usá-los); aprovados desempatam primeiro."""
    rng = rng or random.Random()
    prio = _block_priority()
    rows = (await db.execute(select(Problem.slug, Problem.data, Problem.estado, Problem.bloco, Problem.tipo))).all()
    pool = [r for r in rows if r.bloco in prio]
    used: set[str] = set()
    out: dict[int, list[str]] = {}
    for idx, _title, _pts, _mult, _dur, boss, diffs, tipos in PRESET:
        cands = [
            r for r in pool
            if r.slug not in used and r.tipo in tipos and r.data.get("dificuldade") in diffs
            and (r.data.get("origem") == "boss") == boss
        ]
        if boss and not cands:  # sem problema marcado como boss: o mais difícil dos blocos mais altos
            cands = [r for r in pool if r.slug not in used and r.tipo in _NORMAL and r.data.get("dificuldade") == 5]
        target = {1: 1, 2: 2, 3: 3, 4: 4, 5: 5}.get(idx, 5)  # dificuldade ideal: sobe ronda a ronda
        chosen: list = []
        want = 1 if boss else MISSIONS_PER_ROUND
        while cands and len(chosen) < want:
            seen = {c.tipo for c in chosen}
            best = min(cands, key=lambda r: (-prio[r.bloco], abs(r.data.get("dificuldade", target) - target), r.tipo in seen, r.estado != "aprovado", rng.random()))
            chosen.append(best)
            cands = [c for c in cands if c.slug != best.slug]
        out[idx] = [c.slug for c in chosen]
        used |= {c.slug for c in chosen}
    return out


# ---------------- carregar e verificar acesso ----------------
async def get_tournament(db: AsyncSession, tid: int, *, lock: bool = False) -> Tournament:
    t = await db.get(Tournament, tid, with_for_update=lock)
    if t is None:
        raise ApiError(404, "tournament.not_found")
    return t


async def owned(db: AsyncSession, tid: int, teacher: User, *, lock: bool = False) -> Tournament:
    t = await get_tournament(db, tid, lock=lock)
    if t.teacher_id != teacher.id:
        raise ApiError(404, "tournament.not_found")  # torneio de outro professor = como se não existisse
    return t


async def owned_by_code(db: AsyncSession, code: str, teacher: User) -> Tournament:
    tournament = (await db.execute(select(Tournament).where(
        Tournament.join_code == code, Tournament.teacher_id == teacher.id,
    ))).scalar_one_or_none()
    if tournament is None:
        raise ApiError(404, "tournament.not_found")
    return tournament


async def viewable(db: AsyncSession, tid: int, user: User) -> Tournament:
    """O professor dono, um aluno da turma ou um convidado do próprio torneio."""
    t = await get_tournament(db, tid)
    if user.is_guest:
        if user.guest_tournament_id != t.id:
            raise ApiError(404, "tournament.not_found")
        return t
    if user.role == Role.teacher:
        if t.teacher_id != user.id:
            raise ApiError(404, "tournament.not_found")
    elif user.class_id != t.class_id:
        raise ApiError(404, "tournament.not_found")
    return t


async def rounds_of(db: AsyncSession, tid: int) -> list[TournamentRound]:
    return list((await db.execute(select(TournamentRound).where(TournamentRound.tournament_id == tid).order_by(TournamentRound.idx))).scalars())


async def get_round(db: AsyncSession, tid: int, idx: int, *, lock: bool = False) -> TournamentRound:
    r = (await db.execute(
        select(TournamentRound).where(TournamentRound.tournament_id == tid, TournamentRound.idx == idx).with_for_update(of=TournamentRound) if lock
        else select(TournamentRound).where(TournamentRound.tournament_id == tid, TournamentRound.idx == idx)
    )).scalar_one_or_none()
    if r is None:
        raise ApiError(404, "tournament.round_not_found")
    return r


# ---------------- criar / editar ----------------
async def create(
    db: AsyncSession, teacher: User, class_id: int, name: str, mode: str, fmt: str = "aula",
    group_size: int | None = None, advance: int | None = None, points: dict | None = None,
) -> Tournament:
    cls = await db.get(SchoolClass, class_id)
    if cls is None or cls.teacher_id != teacher.id:
        raise ApiError(404, "tournament.class_not_found")
    config = dict(DEFAULT_CONFIG)
    if fmt == "eliminatoria":
        mode = "individual"
        config.update(group_size=group_size or elimination.DEFAULT_GROUP_SIZE, advance_per_group=advance or elimination.DEFAULT_ADVANCE,
                      points={**points_svc.DEFAULT_POINTS, **(points or {})})
    picks = await pick_problems(db) if fmt == "aula" else {}
    for _ in range(10):
        t = Tournament(class_id=class_id, teacher_id=teacher.id, name=name, mode=mode, format=fmt, join_code=security.random_code(6), config=config)
        try:
            async with db.begin_nested():
                db.add(t)
                await db.flush()
            break
        except IntegrityError:
            continue
    else:
        raise ApiError(500, "common.error")
    if fmt == "eliminatoria":
        await elimination.make_round(db, t, 1)
        await db.commit()
        return t
    for idx, title, pts, mult, dur, boss, _d, _t in PRESET:
        db.add(TournamentRound(
            tournament_id=t.id, idx=idx, title=title, points=pts, multiplier=float(mult), duration_s=dur,
            is_boss=boss, problem_slugs=picks.get(idx, []),
        ))
    await db.commit()
    return t


async def update_round(db: AsyncSession, teacher: User, tid: int, idx: int, data: dict) -> None:
    t = await owned(db, tid, teacher, lock=True)
    rnd = await get_round(db, tid, idx, lock=True)
    if rnd.state != "pending" or t.state == "finished":
        raise ApiError(409, "tournament.round_not_pending")
    if (slugs := data.get("problem_slugs")) is not None:
        if len(set(slugs)) != len(slugs):
            raise ApiError(422, "tournament.duplicate_problem")
        found = {p.slug: p for p in (await db.execute(select(Problem).where(Problem.slug.in_(slugs)))).scalars()} if slugs else {}
        if set(found) != set(slugs):
            raise ApiError(422, "tournament.problem_not_found")
        if t.format == "eliminatoria":
            if len(slugs) != 1 or found[slugs[0]].tipo not in elimination.CODE_TIPOS:
                raise ApiError(422, "tournament.exercise_invalid")
            rnd.edited = True
        rnd.problem_slugs = list(slugs)
    if t.format == "eliminatoria" and (data.get("title") or data.get("duration_s")):
        rnd.edited = True
    for k in ("title", "points", "multiplier", "duration_s"):
        if data.get(k) is not None:
            setattr(rnd, k, data[k])
    await db.commit()


async def random_problems(db: AsyncSession, teacher: User, tid: int, idx: int, rng: random.Random | None = None) -> list[str]:
    """Sugestão aleatória para uma ronda por começar (não grava). Só blocos já dados, sem repetir problemas de outras
    rondas; segue a dificuldade e os tipos próprios da ronda (aprovados e rascunhos, como no sorteio da criação)."""
    rng = rng or random.Random()
    t = await owned(db, tid, teacher)
    rnd = await get_round(db, tid, idx)
    if rnd.state != "pending" or t.state == "finished":
        raise ApiError(409, "tournament.round_not_pending")
    used = {s for r in await rounds_of(db, tid) if r.idx != idx for s in r.problem_slugs}
    prio = _block_priority()
    rows = [r for r in (await db.execute(select(Problem.slug, Problem.data, Problem.estado, Problem.bloco, Problem.tipo))).all()
            if r.bloco in prio and r.slug not in used]
    if t.format == "eliminatoria":
        diffs, tipos, want = elimination.DIFFS.get(rnd.difficulty or "easy", (1, 2)), elimination.CODE_TIPOS, 1
    else:
        preset = next((p for p in PRESET if p[0] == idx), PRESET[-1])
        diffs, tipos, want = preset[6], preset[7], 1 if rnd.is_boss else MISSIONS_PER_ROUND
    def pool(allowed):
        cands = [r for r in allowed if r.tipo in tipos and r.data.get("dificuldade") in diffs]
        if len(cands) < want:  # poucos com esta dificuldade: alarga a todas, mantendo os tipos
            cands += [r for r in allowed if r.tipo in tipos and r not in cands]
        return cands
    # Primeiro só a matéria das aulas; a Arena de Algoritmia ("mais_alem") só entra se não houver mais nada
    cands = pool([r for r in rows if prio[r.bloco] > 0])
    if len(cands) < want:
        cands = pool(rows)
    return [r.slug for r in rng.sample(cands, min(want, len(cands)))]


# ---------------- vistas ----------------
def _remaining(r: TournamentRound, now) -> int | None:
    if r.state == "active" and r.ends_at:
        return max(0, int((r.ends_at - now).total_seconds()))
    if r.state == "paused":
        return r.remaining_s
    return 0 if r.state == "closed" else None


def round_view(r: TournamentRound, now) -> dict:
    return {
        "idx": r.idx, "title": r.title, "points": r.points, "multiplier": r.multiplier, "is_boss": r.is_boss, "state": r.state,
        "ends_at": r.ends_at.isoformat() if r.ends_at and r.state in ("active", "closed") else None,
        "remaining_s": _remaining(r, now), "mission_count": len(r.problem_slugs), "duration_s": r.duration_s,
    }


async def teams_view(db: AsyncSession, t: Tournament) -> list[dict]:
    if t.mode != "agencias":
        return []
    teams = (await db.execute(select(TournamentTeam).where(TournamentTeam.tournament_id == t.id).order_by(TournamentTeam.id))).scalars().all()
    members = (await db.execute(
        select(TournamentPlayer.team_id, User.id, User.display_name).join(User, User.id == TournamentPlayer.user_id)
        .where(TournamentPlayer.tournament_id == t.id, TournamentPlayer.team_id.is_not(None)).order_by(TournamentPlayer.joined_at)
    )).all()
    by_team: dict[int, list] = {}
    for team_id, uid, name in members:
        by_team.setdefault(team_id, []).append({"user_id": uid, "display_name": name})
    return [{"id": tm.id, "name": tm.name, "color_idx": tm.color_idx, "members": by_team.get(tm.id, [])} for tm in teams]


async def missions_view(db: AsyncSession, t: Tournament, rnd: TournamentRound, user: User, teacher: bool) -> list[dict]:
    """Vista pública dos problemas da ronda (sem testes/soluções/respostas) + estado do próprio participante."""
    problems = {p.slug: p for p in (await db.execute(select(Problem).where(Problem.slug.in_(rnd.problem_slugs)))).scalars()} if rnd.problem_slugs else {}
    who = None if teacher else await scoring.participant_for(db, t, user.id)
    solved: set[str] = set()
    hints: dict[str, set[int]] = {}
    if who:
        key, _name, members = who
        solved = set((await db.execute(select(TournamentSolve.problem_slug).where(TournamentSolve.round_id == rnd.id, TournamentSolve.participant_key == key))).scalars())
        for slug, n in (await db.execute(select(TournamentHintUse.problem_slug, TournamentHintUse.n).where(
            TournamentHintUse.round_id == rnd.id, TournamentHintUse.user_id.in_(members)))).all():
            hints.setdefault(slug, set()).add(n)
    out = []
    for slug in rnd.problem_slugs:
        p = problems.get(slug)
        if p is None:
            continue
        view = ProblemSpec.model_validate(p.data).public()
        view.update({"slug": slug, "solved_by_me": slug in solved, "hints_opened": len(hints.get(slug, ()))})
        out.append(view)
    return out


async def snapshot(db: AsyncSession, t: Tournament, user: User) -> dict:
    """Estado completo para alunos, projetor e professor. Lê o last_seq ANTES do resto: se algo mudar
    durante a leitura, o replay a partir desse seq repõe-no (os eventos são idempotentes no cliente)."""
    teacher = user.role == Role.teacher
    if t.format == "eliminatoria":
        return await elimination.build_snapshot(db, t, user, teacher)
    seq = await events.last_seq(db, t.id)
    now = utcnow()
    rounds = await rounds_of(db, t.id)
    current = None
    if t.current_round is not None:
        rnd = next((r for r in rounds if r.idx == t.current_round), None)
        if rnd is not None:
            visible = rnd.state in ("active", "paused", "closed")
            current = {"idx": rnd.idx, "missions": await missions_view(db, t, rnd, user, teacher) if visible else []}
    who = None if teacher else await scoring.participant_for(db, t, user.id)
    player = None if teacher else await db.get(TournamentPlayer, (t.id, user.id))
    board = await scoring.compute_leaderboard(db, t)
    players_count = (await db.execute(select(func.count()).select_from(TournamentPlayer).where(TournamentPlayer.tournament_id == t.id))).scalar_one()
    tour = {"players_count": players_count, "id": t.id, "name": t.name, "mode": t.mode, "format": t.format, "state": t.state, "current_round": t.current_round, "config": t.config}
    if teacher:
        tour["join_code"] = t.join_code  # só o professor
        tour["class_id"] = t.class_id
        tour["incidents_pending"] = await anticheat.pending_count(db, t.id)
    return {
        "tournament": tour, "server_now": now.isoformat(), "last_seq": seq,
        "rounds": [round_view(r, now) for r in rounds], "current": current,
        "players_count": players_count,
        "me": {"user_id": user.id, "team_id": player.team_id if player else None, "participant_key": who[0] if who else None,
               "anticheat": None if teacher else await anticheat.me_view(db, t, user.id)},
        "teams": await teams_view(db, t), "leaderboard": board,
        "podium": scoring.podium_of(board) if t.state == "finished" else None,
    }


async def admin_view(db: AsyncSession, t: Tournament, teacher: User) -> dict:
    """Snapshot + dados só do professor: problemas de cada ronda, presença e submissões por missão."""
    view = await snapshot(db, t, teacher)
    rounds = await rounds_of(db, t.id)
    slugs = {s for r in rounds for s in r.problem_slugs}
    meta = {p.slug: p for p in (await db.execute(select(Problem).where(Problem.slug.in_(slugs)))).scalars()} if slugs else {}
    for rv, r in zip(view["rounds"], rounds):
        rv["problem_slugs"] = list(r.problem_slugs)
        rv["problems"] = [{
            "slug": s, "titulo": meta[s].data["titulo"], "tipo": meta[s].tipo, "bloco": meta[s].bloco,
            "dificuldade": meta[s].data["dificuldade"], "estado": meta[s].estado,
        } for s in r.problem_slugs if s in meta]
    pres = await presence.snapshot(db, t.id)
    players = (await db.execute(
        select(TournamentPlayer, User.display_name).join(User, User.id == TournamentPlayer.user_id)
        .where(TournamentPlayer.tournament_id == t.id).order_by(User.display_name)
    )).all()
    view["players"] = [{
        "user_id": p.user_id, "display_name": name, "team_id": p.team_id,
        "online": pres.get(p.user_id, {}).get("online", False), "last_seen": pres.get(p.user_id, {}).get("last_seen"),
    } for p, name in players]
    view["incidents"] = await anticheat.admin_view(db, t.id)
    attempts = {(rid, slug): n for rid, slug, n in (await db.execute(
        select(TournamentSubmission.round_id, Submission.problem_slug, func.count())
        .join(Submission, Submission.id == TournamentSubmission.submission_id).where(TournamentSubmission.tournament_id == t.id)
        .group_by(TournamentSubmission.round_id, Submission.problem_slug))).all()}
    solves = {(rid, slug): n for rid, slug, n in (await db.execute(
        select(TournamentSolve.round_id, TournamentSolve.problem_slug, func.count()).where(TournamentSolve.tournament_id == t.id)
        .group_by(TournamentSolve.round_id, TournamentSolve.problem_slug))).all()}
    if t.format == "eliminatoria":
        await elimination.admin_extras(db, t, view)
        return view
    view["missions_stats"] = [
        {"round_idx": r.idx, "slug": s, "submissions": attempts.get((r.id, s), 0), "solved": solves.get((r.id, s), 0)}
        for r in rounds for s in r.problem_slugs
    ]
    return view


async def list_for(db: AsyncSession, user: User, class_id: int | None) -> list[dict]:
    if user.role == Role.teacher:
        q = select(Tournament).where(Tournament.teacher_id == user.id)
        if class_id is not None:
            q = q.where(Tournament.class_id == class_id)
    else:  # aluno: só os torneios da sua turma em que já entrou (para retomar sem o código)
        q = select(Tournament).join(TournamentPlayer, TournamentPlayer.tournament_id == Tournament.id).where(
            TournamentPlayer.user_id == user.id, Tournament.class_id == user.class_id)
    rows = (await db.execute(q.order_by(Tournament.id.desc()))).scalars()
    return [{
        "id": t.id, "name": t.name, "mode": t.mode, "format": t.format, "state": t.state, "class_id": t.class_id, "current_round": t.current_round,
        "created_at": t.created_at.isoformat(), **({"join_code": t.join_code} if user.role == Role.teacher else {}),
    } for t in rows]


# ---------------- alunos: entrar e agências ----------------
async def join(db: AsyncSession, user: User, code: str, ip: str = "unknown") -> int:
    if await security.recent_failures(db, JOIN_KEY, ip) >= settings.join_max_failures:
        raise ApiError(429, "tournament.too_many_attempts")
    t = (await db.execute(select(Tournament).where(Tournament.join_code == code.strip().upper()[:12]))).scalar_one_or_none()
    allowed = t is not None and (
        user.guest_tournament_id == t.id if user.is_guest else user.class_id == t.class_id
    )
    if not allowed:
        await security.record_failure(db, JOIN_KEY, ip)  # uma turma partilha o IP: o limite é largo (30 por 15 min)
        raise ApiError(404, "tournament.not_found")
    if t.state == "finished":
        raise ApiError(409, "tournament.finished")
    await _ensure_player(db, t, user)
    await db.commit()
    return t.id


async def _ensure_player(db: AsyncSession, t: Tournament, user: User) -> None:
    """Idempotente: só o primeiro pedido cria a linha e emite player_joined."""
    inserted = (await db.execute(
        insert(TournamentPlayer).values(tournament_id=t.id, user_id=user.id, joined_at=utcnow())
        .on_conflict_do_nothing().returning(TournamentPlayer.user_id)
    )).scalar_one_or_none()
    if inserted is not None:
        count = (await db.execute(select(func.count()).select_from(TournamentPlayer).where(TournamentPlayer.tournament_id == t.id))).scalar_one()
        await events.emit(db, t.id, "player_joined", {"user_id": user.id, "display_name": user.display_name, "players_count": count})


async def _team_op_guard(db: AsyncSession, tid: int, user: User) -> Tournament:
    t = await get_tournament(db, tid, lock=True)  # serializa as operações de agências deste torneio
    if not (user.is_guest and user.guest_tournament_id == t.id) and user.class_id != t.class_id:
        raise ApiError(404, "tournament.not_found")
    if t.mode != "agencias":
        raise ApiError(409, "tournament.not_agencies")
    if t.state == "finished":
        raise ApiError(409, "tournament.finished")
    return t


async def _check_unlocked(db: AsyncSession, t: Tournament, player: TournamentPlayer | None, target_team_id: int | None = None) -> None:
    """Só a primeira atribuição é livre: depois de a agência ter pontos, o aluno não a pode trocar (o professor pode)."""
    if player is None or player.team_id is None or player.team_id == target_team_id:
        return
    key = f"t:{player.team_id}"
    n = (await db.execute(select(func.count()).select_from(TournamentSolve).where(TournamentSolve.tournament_id == t.id, TournamentSolve.participant_key == key))).scalar_one()
    if n:
        raise ApiError(409, "tournament.team_locked")


async def _member_count(db: AsyncSession, team_id: int) -> int:
    return (await db.execute(select(func.count()).select_from(TournamentPlayer).where(TournamentPlayer.team_id == team_id))).scalar_one()


async def _drop_if_empty(db: AsyncSession, t: Tournament, team_id: int | None) -> None:
    """No lobby uma agência vazia desaparece; mais tarde fica (os pontos dela mantêm-se)."""
    if team_id is not None and t.state == "lobby" and await _member_count(db, team_id) == 0:
        await db.execute(delete(TournamentTeam).where(TournamentTeam.id == team_id))


async def create_team(db: AsyncSession, user: User, tid: int, name: str) -> list[dict]:
    t = await _team_op_guard(db, tid, user)
    name = " ".join(name.split())
    if not 1 <= len(name) <= 24:
        raise ApiError(422, "tournament.team_name_invalid")
    taken = (await db.execute(select(func.count()).select_from(TournamentTeam).where(
        TournamentTeam.tournament_id == tid, func.lower(TournamentTeam.name) == name.lower()))).scalar_one()
    if taken:
        raise ApiError(409, "tournament.team_name_taken")
    await _ensure_player(db, t, user)
    await _check_unlocked(db, t, await db.get(TournamentPlayer, (tid, user.id)))
    used = set((await db.execute(select(TournamentTeam.color_idx).where(TournamentTeam.tournament_id == tid))).scalars())
    count = (await db.execute(select(func.count()).select_from(TournamentTeam).where(TournamentTeam.tournament_id == tid))).scalar_one()
    color = next((i for i in range(TEAM_COLORS) if i not in used), count % TEAM_COLORS)
    team = TournamentTeam(tournament_id=tid, name=name, color_idx=color)
    try:
        async with db.begin_nested():
            db.add(team)
            await db.flush()
    except IntegrityError:
        raise ApiError(409, "tournament.team_name_taken") from None
    player = await db.get(TournamentPlayer, (tid, user.id))
    old, player.team_id = player.team_id, team.id
    await db.flush()
    await _drop_if_empty(db, t, old)
    teams = await teams_view(db, t)
    await events.emit(db, tid, "team_updated", {"teams": teams})
    await db.commit()
    return teams


async def _enter_team(db: AsyncSession, t: Tournament, player: TournamentPlayer, team_id: int) -> list[dict]:
    team = await db.get(TournamentTeam, team_id)
    if team is None or team.tournament_id != t.id:
        raise ApiError(404, "tournament.team_not_found")
    if player.team_id != team.id:
        if await _member_count(db, team.id) >= MAX_TEAM:
            raise ApiError(409, "tournament.team_full")
        old, player.team_id = player.team_id, team.id
        await db.flush()
        await _drop_if_empty(db, t, old)
    teams = await teams_view(db, t)
    await events.emit(db, t.id, "team_updated", {"teams": teams})
    await db.commit()
    return teams


async def join_team(db: AsyncSession, user: User, tid: int, team_id: int) -> list[dict]:
    t = await _team_op_guard(db, tid, user)
    await _ensure_player(db, t, user)
    player = await db.get(TournamentPlayer, (tid, user.id))
    await _check_unlocked(db, t, player, team_id)
    return await _enter_team(db, t, player, team_id)


async def move_player(db: AsyncSession, teacher: User, tid: int, team_id: int, user_id: int) -> list[dict]:
    t = await owned(db, tid, teacher, lock=True)
    if t.mode != "agencias":
        raise ApiError(409, "tournament.not_agencies")
    if t.state == "finished":
        raise ApiError(409, "tournament.finished")
    player = await db.get(TournamentPlayer, (tid, user_id))
    if player is None:
        raise ApiError(404, "tournament.player_not_found")
    return await _enter_team(db, t, player, team_id)


# ---------------- controlo das rondas (professor) ----------------
async def start_round(db: AsyncSession, teacher: User, tid: int, idx: int) -> Tournament:
    if (await owned(db, tid, teacher)).format == "eliminatoria":
        return await elimination.start_next(db, teacher, tid, idx)
    t = await owned(db, tid, teacher, lock=True)
    rnd = await get_round(db, tid, idx, lock=True)
    if t.state == "finished":
        raise ApiError(409, "tournament.finished")
    if t.state in ("round_active", "round_paused"):
        raise ApiError(409, "tournament.round_in_progress")
    if rnd.state != "pending":
        raise ApiError(409, "tournament.round_not_pending")
    if not rnd.problem_slugs:
        raise ApiError(409, "tournament.round_empty")
    now = utcnow()
    rnd.state, rnd.started_at, rnd.ends_at, rnd.remaining_s = "active", now, now + timedelta(seconds=rnd.duration_s), None
    t.state, t.current_round = "round_active", idx
    await db.flush()
    await events.emit(db, tid, "round_started", {"idx": idx, "ends_at": rnd.ends_at.isoformat(), "server_now": now.isoformat()})
    await scoring.emit_leaderboard_now(db, t)  # novo ponto de comparação para as setas ▲▼
    await db.commit()
    return t


async def _running_round(db: AsyncSession, tid: int, idx: int, states: tuple[str, ...]) -> TournamentRound:
    rnd = await get_round(db, tid, idx, lock=True)
    if rnd.state not in states:
        raise ApiError(409, "tournament.round_not_active")
    return rnd


async def pause_round(db: AsyncSession, teacher: User, tid: int, idx: int) -> Tournament:
    t = await owned(db, tid, teacher, lock=True)
    rnd = await _running_round(db, tid, idx, ("active",))
    now = utcnow()
    rnd.remaining_s = max(0, int((rnd.ends_at - now).total_seconds()))
    rnd.state, t.state = "paused", "round_paused"
    await db.flush()
    await events.emit(db, tid, "round_paused", {"idx": idx, "remaining_s": rnd.remaining_s})
    await db.commit()
    return t


async def resume_round(db: AsyncSession, teacher: User, tid: int, idx: int) -> Tournament:
    t = await owned(db, tid, teacher, lock=True)
    rnd = await _running_round(db, tid, idx, ("paused",))
    now = utcnow()
    rnd.ends_at, rnd.remaining_s = now + timedelta(seconds=rnd.remaining_s or 0), None
    rnd.state, t.state = "active", "round_active"
    await db.flush()
    await events.emit(db, tid, "round_resumed", {"idx": idx, "ends_at": rnd.ends_at.isoformat(), "server_now": now.isoformat()})
    await db.commit()
    return t


async def extend_round(db: AsyncSession, teacher: User, tid: int, idx: int, seconds: int) -> Tournament:
    t = await owned(db, tid, teacher, lock=True)
    rnd = await _running_round(db, tid, idx, ("active", "paused"))
    if rnd.state == "active":
        rnd.ends_at = max(rnd.ends_at, utcnow()) + timedelta(seconds=seconds)
        payload = {"idx": idx, "ends_at": rnd.ends_at.isoformat()}
    else:
        rnd.remaining_s = (rnd.remaining_s or 0) + seconds
        payload = {"idx": idx, "ends_at": None, "remaining_s": rnd.remaining_s}
    await db.flush()
    await events.emit(db, tid, "round_extended", payload)
    await db.commit()
    return t


async def _close(db: AsyncSession, t: Tournament, rnd: TournamentRound) -> None:
    now = utcnow()
    # o fim passa a ser agora (se for mais cedo): a tolerância de rede conta a partir daqui
    rnd.ends_at = min(rnd.ends_at, now) if rnd.ends_at else now
    rnd.state, rnd.remaining_s = "closed", None
    t.state = "between_rounds"
    await db.flush()
    await events.emit(db, t.id, "round_closed", {"idx": rnd.idx})


async def close_round(db: AsyncSession, teacher: User, tid: int, idx: int) -> Tournament:
    if (await owned(db, tid, teacher)).format == "eliminatoria":
        return await elimination.close_round(db, teacher, tid, idx)
    t = await owned(db, tid, teacher, lock=True)
    rnd = await _running_round(db, tid, idx, ("active", "paused"))
    await _close(db, t, rnd)
    await scoring.emit_leaderboard_now(db, t)
    await db.commit()
    return t


async def finish(db: AsyncSession, teacher: User, tid: int) -> Tournament:
    t = await owned(db, tid, teacher, lock=True)
    if t.state == "finished":
        raise ApiError(409, "tournament.finished")
    if t.format == "eliminatoria":
        await elimination.finish(db, t)
        await db.commit()
        return t
    if t.state in ("round_active", "round_paused") and t.current_round is not None:
        await _close(db, t, await get_round(db, tid, t.current_round, lock=True))
    t.state = "finished"
    await db.flush()
    board = await scoring.compute_leaderboard(db, t)
    await scoring.emit_leaderboard_now(db, t)
    await events.emit(db, tid, "tournament_finished", {"podium": scoring.podium_of(board)})
    await db.commit()
    return t


# ---------------- submissões e pistas ----------------
async def validate_submission(db: AsyncSession, user: User, tid: int, round_idx: int, slug: str) -> tuple[Tournament, TournamentRound]:
    """Regras do servidor para uma submissão de torneio. Devolve (torneio, ronda) ou levanta ApiError."""
    t = await get_tournament(db, tid)
    if user.role == Role.teacher or (not (user.is_guest and user.guest_tournament_id == t.id) and user.class_id != t.class_id):
        raise ApiError(404, "tournament.not_found")
    if await db.get(TournamentPlayer, (tid, user.id)) is None:
        raise ApiError(403, "tournament.not_participant")
    if t.mode == "agencias" and (await scoring.participant_for(db, t, user.id)) is None:
        raise ApiError(403, "tournament.team_required")
    if await anticheat.is_locked(db, tid, user.id):
        raise ApiError(403, "tournament.locked")
    if t.state == "finished":
        raise ApiError(409, "tournament.finished")
    rnd = await get_round(db, tid, round_idx)
    if rnd.state == "paused":
        raise ApiError(409, "tournament.round_paused")
    if rnd.state == "pending":
        raise ApiError(409, "tournament.round_not_active")
    grace = timedelta(seconds=t.config.get("grace_s", 30))
    if rnd.ends_at is None or utcnow() > rnd.ends_at + grace:
        raise ApiError(409, "tournament.time_over")
    if slug not in rnd.problem_slugs:
        raise ApiError(422, "tournament.problem_not_in_round")
    return t, rnd


async def link_submission(db: AsyncSession, sub: Submission, t: Tournament, rnd: TournamentRound) -> None:
    await db.execute(
        insert(TournamentSubmission).values(submission_id=sub.id, tournament_id=t.id, round_id=rnd.id, received_at=utcnow())
        .on_conflict_do_nothing()
    )
    await db.commit()


async def open_hint(db: AsyncSession, user: User, tid: int, slug: str, n: int) -> dict:
    t = await get_tournament(db, tid)
    if user.role == Role.teacher or (not (user.is_guest and user.guest_tournament_id == t.id) and user.class_id != t.class_id):
        raise ApiError(404, "tournament.not_found")
    if await db.get(TournamentPlayer, (tid, user.id)) is None:
        raise ApiError(403, "tournament.not_participant")
    if await anticheat.is_locked(db, tid, user.id):
        raise ApiError(403, "tournament.locked")
    if t.current_round is None:
        raise ApiError(409, "tournament.round_not_active")
    rnd = await get_round(db, tid, t.current_round)
    if rnd.state != "active":
        raise ApiError(409, "tournament.round_not_active")
    if slug not in rnd.problem_slugs:
        raise ApiError(422, "tournament.problem_not_in_round")
    problem = await db.get(Problem, slug)
    pistas = (problem.data.get("pistas") or []) if problem else []
    if not 1 <= n <= len(pistas):
        raise ApiError(404, "tournament.hint_not_found")
    await db.execute(insert(TournamentHintUse).values(round_id=rnd.id, problem_slug=slug, user_id=user.id, n=n).on_conflict_do_nothing())
    await db.commit()
    return {"n": n, "text": pistas[n - 1]}
