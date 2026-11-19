# Formato "Eliminatória" (individual): em cada ronda os jogadores em jogo são distribuídos por grupos equilibrados,
# há um exercício por ronda (dificuldade a subir) e o primeiro a ter uma submissão aceite ganha o grupo.
# Fim da ronda: todos os grupos decididos ou tempo + tolerância (fecho automático, um só worker age).
# Sem aceites: mais testes passados, depois mais cedo, depois sorteio. Eliminados continuam a treinar (só pontos).
import asyncio
import logging
import math
import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import SessionLocal
from app.errors import ApiError
from app.models._base import utcnow
from app.models.problem import Problem
from app.models.submission import Submission
from app.models.tournament import (
    Tournament, TournamentGroup, TournamentHintUse, TournamentPlayer, TournamentRound, TournamentSubmission,
)
from app.models.points import UserPoints
from app.models.user import Role, User
from app.services import points as pts
from app.services.leaderboard import avatar_seed
from app.services import tournament_anticheat as anticheat
from app.services import tournament_events as events
from app.services.problems import ProblemSpec

log = logging.getLogger("pyarena.elimination")
CODE_TIPOS = ("programa", "funcao", "bug")
DIFFS = {"easy": (1, 2), "medium": (3,), "hard": (4, 5)}
DURATIONS = {"easy": 480, "medium": 600, "hard": 720}
DEFAULT_GROUP_SIZE, DEFAULT_ADVANCE = 4, 1
FLUSH_WAIT_S = 60  # espera máxima, depois do fim, por submissões ainda em correção


# ---------------- planeamento (funções puras) ----------------
def group_sizes(n: int, group_size: int) -> list[int]:
    """n jogadores em ceil(n/group_size) grupos cujos tamanhos diferem no máximo 1 (maiores primeiro)."""
    k = math.ceil(n / group_size)
    base, extra = divmod(n, k)
    return [base + 1] * extra + [base] * (k - extra)


def is_final_for(alive: int, group_size: int) -> bool:
    return alive <= group_size + 1


def adv_eff(size: int, advance: int, final: bool) -> int:
    """Quantos passam num grupo: sempre pelo menos 1 fica de fora; na final só o vencedor."""
    return 1 if final else max(1, min(advance, size - 1))


def plan_bracket(n: int, group_size: int, advance: int) -> list[dict]:
    rounds, idx = [], 1
    while n >= 2:
        final = is_final_for(n, group_size)
        sizes = [n] if final else group_sizes(n, group_size)
        advancing = 1 if final else sum(adv_eff(s, advance, False) for s in sizes)
        rounds.append({"idx": idx, "groups": len(sizes), "sizes": sizes, "advancing": advancing, "is_final": final})
        if final:
            break
        n, idx = advancing, idx + 1
    return rounds


def difficulty_for(idx: int, final: bool) -> str:
    return "hard" if final else ("easy", "medium")[idx - 1] if idx <= 2 else "hard"


def draw_groups(players: list[int], sizes: list[int], previous_pairs: set[frozenset], rng: random.Random, tries: int = 300) -> list[list[int]]:
    """Sorteia os grupos, evitando repetir adversários da ronda anterior sempre que possível."""
    best, best_cost = None, None
    for _ in range(tries):
        order = players[:]
        rng.shuffle(order)
        groups, i = [], 0
        for s in sizes:
            groups.append(order[i:i + s])
            i += s
        cost = sum(1 for g in groups for a in range(len(g)) for b in range(a + 1, len(g)) if frozenset((g[a], g[b])) in previous_pairs)
        if best is None or cost < best_cost:
            best, best_cost = groups, cost
            if cost == 0:
                break
    return best


