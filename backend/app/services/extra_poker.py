# Mesas de poker: lugares e buy-in, início das mãos, ações (idempotentes, por vez), temporizadores do servidor
# (30 s -> check/fold; ausente -> auto-fold -> sitting_out), escrita atómica de `poker_net` por mão (soma 0) e eventos.
# Um advisory lock por mesa serializa tudo; o motor (poker_engine) é puro e o estado da mão fica em poker_hands.state.
import asyncio
import copy
import logging
from datetime import timedelta

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import SessionLocal
from app.errors import ApiError
from app.models._base import utcnow
from app.models.extra import PokerAction, PokerEvent, PokerHand, PokerSeat, PokerTable
from app.models.user import Role, SchoolClass, User
from app.services import extra
from app.services import poker_engine as eng
from app.services.leaderboard import avatar_seed

log = logging.getLogger("pyarena.poker")
TURN_S = 30
BETWEEN_HANDS_S = 5
AWAY_HANDS_LIMIT = 2
LOCK_NS = 2024
ENGINE_ERRORS = {"extra.poker_not_enough_players", "extra.poker_invalid_dealer"}


def channel(table_id: int) -> str:
    return f"poker_{int(table_id)}"


# ---------------- eventos ----------------
async def emit(db: AsyncSession, table_id: int, type_: str, payload: dict, user_id: int | None = None) -> int:
    ev = PokerEvent(table_id=table_id, type=type_, payload=payload, user_id=user_id)
    db.add(ev)
    await db.flush()
    await db.execute(text("SELECT pg_notify(:c, :p)"), {"c": channel(table_id), "p": str(ev.seq)})
    return ev.seq


def visible_to(ev: dict, user_id: int) -> bool:
    """hole_cards é privado: só o dono. O resto é público."""
    return ev["type"] != "hole_cards" or ev["payload"].get("user_id") == user_id


async def events_after(db: AsyncSession, table_id: int, after: int, limit: int = 500) -> list[dict]:
    rows = (await db.execute(select(PokerEvent).where(PokerEvent.table_id == table_id, PokerEvent.seq > after).order_by(PokerEvent.seq).limit(limit))).scalars()
    return [{"seq": e.seq, "type": e.type, "payload": e.payload} for e in rows]


async def last_seq(db: AsyncSession, table_id: int) -> int:
    return int((await db.execute(select(func.coalesce(func.max(PokerEvent.seq), 0)).where(PokerEvent.table_id == table_id))).scalar_one())


async def lock(db: AsyncSession, table_id: int) -> None:
    await db.execute(text("SELECT pg_advisory_xact_lock(:n, :t)"), {"n": LOCK_NS, "t": table_id})


def _wire(e: dict) -> dict:
    """Payload público de um evento do motor: cartas no formato de saída ("10h") e `type` = tipo da ação."""
    out = {k: v for k, v in e.items() if k != "type"}
    if e["type"] == "action":
        out["type"] = e["action"]
    if "board" in out:
        out["board"] = eng.out_cards(out["board"])
    if e["type"] == "showdown":
        out["hands"] = [dict(h, cards=eng.out_cards(h["cards"]), best5=eng.out_cards(h["best5"])) for h in out["hands"]]
    return out


# ---------------- acesso ----------------
async def get_table(db: AsyncSession, table_id: int, user: User, *, for_update: bool = False) -> PokerTable:
    t = await db.get(PokerTable, table_id)
    if t is None or t.state != "open":
        raise ApiError(404, "extra.table_not_found")
    if user.role == Role.teacher:
        cls = await db.get(SchoolClass, t.class_id)
        if cls is None or cls.teacher_id != user.id:
            raise ApiError(404, "extra.table_not_found")
    elif user.class_id != t.class_id:  # turmas nunca se misturam
        raise ApiError(404, "extra.table_not_found")
    if for_update:
        await lock(db, table_id)
        await db.refresh(t)
    return t


async def seats_of(db: AsyncSession, table_id: int) -> list[PokerSeat]:
    return list((await db.execute(select(PokerSeat).where(PokerSeat.table_id == table_id).order_by(PokerSeat.seat))).scalars())


async def names(db: AsyncSession, ids) -> dict[int, str]:
    ids = list(set(ids))
    return dict((await db.execute(select(User.id, User.display_name).where(User.id.in_(ids)))).all()) if ids else {}


# ---------------- mesas ----------------
async def create_table(db: AsyncSession, user: User, class_id: int | None, name: str, max_seats: int) -> PokerTable:
    cls = await extra.class_for(db, user, class_id)
    st = await extra.get_settings(db, cls.id)
    if not st["poker_enabled"]:
        raise ApiError(403, "extra.poker_disabled")
    if user.role != Role.teacher and not st["students_can_create_tables"]:
        raise ApiError(403, "extra.create_not_allowed")
    n = (await db.execute(select(func.count()).select_from(PokerTable).where(PokerTable.class_id == cls.id, PokerTable.state == "open"))).scalar_one()
    if n >= st["max_tables"]:
        raise ApiError(409, "extra.too_many_tables")
    t = PokerTable(class_id=cls.id, name=name, max_seats=max_seats, small_blind=1, big_blind=2, created_by=user.id)
    db.add(t)
    await db.commit()
    return t


async def list_tables(db: AsyncSession, user: User, class_id: int | None) -> list[dict]:
    cls = await extra.class_for(db, user, class_id)
    tables = (await db.execute(select(PokerTable).where(PokerTable.class_id == cls.id, PokerTable.state == "open").order_by(PokerTable.id))).scalars().all()
    counts = dict((await db.execute(select(PokerSeat.table_id, func.count()).where(PokerSeat.table_id.in_([t.id for t in tables] or [0])).group_by(PokerSeat.table_id))).all())
    return [{"id": t.id, "name": t.name, "max_seats": t.max_seats, "small_blind": t.small_blind, "big_blind": t.big_blind,
             "seated": counts.get(t.id, 0), "in_hand": t.current_hand_id is not None} for t in tables]


# ---------------- vista (snapshot) ----------------
async def snapshot(db: AsyncSession, t: PokerTable, user: User) -> dict:
    """Vista do utilizador: só as SUAS cartas fechadas (me.hole); as dos outros só aparecem no showdown (evento)."""
    seq = await last_seq(db, t.id)
    seats = await seats_of(db, t.id)
    nm = await names(db, [s.user_id for s in seats])
    hand = await db.get(PokerHand, t.current_hand_id) if t.current_hand_id else None
    st = hand.state if hand else None
    by_user = {p["user_id"]: p for p in st["players"]} if st else {}
    hand_view, me = None, {"user_id": user.id, "seat": None, "hole": [], "to_call": None, "can_check": None, "min_raise_to": None, "max_raise_to": None}
    mine = next((s for s in seats if s.user_id == user.id), None)
    if mine:
        me["seat"], me["status"] = mine.seat, mine.status
    if st:
        hand_view = {
            "id": hand.id, "hand_no": hand.hand_no, "street": st["street"], "board": eng.out_cards(st["board"]), "pot": eng.pot_total(st),
            "pots": eng.display_pots(st["players"]), "to_act": st["to_act"],
            "deadline": t.turn_deadline.isoformat() if t.turn_deadline and not st["done"] else None, "current_bet": st["current_bet"],
            "min_raise": st["min_raise"], "dealer_seat": st["dealer"], "sb_seat": st["sb_seat"], "bb_seat": st["bb_seat"],
            "to_act_user": next((p["user_id"] for p in st["players"] if p["seat"] == st["to_act"]), None),
        }
        mp = by_user.get(user.id)
        if mp:
            me["hole"] = eng.out_cards(mp["hole"])
            if not mp["folded"] and not st["done"] and not mp["all_in"]:
                lg = eng.legal(st, mp["seat"])
                me.update(to_call=lg["to_call"], can_check=lg["can_check"], min_raise_to=lg["min_raise_to"], max_raise_to=lg["max_raise_to"], my_turn=st["to_act"] == mp["seat"])
    last = None
    if hand is None:
        row = (await db.execute(select(PokerHand).where(PokerHand.table_id == t.id).order_by(PokerHand.id.desc()).limit(1))).scalars().first()
        if row and row.results:
            last = {"hand_id": row.id, "nets": row.results.get("nets"), "board": eng.out_cards(row.results.get("board"))}
    out_seats = []
    for s in seats:
        p = by_user.get(s.user_id)
        out_seats.append({
            "seat": s.seat, "user_id": s.user_id, "display_name": nm.get(s.user_id, "?"), "avatar_seed": avatar_seed(s.user_id),
            "stack": p["stack"] if p else s.stack, "bet": p["bet"] if p else 0, "folded": bool(p and p["folded"]), "all_in": bool(p and p["all_in"]),
            "status": s.status, "is_dealer": bool(st and st["dealer"] == s.seat), "in_hand": p is not None,
        })
    return {
        "table": {"id": t.id, "name": t.name, "max_seats": t.max_seats, "small_blind": t.small_blind, "big_blind": t.big_blind, "state": t.state,
                  "next_hand_at": t.next_hand_at.isoformat() if t.next_hand_at else None},
        "seats": out_seats, "hand": hand_view, "me": me, "last_hand": last, "server_now": utcnow().isoformat(), "last_seq": seq,
    }