# ---------------- exercícios ----------------
async def pick_exercise(db: AsyncSession, difficulty: str, final: bool, exclude: set[str], rng: random.Random | None = None) -> str | None:
    from app.services.tournament import _block_priority
    rng = rng or random.Random()
    prio = _block_priority()
    rows = (await db.execute(select(Problem.slug, Problem.data, Problem.estado, Problem.bloco, Problem.tipo))).all()
    cands = [r for r in rows if r.bloco in prio and r.tipo in CODE_TIPOS and r.slug not in exclude and r.data.get("dificuldade") in DIFFS[difficulty]]
    if final:  # final: um boss se houver, senão ★4–★5
        boss = [r for r in cands if r.data.get("origem") == "boss"]
        cands = boss or cands
    else:
        cands = [r for r in cands if r.data.get("origem") != "boss"] or cands
    if not cands:
        return None
    return min(cands, key=lambda r: (-prio[r.bloco], r.estado != "aprovado", rng.random())).slug


def round_title(idx: int, final: bool) -> dict:
    return {"pt": "Final", "en": "Final"} if final else {"pt": f"Ronda {idx}", "en": f"Round {idx}"}


async def make_round(db: AsyncSession, t: Tournament, idx: int, alive: int | None = None) -> TournamentRound:
    final = alive is not None and is_final_for(alive, t.config["group_size"])
    diff = difficulty_for(idx, final)
    used = {s for ss in (await db.execute(select(TournamentRound.problem_slugs).where(TournamentRound.tournament_id == t.id))).scalars() for s in ss}
    slug = await pick_exercise(db, diff, final, used)
    r = TournamentRound(
        tournament_id=t.id, idx=idx, title=round_title(idx, final), points=0, multiplier=1.0, duration_s=DURATIONS[diff],
        is_boss=False, is_final=final, difficulty=diff, problem_slugs=[slug] if slug else [],
    )
    db.add(r)
    await db.flush()
    return r


# ---------------- leitura ----------------
async def alive_ids(db: AsyncSession, tid: int) -> list[int]:
    return list((await db.execute(select(TournamentPlayer.user_id).where(TournamentPlayer.tournament_id == tid, TournamentPlayer.status == "alive"))).scalars())


async def load_progress(db: AsyncSession, tid: int) -> dict[tuple[int, int], dict]:
    """(round_id, user_id) -> {passed, total, attempts, solved_at, best_at}. Nunca devolve código."""
    rows = (await db.execute(
        select(TournamentSubmission.round_id, Submission.user_id, Submission.status, Submission.passed, Submission.total, Submission.created_at, Submission.finished_at)
        .join(Submission, Submission.id == TournamentSubmission.submission_id).where(TournamentSubmission.tournament_id == tid)
        .order_by(Submission.created_at)
    )).all()
    out: dict[tuple[int, int], dict] = {}
    for rid, uid, status, passed, total, created, finished in rows:
        p = out.setdefault((rid, uid), {"passed": 0, "total": None, "attempts": 0, "solved_at": None, "best_at": None})
        p["attempts"] += 1
        if passed is not None and (passed > p["passed"] or p["best_at"] is None):
            p["passed"], p["total"], p["best_at"] = passed, total, created
        if status == "accepted" and p["solved_at"] is None:
            p["solved_at"] = finished or created
    return out


def group_view(g: TournamentGroup, names: dict[int, str], prog: dict, with_progress: bool = True) -> dict:
    members = []
    for uid in g.members:
        p = prog.get((g.round_id, uid), {}) if with_progress else {}
        members.append({
            "user_id": uid, "display_name": names.get(uid, "?"), "avatar_seed": avatar_seed(uid), "passed": p.get("passed", 0), "total": p.get("total"),
            "attempts": p.get("attempts", 0), "solved_at": p["solved_at"].isoformat() if p.get("solved_at") else None,
            "status": "winner" if uid in g.winners else ("out" if g.decided else "playing"),
        })
    return {"id": g.id, "members": members, "decided": g.decided, "winners": list(g.winners), "decided_by": g.decided_by}


async def _names(db: AsyncSession, ids) -> dict[int, str]:
    ids = list(set(ids))
    return dict((await db.execute(select(User.id, User.display_name).where(User.id.in_(ids)))).all()) if ids else {}


async def my_points(db: AsyncSession, tid: int, uid: int) -> int:
    return int((await db.execute(select(func.coalesce(func.sum(UserPoints.points), 0)).where(UserPoints.tournament_id == tid, UserPoints.user_id == uid))).scalar_one())


async def tournament_points(db: AsyncSession, tid: int) -> dict[int, int]:
    return {u: int(p) for u, p in (await db.execute(
        select(UserPoints.user_id, func.sum(UserPoints.points)).where(UserPoints.tournament_id == tid).group_by(UserPoints.user_id)))}


async def podium(db: AsyncSession, t: Tournament) -> list[dict] | None:
    final = (await db.execute(select(TournamentRound).where(TournamentRound.tournament_id == t.id, TournamentRound.is_final, TournamentRound.state == "closed"))).scalar_one_or_none()
    if final is None:
        return None
    g = (await db.execute(select(TournamentGroup).where(TournamentGroup.round_id == final.id))).scalars().first()
    if g is None or not g.ranking:
        return None
    top = g.ranking[:3]
    names, tp = await _names(db, top), await tournament_points(db, t.id)
    return [{"participant_key": f"u:{u}", "user_id": u, "name": names.get(u, "?"), "avatar_seed": avatar_seed(u), "points": tp.get(u, 0), "rank": i, "color_idx": u % 8} for i, u in enumerate(top, 1)]


async def build_snapshot(db: AsyncSession, t: Tournament, user: User, teacher: bool) -> dict:
    from app.services import tournament as svc
    seq = await events.last_seq(db, t.id)
    now = utcnow()
    rounds = await svc.rounds_of(db, t.id)
    groups = list((await db.execute(select(TournamentGroup).where(TournamentGroup.tournament_id == t.id).order_by(TournamentGroup.round_id, TournamentGroup.idx))).scalars())
    prog = await load_progress(db, t.id)
    players = list((await db.execute(select(TournamentPlayer).where(TournamentPlayer.tournament_id == t.id))).scalars())
    names = await _names(db, [m for g in groups for m in g.members] + [p.user_id for p in players])
    by_round: dict[int, list] = {}
    for g in groups:
        by_round.setdefault(g.round_id, []).append(g)
    rviews = []
    for r in rounds:
        v = svc.round_view(r, now)
        v.update({"title": r.title, "is_final": r.is_final, "difficulty": r.difficulty,
                  "groups": [group_view(g, names, prog) for g in by_round.get(r.id, [])]})
        rviews.append(v)
    me_p = next((p for p in players if p.user_id == user.id), None)
    cur = next((r for r in rounds if r.idx == t.current_round), None)
    my_group = None
    if cur is not None:
        my_group = next((g for g in by_round.get(cur.id, []) if user.id in g.members), None)
    current = None
    if cur is not None:
        visible = cur.state in ("active", "paused", "closed")
        mission = None
        if visible and cur.problem_slugs:
            mission = await _mission_view(db, cur, user, practice=teacher or my_group is None or (me_p is not None and me_p.status != "alive"))
        current = {"idx": cur.idx, "mission": mission, "missions": [mission] if mission else []}
    champion_id = next((p.user_id for p in players if p.status == "champion"), None)
    tp = await tournament_points(db, t.id)
    board = sorted(players, key=lambda p: (-tp.get(p.user_id, 0), names.get(p.user_id, "").lower()))
    leaderboard = [{
        "participant_key": f"u:{p.user_id}", "name": names.get(p.user_id, "?"), "avatar_seed": avatar_seed(p.user_id), "color_idx": p.user_id % 8, "points": tp.get(p.user_id, 0),
        "per_round": [], "solved": 0, "rank": 1 + sum(1 for o in board if tp.get(o.user_id, 0) > tp.get(p.user_id, 0)), "delta_rank": 0,
    } for p in board]
    tour = {"id": t.id, "name": t.name, "mode": t.mode, "format": t.format, "state": t.state, "current_round": t.current_round,
            "config": t.config, "players_count": len(players)}
    if teacher:
        tour["join_code"], tour["class_id"] = t.join_code, t.class_id
        tour["incidents_pending"] = await anticheat.pending_count(db, t.id)
    return {
        "format": "eliminatoria", "tournament": tour, "server_now": now.isoformat(), "last_seq": seq, "config": t.config,
        "players_count": len(players), "alive_count": sum(1 for p in players if p.status != "eliminated"),
        "rounds": rviews, "current": current,
        "me": {
            "user_id": user.id, "status": None if teacher or me_p is None else me_p.status, "group_id": my_group.id if my_group else None,
            "eliminated_in_round": me_p.eliminated_in_round if me_p else None, "team_id": None,
            "participant_key": None if teacher else f"u:{user.id}",
            "anticheat": None if teacher else await anticheat.me_view(db, t, user.id),
        },
        "teams": [], "leaderboard": leaderboard,
        "champion": {"user_id": champion_id, "display_name": names.get(champion_id), "avatar_seed": avatar_seed(champion_id)} if champion_id else None,
        "podium": await podium(db, t), "my_points_this_tournament": 0 if teacher else await my_points(db, t.id, user.id),
    }