def table_view(t: PokerTable) -> dict:
    return {"id": t.id, "name": t.name, "max_seats": t.max_seats, "small_blind": t.small_blind, "big_blind": t.big_blind, "state": t.state, "seated": 0}


# ---------------- sentar / levantar ----------------
async def sit(db: AsyncSession, user: User, table_id: int, seat: int, buy_in: int) -> PokerTable:
    if user.role != Role.student:
        raise ApiError(403, "extra.students_only")
    t = await get_table(db, table_id, user, for_update=True)
    st = await extra.get_settings(db, t.class_id)
    if not st["poker_enabled"]:
        raise ApiError(403, "extra.poker_disabled")
    if not await extra.has_consent(db, user.id):
        raise ApiError(403, "extra.consent_required")
    if not 0 <= seat < t.max_seats:
        raise ApiError(422, "extra.invalid_seat")
    if (await db.execute(select(PokerSeat).where(PokerSeat.user_id == user.id))).scalars().first():
        raise ApiError(409, "extra.already_seated")
    if (await db.get(PokerSeat, (t.id, seat))) is not None:
        raise ApiError(409, "extra.seat_taken")
    if await extra.loss_today(db, user.id) >= st["daily_loss_limit"]:
        raise ApiError(403, "extra.loss_limit_reached")
    avail = await extra.available(db, user.id, st["poker_source"])
    lo, hi = extra.buyin_limits(st, avail)
    if avail < st["buy_in_min"] or hi < lo:
        raise ApiError(403, "extra.insufficient_balance")
    if not isinstance(buy_in, int) or not lo <= buy_in <= hi:
        raise ApiError(422, "extra.invalid_buy_in")
    db.add(PokerSeat(table_id=t.id, seat=seat, user_id=user.id, stack=buy_in, buy_in=buy_in, status="sitting"))
    await db.flush()
    await emit(db, t.id, "seat_changed", {"seat": seat, "user_id": user.id, "display_name": user.display_name, "avatar_seed": avatar_seed(user.id), "stack": buy_in, "status": "sitting"})
    await db.commit()
    return t


async def leave(db: AsyncSession, user: User, table_id: int) -> int:
    """Levanta-se: devolve o stack (o líquido já está no livro). Em plena mão: desiste e sai no fim dela."""
    t = await get_table(db, table_id, user, for_update=True)
    s = (await db.execute(select(PokerSeat).where(PokerSeat.table_id == t.id, PokerSeat.user_id == user.id))).scalars().first()
    if s is None:
        raise ApiError(404, "extra.not_seated")
    hand = await db.get(PokerHand, t.current_hand_id) if t.current_hand_id else None
    if hand and not hand.state["done"] and any(p["user_id"] == user.id for p in hand.state["players"]):
        s.status = "leaving"  # sai no fim da mão (as fichas em jogo ficam no pote)
        state = copy.deepcopy(hand.state)
        events = eng.fold_out(state, s.seat)
        hand.state = state
        await _apply(db, t, hand, events, user_id=user.id, auto=True, action="leave", seat=s.seat)
        await db.commit()
        return s.stack
    stack = s.stack
    await db.delete(s)
    await emit(db, t.id, "seat_changed", {"seat": s.seat, "user_id": None, "stack": 0, "status": "empty", "left": user.id})
    await db.commit()
    return stack


async def back(db: AsyncSession, user: User, table_id: int) -> PokerTable:
    t = await get_table(db, table_id, user, for_update=True)
    s = (await db.execute(select(PokerSeat).where(PokerSeat.table_id == t.id, PokerSeat.user_id == user.id))).scalars().first()
    if s is None:
        raise ApiError(404, "extra.not_seated")
    if s.status in ("away", "sitting_out"):
        s.status, s.away_hands = "sitting", 0
        await emit(db, t.id, "seat_changed", {"seat": s.seat, "user_id": user.id, "stack": s.stack, "status": "sitting"})
        await db.commit()
    return t


# ---------------- mãos ----------------
async def start_hand(db: AsyncSession, t: PokerTable) -> bool:
    seats = [s for s in await seats_of(db, t.id) if s.status in ("sitting", "away") and s.stack > 0]
    if len(seats) < 2:
        return False
    nums = [s.seat for s in seats]
    prev = t.dealer_seat if t.dealer_seat is not None else -1
    dealer = next((x for x in nums if x > prev), nums[0])
    state = eng.new_hand([(s.seat, s.user_id, s.stack) for s in seats], dealer, t.small_blind, t.big_blind)
    t.hand_no += 1
    hand = PokerHand(table_id=t.id, hand_no=t.hand_no, dealer_seat=dealer, state=state)
    db.add(hand)
    await db.flush()
    t.dealer_seat, t.current_hand_id, t.next_hand_at = dealer, hand.id, None
    nm = await names(db, [s.user_id for s in seats])
    await emit(db, t.id, "hand_started", {"hand_id": hand.id, "hand_no": hand.hand_no, "dealer": dealer, "sb_seat": state["sb_seat"], "bb_seat": state["bb_seat"],
                                          "players": [{"seat": p["seat"], "user_id": p["user_id"], "display_name": nm.get(p["user_id"]), "stack": p["stack"] + p["bet"], "bet": p["bet"]} for p in state["players"]]})
    for p in state["players"]:
        await emit(db, t.id, "hole_cards", {"hand_id": hand.id, "user_id": p["user_id"], "cards": eng.out_cards(p["hole"])}, user_id=p["user_id"])
    await _after_state(db, t, hand, [])
    return True


async def _after_state(db: AsyncSession, t: PokerTable, hand: PokerHand, events: list[dict]) -> None:
    """Publica os eventos do motor, fixa o prazo da próxima vez ou fecha a mão."""
    s = hand.state
    for e in events:
        await emit(db, t.id, e["type"], _wire(e) | {"hand_id": hand.id})
    if s["done"]:
        await _finish_hand(db, t, hand)
        return
    seat = await db.get(PokerSeat, (t.id, s["to_act"]))
    away = seat is not None and seat.status in ("away", "leaving", "sitting_out")
    t.turn_deadline = utcnow() + timedelta(seconds=0 if away else TURN_S)
    user_id = next(p["user_id"] for p in s["players"] if p["seat"] == s["to_act"])
    await emit(db, t.id, "turn", {"hand_id": hand.id, "seat": s["to_act"], "user_id": user_id, "deadline": t.turn_deadline.isoformat(), "server_now": utcnow().isoformat(), "street": s["street"]})


async def _apply(db: AsyncSession, t: PokerTable, hand: PokerHand, events: list[dict], user_id: int, auto: bool, action: str, amount: int = 0,
                 action_id: str | None = None, seat: int | None = None) -> None:
    n = (await db.execute(select(func.count()).select_from(PokerAction).where(PokerAction.hand_id == hand.id))).scalar_one()
    db.add(PokerAction(hand_id=hand.id, seq=n + 1, user_id=user_id, seat=seat if seat is not None else -1, type=action, amount=amount,
                       street=events[0].get("street", hand.state["street"]) if events else hand.state["street"], action_id=action_id, auto=auto))
    await db.flush()
    await _after_state(db, t, hand, [dict(e, auto=auto) if e["type"] == "action" else e for e in events])