async def _mission_view(db: AsyncSession, rnd: TournamentRound, user: User, practice: bool) -> dict | None:
    slug = rnd.problem_slugs[0]
    p = await db.get(Problem, slug)
    if p is None:
        return None
    view = ProblemSpec.model_validate(p.data).public()
    solved = (await db.execute(
        select(func.count()).select_from(TournamentSubmission).join(Submission, Submission.id == TournamentSubmission.submission_id)
        .where(TournamentSubmission.round_id == rnd.id, Submission.user_id == user.id, Submission.status == "accepted"))).scalar_one() > 0
    hints = (await db.execute(select(func.count()).select_from(TournamentHintUse).where(TournamentHintUse.round_id == rnd.id, TournamentHintUse.user_id == user.id))).scalar_one()
    view.update({"slug": slug, "solved_by_me": solved, "hints_opened": hints, "practice": practice})
    return view


async def admin_extras(db: AsyncSession, t: Tournament, view: dict) -> None:
    pl = {p.user_id: p for p in (await db.execute(select(TournamentPlayer).where(TournamentPlayer.tournament_id == t.id))).scalars()}
    for p in view["players"]:
        p["status"] = pl[p["user_id"]].status if p["user_id"] in pl else None
    view["bracket_preview"] = bracket_preview(len([p for p in pl.values() if p.status != "eliminated"]), t.config)
    view["missions_stats"] = []


def bracket_preview(n: int, config: dict, group_size: int | None = None, advance: int | None = None) -> dict:
    gs, adv = group_size or config.get("group_size", DEFAULT_GROUP_SIZE), advance or config.get("advance_per_group", DEFAULT_ADVANCE)
    return {"players": n, "rounds": plan_bracket(n, gs, adv)}


# ---------------- progresso agrupado (<= 2 eventos/s por torneio) ----------------
_GATE = text(
    """UPDATE tournaments SET gp_emitted_at = clock_timestamp()
       WHERE id = :id AND (gp_emitted_at IS NULL OR gp_emitted_at <= clock_timestamp() - interval '500 milliseconds') RETURNING id"""
)
_WAIT = text("SELECT extract(epoch from (gp_emitted_at + interval '500 milliseconds' - clock_timestamp())) FROM tournaments WHERE id = :id")
_pending: dict[int, dict] = {}
_workers: dict[int, asyncio.Task] = {}
_tasks: set[asyncio.Task] = set()


def schedule_progress(tid: int, payload: dict) -> None:
    """Guarda só o último estado de cada (grupo, aluno) e emite em lote, no máximo 2 vezes por segundo."""
    _pending.setdefault(tid, {})[(payload["group_id"], payload["user_id"])] = payload
    if tid not in _workers:
        task = asyncio.get_running_loop().create_task(_progress_worker(tid))
        _workers[tid] = task
        _tasks.add(task)
        task.add_done_callback(_tasks.discard)