async def _finish_hand(db: AsyncSession, t: PokerTable, hand: PokerHand) -> None:
    """Escreve poker_net de TODOS os jogadores da mão numa só transação (soma 0), atualiza os stacks e limpa a mesa."""
    s = hand.state
    res = s["results"]
    hand.results, hand.ended_at = res, utcnow()
    nets = {int(u): v for u, v in res["nets"].items()}
    assert sum(nets.values()) == 0
    seats = {x.user_id: x for x in await seats_of(db, t.id)}
    for p in s["players"]:
        net = nets[p["user_id"]]
        if net:
            await db.execute(text("""INSERT INTO user_points (user_id, points, reason, tournament_id, round_idx, problem_slug, created_at)
                                    VALUES (:u, :p, 'poker_net', NULL, NULL, :s, now())
                                    ON CONFLICT (user_id, COALESCE(tournament_id, 0), reason, COALESCE(round_idx, 0), COALESCE(problem_slug, '')) DO NOTHING"""),
                             {"u": p["user_id"], "p": net, "s": f"hand-{hand.id}"})
        seat = seats.get(p["user_id"])
        if seat is not None:
            seat.stack = p["stack"]
    st = await extra.get_settings(db, t.class_id)
    await db.flush()
    removed = []
    for p in s["players"]:
        seat = seats.get(p["user_id"])
        if seat is None:
            continue
        if seat.status == "away":
            seat.away_hands += 1
            if seat.away_hands >= AWAY_HANDS_LIMIT:
                seat.status = "sitting_out"
        if seat.status == "leaving" or seat.stack <= 0 or await extra.loss_today(db, p["user_id"]) >= st["daily_loss_limit"]:
            reason = "left" if seat.status == "leaving" else "busted" if seat.stack <= 0 else "loss_limit"
            removed.append((seat.seat, p["user_id"], reason))
            await db.delete(seat)
    await emit(db, t.id, "hand_ended", {"hand_id": hand.id, "nets": {str(u): v for u, v in nets.items()}, "removed": [{"seat": a, "user_id": b, "reason": c} for a, b, c in removed]})
    for seat_no, uid, reason in removed:
        await emit(db, t.id, "seat_changed", {"seat": seat_no, "user_id": None, "stack": 0, "status": "empty", "left": uid, "reason": reason})
    t.current_hand_id, t.turn_deadline, t.next_hand_at = None, None, utcnow() + timedelta(seconds=BETWEEN_HANDS_S)


# ---------------- ações ----------------
async def act(db: AsyncSession, user: User, table_id: int, action_id: str, type_: str, amount: int | None) -> tuple[PokerTable, bool]:
    t = await get_table(db, table_id, user, for_update=True)
    dup = (await db.execute(select(PokerAction.id).where(PokerAction.user_id == user.id, PokerAction.action_id == action_id).limit(1))).first()
    if dup is not None:
        return t, True  # pedido repetido (rede má): não se aplica outra vez
    hand = await db.get(PokerHand, t.current_hand_id) if t.current_hand_id else None
    if hand is None or hand.state["done"]:
        raise ApiError(409, "extra.no_hand")
    me = next((p for p in hand.state["players"] if p["user_id"] == user.id), None)
    if me is None:
        raise ApiError(403, "extra.not_in_hand")
    if hand.state["to_act"] != me["seat"]:
        raise ApiError(409, "extra.poker_not_your_turn")
    state = copy.deepcopy(hand.state)  # cópia: só assim o ORM deteta a alteração do JSONB
    try:
        events = eng.act(state, me["seat"], type_, amount)
    except eng.PokerError as exc:
        raise ApiError(422 if exc.key != "extra.poker_not_your_turn" else 409, exc.key) from None
    hand.state = state
    seat = await db.get(PokerSeat, (t.id, me["seat"]))
    if seat is not None and seat.status == "away":  # voltou a jogar
        seat.status, seat.away_hands = "sitting", 0
    await _apply(db, t, hand, events, user_id=user.id, auto=False, action=type_, amount=events[0].get("amount", 0) if events else 0, action_id=action_id, seat=me["seat"])
    await db.commit()
    return t, False