async def _progress_worker(tid: int) -> None:
    me = asyncio.current_task()
    try:
        while True:
            async with SessionLocal() as db:
                if (await db.execute(_GATE, {"id": tid})).first() is not None:
                    if _workers.get(tid) is me:
                        del _workers[tid]
                    items = list(_pending.pop(tid, {}).values())
                    for it in items:
                        await events.emit(db, tid, "group_progress", it)
                    await db.commit()
                    return
                wait = (await db.execute(_WAIT, {"id": tid})).scalar()
                await db.rollback()
            if wait is None:
                return
            await asyncio.sleep(max(0.02, float(wait)) + 0.01)
    except asyncio.CancelledError:
        raise
    except Exception:  # noqa: BLE001
        log.exception("falha a emitir group_progress de %s", tid)
    finally:
        if _workers.get(tid) is me:
            del _workers[tid]


async def drain() -> None:
    while _tasks:
        await asyncio.gather(*list(_tasks), return_exceptions=True)


async def cancel_all() -> None:
    for t in list(_tasks):
        t.cancel()
    await asyncio.gather(*list(_tasks), return_exceptions=True)
    _workers.clear()
    _pending.clear()


# ---------------- decisão dos grupos ----------------
def _order_rest(candidates: list[int], rnd_id: int, prog: dict, rng: random.Random, tpoints: dict[int, int]) -> tuple[list[int], bool]:
    """Ordem total de quem não ganhou por solve: mais testes passados, depois submissão mais cedo, depois mais pontos
    no torneio e, por fim, sorteio (semente guardada). Quem não submeteu fica no fim, ordenado pelos mesmos critérios."""
    far = datetime.max.replace(tzinfo=timezone.utc)

    def key(u: int):
        p = prog.get((rnd_id, u), {})
        has = p.get("best_at") is not None
        return (-(p.get("passed", 0) if has else 0), p["best_at"] if has else far, -tpoints.get(u, 0), rng.random())

    ordered = sorted(candidates, key=key)
    return ordered, any(prog.get((rnd_id, u), {}).get("best_at") is None for u in candidates)


async def _decide_group(db: AsyncSession, t: Tournament, rnd: TournamentRound, g: TournamentGroup, prog: dict) -> None:
    need = adv_eff(len(g.members), t.config["advance_per_group"], rnd.is_final)
    seed = random.getrandbits(48)
    rng = random.Random(seed)
    others, drew = _order_rest([m for m in g.members if m not in g.winners], rnd.id, prog, rng, await tournament_points(db, t.id))
    ranking = [*g.winners, *others]
    newly = not g.decided
    if newly:
        g.winners = ranking[:need]
        drew_for_winner = drew and len([w for w in ranking[:need] if prog.get((rnd.id, w), {}).get("attempts", 0) == 0]) > 0
        g.decided, g.decided_by = True, ("draw" if drew_for_winner else "tests")
    if drew:
        g.draw_seed = seed
    g.ranking = ranking
    if newly:
        await events.emit(db, t.id, "group_decided", {"idx": rnd.idx, "group_id": g.id, "winners": list(g.winners), "decided_by": g.decided_by})


async def finalize_round(db: AsyncSession, t: Tournament, rnd: TournamentRound, *, create_next: bool = True) -> None:
    """Fecha a ronda: decide os grupos em falta, elimina, dá pontos e prepara a ronda seguinte (ou o campeão).
    Tem de ser chamada com o torneio bloqueado (FOR UPDATE) e com a ronda ainda active/paused: é isso que garante
    que só se faz uma vez, mesmo com vários workers."""
    if rnd.state not in ("active", "paused"):
        return
    await events.lock(db, t.id)
    cfg = pts.config_points(t)
    groups = list((await db.execute(select(TournamentGroup).where(TournamentGroup.round_id == rnd.id).order_by(TournamentGroup.idx))).scalars())
    prog = await load_progress(db, t.id)
    for g in groups:
        await _decide_group(db, t, rnd, g, prog)
    winners = [w for g in groups for w in g.winners]
    losers = [m for g in groups for m in g.members if m not in g.winners]
    if losers:
        await db.execute(text("UPDATE tournament_players SET status='eliminated', eliminated_in_round=:i WHERE tournament_id=:t AND user_id = ANY(:u)"),
                         {"i": rnd.idx, "t": t.id, "u": losers})
        await events.emit(db, t.id, "player_eliminated", {"user_ids": losers, "idx": rnd.idx})
    for w in winners:
        await pts.award(db, t, w, cfg["group_win"], "group_win", rnd.idx)
    now = utcnow()
    rnd.ends_at = min(rnd.ends_at, now) if rnd.ends_at else now
    rnd.state, rnd.remaining_s = "closed", None
    t.state = "between_rounds"
    await db.flush()
    nxt = None
    if rnd.is_final and groups:
        g = groups[0]
        champ = g.winners[0]
        await db.execute(text("UPDATE tournament_players SET status='champion' WHERE tournament_id=:t AND user_id=:u"), {"t": t.id, "u": champ})
        await pts.award(db, t, champ, cfg["champion"], "champion")
        # 2.º e 3.º lugares da final recebem sempre o prémio (menor que o do campeão).
        for place, key in ((1, "second"), (2, "third")):
            if place < len(g.ranking):
                await pts.award(db, t, g.ranking[place], cfg[key], key)
        t.state = "finished"
        names = await _names(db, [champ])
        await events.emit(db, t.id, "round_closed", {"idx": rnd.idx, "next_idx": None})
        await events.emit(db, t.id, "champion", {"user_id": champ, "display_name": names.get(champ), "avatar_seed": avatar_seed(champ)})
        await db.flush()
        await events.emit(db, t.id, "tournament_finished", {"podium": await podium(db, t)})
        return
    if create_next:
        nxt = await make_round(db, t, rnd.idx + 1, len(winners))
    await events.emit(db, t.id, "round_closed", {"idx": rnd.idx, "next_idx": nxt.idx if nxt else None})


# ---------------- início da ronda (professor) ----------------
async def start_next(db: AsyncSession, teacher: User, tid: int, idx: int | None = None) -> Tournament:
    from app.services import tournament as svc
    t = await svc.owned(db, tid, teacher, lock=True)
    if t.format != "eliminatoria":
        raise ApiError(409, "tournament.wrong_format")
    if t.state == "finished":
        raise ApiError(409, "tournament.finished")
    if t.state in ("round_active", "round_paused"):
        raise ApiError(409, "tournament.round_in_progress")
    rounds = await svc.rounds_of(db, tid)
    rnd = next((r for r in rounds if r.state == "pending"), None)
    if rnd is None or (idx is not None and rnd.idx != idx):
        raise ApiError(409, "tournament.round_not_pending")
    alive = await alive_ids(db, tid)
    if len(alive) < 2:
        raise ApiError(409, "tournament.not_enough_players")
    final = is_final_for(len(alive), t.config["group_size"])
    diff = difficulty_for(rnd.idx, final)
    if not rnd.edited and (rnd.is_final != final or rnd.difficulty != diff):  # o número de jogadores mudou: reajusta o exercício
        used = {s for r in rounds if r.id != rnd.id for s in r.problem_slugs}
        slug = await pick_exercise(db, diff, final, used)
        rnd.problem_slugs = [slug] if slug else []
        rnd.duration_s, rnd.difficulty = DURATIONS[diff], diff
    rnd.is_final, rnd.title = final, round_title(rnd.idx, final)
    if not rnd.problem_slugs:
        raise ApiError(409, "tournament.round_empty")
    prev = rounds[rnd.idx - 2] if rnd.idx > 1 else None
    pairs: set[frozenset] = set()
    if prev is not None:
        for g in (await db.execute(select(TournamentGroup).where(TournamentGroup.round_id == prev.id))).scalars():
            pairs |= {frozenset((a, b)) for i, a in enumerate(g.members) for b in g.members[i + 1:]}
    sizes = [len(alive)] if final else group_sizes(len(alive), t.config["group_size"])
    drawn = draw_groups(alive, sizes, pairs, random.Random())
    new = [TournamentGroup(tournament_id=tid, round_id=rnd.id, idx=i, members=m) for i, m in enumerate(drawn, 1)]
    db.add_all(new)
    now = utcnow()
    rnd.state, rnd.started_at, rnd.ends_at, rnd.remaining_s = "active", now, now + timedelta(seconds=rnd.duration_s), None
    t.state, t.current_round = "round_active", rnd.idx
    await db.flush()
    names = await _names(db, alive)
    await events.emit(db, tid, "groups_drawn", {"idx": rnd.idx, "groups": [group_view(g, names, {}, False) for g in new]})
    await events.emit(db, tid, "round_started", {"idx": rnd.idx, "ends_at": rnd.ends_at.isoformat(), "server_now": now.isoformat()})
    await db.commit()
    return t