async def timeout_action(db: AsyncSession, t: PokerTable) -> bool:
    """Prazo da vez expirado (ou jogador ausente): check se possível, senão fold. Marca o lugar como away."""
    hand = await db.get(PokerHand, t.current_hand_id) if t.current_hand_id else None
    if hand is None or hand.state["done"] or hand.state["to_act"] is None:
        return False
    state = copy.deepcopy(hand.state)
    seat_no = state["to_act"]
    p = next(x for x in state["players"] if x["seat"] == seat_no)
    seat = await db.get(PokerSeat, (t.id, seat_no))
    if seat is not None and seat.status == "sitting":
        seat.status = "away"
    kind = "check" if eng.legal(state, seat_no)["can_check"] else "fold"
    events = eng.act(state, seat_no, kind)
    hand.state = state
    await _apply(db, t, hand, events, user_id=p["user_id"], auto=True, action=kind, seat=seat_no)
    return True


async def tick() -> int:
    """Uma volta do temporizador: expira vezes e começa mãos. Seguro com vários workers (lock não bloqueante por mesa)."""
    done = 0
    async with SessionLocal() as db:
        ids = [r[0] for r in (await db.execute(select(PokerTable.id).where(PokerTable.state == "open"))).all()]
    for tid in ids:
        async with SessionLocal() as db:
            got = (await db.execute(text("SELECT pg_try_advisory_xact_lock(:n, :t)"), {"n": LOCK_NS, "t": tid})).scalar()
            if not got:
                continue
            t = await db.get(PokerTable, tid)
            await db.refresh(t)
            now = utcnow()
            if t.current_hand_id is not None:
                if t.turn_deadline is not None and t.turn_deadline <= now and await timeout_action(db, t):
                    await db.commit()
                    done += 1
            elif t.next_hand_at is None or t.next_hand_at <= now:
                if await start_hand(db, t):
                    await db.commit()
                    done += 1
    return done


async def loop(stop: asyncio.Event) -> None:
    while not stop.is_set():
        try:
            await tick()
        except Exception:  # noqa: BLE001
            log.exception("erro no temporizador do poker")
        await asyncio.sleep(1)


# ---------------- auditoria (professor) ----------------
async def hands_for_audit(db: AsyncSession, user: User, table_id: int, limit: int = 50) -> list[dict]:
    t = await db.get(PokerTable, table_id)
    if t is None:
        raise ApiError(404, "extra.table_not_found")
    await extra.class_for(db, user, t.class_id)  # só o professor dono da turma
    hands = (await db.execute(select(PokerHand).where(PokerHand.table_id == table_id).order_by(PokerHand.id.desc()).limit(limit))).scalars().all()
    out = []
    for h in hands:
        acts = (await db.execute(select(PokerAction).where(PokerAction.hand_id == h.id).order_by(PokerAction.seq))).scalars().all()
        nm = await names(db, [p["user_id"] for p in h.state["players"]])
        out.append({
            "id": h.id, "table_id": h.table_id, "hand_no": h.hand_no, "started_at": h.started_at.isoformat(), "ended_at": h.ended_at.isoformat() if h.ended_at else None,
            "dealer_seat": h.dealer_seat, "board": eng.out_cards(h.state["board"]),
            "players": [{"seat": p["seat"], "user_id": p["user_id"], "display_name": nm.get(p["user_id"]), "hole": eng.out_cards(p["hole"]), "start_stack": p["start_stack"], "folded": p["folded"]} for p in h.state["players"]],
            "actions": [{"seq": a.seq, "seat": a.seat, "user_id": a.user_id, "type": a.type, "amount": a.amount, "street": a.street, "auto": a.auto} for a in acts],
            "results": ({**h.results, "board": eng.out_cards(h.results["board"]), "hands": {k: {kk: (eng.out_cards(vv) if kk in ("cards", "best5") else vv) for kk, vv in v.items() if kk != "value"} for k, v in h.results["hands"].items()}} if h.results else None),
        })
    return out