async def close_round(db: AsyncSession, teacher: User, tid: int, idx: int) -> Tournament:
    from app.services import tournament as svc
    t = await svc.owned(db, tid, teacher, lock=True)
    rnd = await svc.get_round(db, tid, idx, lock=True)
    if rnd.state not in ("active", "paused"):
        raise ApiError(409, "tournament.round_not_active")
    await finalize_round(db, t, rnd)
    await db.commit()
    return t


async def finish(db: AsyncSession, t: Tournament) -> None:
    """Terminar a meio: fecha a ronda em curso sem preparar outra."""
    if t.state in ("round_active", "round_paused") and t.current_round is not None:
        from app.services import tournament as svc
        rnd = await svc.get_round(db, t.id, t.current_round, lock=True)
        await finalize_round(db, t, rnd, create_next=False)
    if t.state != "finished":
        t.state = "finished"
        await db.flush()
        await events.emit(db, t.id, "tournament_finished", {"podium": await podium(db, t)})


async def set_winner(db: AsyncSession, teacher: User, tid: int, gid: int, user_id: int) -> Tournament:
    from app.services import tournament as svc
    t = await svc.owned(db, tid, teacher, lock=True)
    g = await db.get(TournamentGroup, gid)
    if g is None or g.tournament_id != tid:
        raise ApiError(404, "tournament.group_not_found")
    rnd = await db.get(TournamentRound, g.round_id)
    if rnd.state not in ("active", "paused"):
        raise ApiError(409, "tournament.round_not_active")
    if user_id not in g.members:
        raise ApiError(422, "tournament.player_not_in_group")
    await events.lock(db, tid)
    need = adv_eff(len(g.members), t.config["advance_per_group"], rnd.is_final)
    g.winners = [user_id, *[w for w in g.winners if w != user_id]][:need]
    g.decided, g.decided_by = True, "teacher"
    await db.flush()
    await events.emit(db, tid, "group_decided", {"idx": rnd.idx, "group_id": g.id, "winners": list(g.winners), "decided_by": "teacher"})
    await _maybe_close(db, t, rnd)
    await db.commit()
    return t


async def _maybe_close(db: AsyncSession, t: Tournament, rnd: TournamentRound) -> None:
    undecided = (await db.execute(select(func.count()).select_from(TournamentGroup).where(TournamentGroup.round_id == rnd.id, TournamentGroup.decided.is_(False)))).scalar_one()
    if undecided == 0:
        await finalize_round(db, t, rnd)


# ---------------- submissões ----------------
async def handle_finished(db: AsyncSession, link: TournamentSubmission, sub: Submission) -> None:
    """Chamado quando uma submissão de torneio Eliminatória termina de ser corrigida."""
    t = await db.get(Tournament, link.tournament_id, with_for_update=True)  # primeiro o lock da linha, depois o consultivo
    await events.lock(db, t.id)
    rnd = await db.get(TournamentRound, link.round_id)
    player = await db.get(TournamentPlayer, (t.id, sub.user_id))
    if rnd is None or player is None or sub.status in ("queued", "running", "error", "internal_error"):
        await db.rollback()
        return
    cfg = pts.config_points(t)
    await pts.award(db, t, sub.user_id, cfg["participation"], "participation")
    groups = list((await db.execute(select(TournamentGroup).where(TournamentGroup.round_id == rnd.id))).scalars())
    g = next((x for x in groups if sub.user_id in x.members), None)
    if sub.status == "accepted":
        prob = await db.get(Problem, sub.problem_slug)
        stars = prob.data.get("dificuldade", 1) if prob else 1
        await pts.award(db, t, sub.user_id, cfg[pts.difficulty_key(stars)], "exercise", rnd.idx, sub.problem_slug)
        if g is not None and not g.decided and sub.user_id not in g.winners and player.status == "alive":
            g.winners = [*g.winners, sub.user_id]
            if len(g.winners) >= adv_eff(len(g.members), t.config["advance_per_group"], rnd.is_final):
                g.decided, g.decided_by = True, "solve"
                await db.flush()
                await events.emit(db, t.id, "group_decided", {"idx": rnd.idx, "group_id": g.id, "winners": list(g.winners), "decided_by": "solve"})
                await _maybe_close(db, t, rnd)
    progress = None
    if g is not None:
        p = (await load_progress(db, t.id)).get((rnd.id, sub.user_id), {})
        progress = {"idx": rnd.idx, "group_id": g.id, "user_id": sub.user_id, "passed": p.get("passed", 0), "total": p.get("total"), "attempts": p.get("attempts", 0)}
    await db.commit()
    if progress:
        schedule_progress(t.id, progress)


# ---------------- fecho automático ----------------
async def autoclose_once() -> int:
    """Fecha as rondas cujo ends_at + grace_s já passou. Seguro com vários workers: o torneio é bloqueado com
    FOR NO KEY UPDATE SKIP LOCKED (só um consegue) e a ronda é relida já com o lock (se já fechou, não faz nada).
    Não se usa FOR UPDATE porque gravar um evento (FK para o torneio) faria este fecho saltar a ronda nessa volta."""
    now = utcnow()
    async with SessionLocal() as db:
        cands = [r[0] for r in (await db.execute(
            select(TournamentRound.tournament_id).join(Tournament, Tournament.id == TournamentRound.tournament_id)
            .where(Tournament.format == "eliminatoria", TournamentRound.state == "active", TournamentRound.ends_at < now))).all()]
    done = 0
    for tid in cands:
        async with SessionLocal() as db:
            t = (await db.execute(select(Tournament).where(Tournament.id == tid).with_for_update(skip_locked=True, key_share=True))).scalar_one_or_none()
            if t is None or t.current_round is None:
                continue
            rnd = (await db.execute(select(TournamentRound).where(TournamentRound.tournament_id == tid, TournamentRound.idx == t.current_round))).scalar_one()
            grace = timedelta(seconds=t.config.get("grace_s", 30))
            if rnd.state != "active" or rnd.ends_at is None or utcnow() <= rnd.ends_at + grace:
                continue
            pending = (await db.execute(
                select(func.count()).select_from(TournamentSubmission).join(Submission, Submission.id == TournamentSubmission.submission_id)
                .where(TournamentSubmission.round_id == rnd.id, Submission.status.in_(("queued", "running"))))).scalar_one()
            if pending and utcnow() <= rnd.ends_at + grace + timedelta(seconds=FLUSH_WAIT_S):
                continue  # ainda há submissões a serem corrigidas: espera
            await finalize_round(db, t, rnd)
            await db.commit()
            done += 1
    return done


async def autoclose_loop(stop: asyncio.Event) -> None:
    while not stop.is_set():
        try:
            await autoclose_once()
        except Exception:  # noqa: BLE001
            log.exception("erro no fecho automático")
        await asyncio.sleep(2)


async def update_config(db: AsyncSession, teacher: User, tid: int, data: dict) -> Tournament:
    """Muda group_size / advance_per_group / pontos, só no lobby (antes de a 1.ª ronda começar)."""
    from app.services import tournament as svc
    t = await svc.owned(db, tid, teacher, lock=True)
    if t.format != "eliminatoria":
        raise ApiError(409, "tournament.wrong_format")
    if t.state != "lobby":
        raise ApiError(409, "tournament.lobby_only")
    cfg = dict(t.config)
    for k in ("group_size", "advance_per_group"):
        if data.get(k) is not None:
            cfg[k] = data[k]
    if data.get("points") is not None:
        cfg["points"] = {**pts.config_points(t), **data["points"]}
    t.config = cfg  # reatribui: o JSONB só deteta mudanças por substituição
    await db.commit()
    return t
