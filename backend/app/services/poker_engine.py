# Motor de Texas Hold'em No-Limit, puro e sem I/O: baralho (secrets.SystemRandom), blinds (heads-up com regras próprias),
# rondas de apostas com mínimo de raise, all-in e side pots, showdown com avaliador completo (kickers, roda A-2-3-4-5,
# empates com o resto para o primeiro à esquerda do botão). O estado é um dict JSON (serializável) para guardar na BD.
# As cartas são strings "As", "Td", "2c" (rank 23456789TJQKA + naipe cdhs). A soma dos líquidos de uma mão é sempre 0.
import secrets
from itertools import combinations

RANKS = "23456789TJQKA"
SUITS = "cdhs"
DECK = [r + s for r in RANKS for s in SUITS]
HAND_NAMES = ["high_card", "pair", "two_pair", "trips", "straight", "flush", "full_house", "quads", "straight_flush", "royal_flush"]
STREETS = ("preflop", "flop", "turn", "river")


class PokerError(Exception):
    """Ação inválida (a chave é uma das chaves extra.*)."""

    def __init__(self, key: str):
        super().__init__(key)
        self.key = key


# ---------------- avaliação ----------------
def _rank(card: str) -> int:
    return RANKS.index(card[0]) + 2


def _straight_high(ranks: set[int]) -> int | None:
    if 14 in ranks:
        ranks = ranks | {1}
    for high in range(14, 4, -1):
        if all(r in ranks for r in range(high - 4, high + 1)):
            return high
    return None


def evaluate5(cards: tuple[str, ...]) -> tuple:
    """(categoria 0..9, desempates...). Maior tuplo = melhor mão."""
    ranks = sorted((_rank(c) for c in cards), reverse=True)
    flush = len({c[1] for c in cards}) == 1
    straight = _straight_high(set(ranks))
    counts: dict[int, int] = {}
    for r in ranks:
        counts[r] = counts.get(r, 0) + 1
    groups = sorted(counts.items(), key=lambda kv: (-kv[1], -kv[0]))
    pattern = [n for _, n in groups]
    if straight and flush:
        return (9 if straight == 14 else 8, straight)
    if pattern == [4, 1]:
        return (7, groups[0][0], groups[1][0])
    if pattern == [3, 2]:
        return (6, groups[0][0], groups[1][0])
    if flush:
        return (5, *ranks)
    if straight:
        return (4, straight)
    if pattern == [3, 1, 1]:
        return (3, groups[0][0], groups[1][0], groups[2][0])
    if pattern == [2, 2, 1]:
        return (2, groups[0][0], groups[1][0], groups[2][0])
    if pattern == [2, 1, 1, 1]:
        return (1, groups[0][0], *[g[0] for g in groups[1:]])
    return (0, *ranks)


def best_hand(cards: list[str]) -> tuple[tuple, tuple[str, ...]]:
    """Melhor mão de 5 entre 5–7 cartas: (valor, as 5 cartas)."""
    best, best_cards = None, ()
    for combo in combinations(cards, 5):
        v = evaluate5(combo)
        if best is None or v > best:
            best, best_cards = v, combo
    return best, best_cards


# ---------------- estado ----------------
def _player(seat: int, user_id: int, stack: int) -> dict:
    return {"seat": seat, "user_id": user_id, "stack": stack, "start_stack": stack, "hole": [], "bet": 0, "total": 0,
            "folded": False, "all_in": False, "acted": False, "can_raise": True}


def new_hand(entries: list[tuple[int, int, int]], dealer_seat: int, small_blind: int, big_blind: int, rng=None, deck: list[str] | None = None) -> dict:
    """entries = [(seat, user_id, stack)] dos jogadores ativos (>= 2, stack > 0). `deck` só para testes."""
    if len(entries) < 2:
        raise PokerError("extra.poker_not_enough_players")
    players = [_player(*e) for e in sorted(entries)]
    seats = [p["seat"] for p in players]
    if dealer_seat not in seats:
        raise PokerError("extra.poker_invalid_dealer")
    d = list(deck) if deck is not None else list(DECK)
    if deck is None:
        (rng or secrets.SystemRandom()).shuffle(d)
    h = {"players": players, "dealer": dealer_seat, "sb": small_blind, "bb": big_blind, "board": [], "deck": d, "street": "preflop",
         "current_bet": 0, "min_raise": big_blind, "to_act": None, "done": False, "results": None, "log": []}
    n = len(players)
    di = seats.index(dealer_seat)
    sb_i, bb_i = (di, (di + 1) % n) if n == 2 else ((di + 1) % n, (di + 2) % n)
    h["sb_seat"], h["bb_seat"] = players[sb_i]["seat"], players[bb_i]["seat"]
    for p in players:  # duas cartas a cada um, a começar à esquerda do botão
        p["hole"] = []
    for _ in range(2):
        for k in range(n):
            players[(di + 1 + k) % n]["hole"].append(d.pop())
    _post(players[sb_i], small_blind)
    _post(players[bb_i], big_blind)
    h["current_bet"] = max(p["bet"] for p in players)
    first = di if n == 2 else (bb_i + 1) % n
    h["to_act"] = _first_actor(h, first)
    _settle(h, advance_from=None)
    return h


def _post(p: dict, amount: int) -> None:
    amt = min(amount, p["stack"])
    p["stack"] -= amt
    p["bet"] += amt
    p["total"] += amt
    if p["stack"] == 0:
        p["all_in"] = True


def _idx(h: dict, seat: int) -> int:
    return next(i for i, p in enumerate(h["players"]) if p["seat"] == seat)


def _can_act(p: dict) -> bool:
    return not p["folded"] and not p["all_in"]


def _first_actor(h: dict, start_i: int) -> int | None:
    n = len(h["players"])
    for k in range(n):
        p = h["players"][(start_i + k) % n]
        if _can_act(p):
            return p["seat"]
    return None


def legal(h: dict, seat: int) -> dict:
    """O que o jogador da vez pode fazer (valores em 'total apostado nesta ronda')."""
    p = h["players"][_idx(h, seat)]
    to_call = max(0, h["current_bet"] - p["bet"])
    max_to = p["bet"] + p["stack"]
    min_to = h["current_bet"] + h["min_raise"] if h["current_bet"] else h["bb"]
    can_raise = p["can_raise"] and max_to > h["current_bet"]
    return {
        "can_check": to_call == 0, "to_call": min(to_call, p["stack"]), "can_fold": True,
        "can_raise": can_raise, "min_raise_to": min(min_to, max_to) if can_raise else None, "max_raise_to": max_to if can_raise else None,
    }


def _commit(p: dict, to: int) -> None:
    add = to - p["bet"]
    p["stack"] -= add
    p["bet"] = to
    p["total"] += add
    if p["stack"] == 0:
        p["all_in"] = True


def act(h: dict, seat: int, type_: str, amount: int | None = None) -> list[dict]:
    """Aplica uma ação da vez de `seat`. Levanta PokerError. Devolve os eventos gerados (ação, ruas, showdown...)."""
    if h["done"]:
        raise PokerError("extra.poker_hand_over")
    if h["to_act"] != seat:
        raise PokerError("extra.poker_not_your_turn")
    p = h["players"][_idx(h, seat)]
    to_call = max(0, h["current_bet"] - p["bet"])
    events: list[dict] = []
    committed_before = p["total"]
    if type_ == "fold":
        p["folded"] = True
    elif type_ == "check":
        if to_call:
            raise PokerError("extra.poker_cannot_check")
        p["acted"] = True
    elif type_ == "call":
        if not to_call:
            raise PokerError("extra.poker_nothing_to_call")
        _commit(p, p["bet"] + min(to_call, p["stack"]))
        p["acted"] = True
    elif type_ in ("bet", "raise", "all_in"):
        max_to = p["bet"] + p["stack"]
        to = max_to if type_ == "all_in" else amount
        if not isinstance(to, int) or isinstance(to, bool) or to > max_to or to <= p["bet"]:
            raise PokerError("extra.poker_invalid_amount")
        if to > h["current_bet"] and not p["can_raise"]:
            raise PokerError("extra.poker_cannot_raise")
        if to < h["current_bet"] and to != max_to:
            raise PokerError("extra.poker_invalid_amount")
        if to == h["current_bet"] and type_ != "all_in" and to != max_to:
            raise PokerError("extra.poker_invalid_amount")  # igualar a aposta é "call"
        if to > h["current_bet"]:
            increment = to - h["current_bet"]
            min_inc = h["min_raise"]
            if to != max_to and increment < min_inc:
                raise PokerError("extra.poker_raise_too_small")
            others = [o for o in h["players"] if o is not p and _can_act(o)]
            if increment >= min_inc:  # raise completo: reabre a ação a todos
                h["min_raise"] = increment
                for o in others:
                    o["acted"], o["can_raise"] = False, True
            else:  # all-in curto: quem já tinha agido só pode pagar ou desistir
                for o in others:
                    if o["acted"]:
                        o["acted"], o["can_raise"] = False, False
            h["current_bet"] = to
        _commit(p, to)
        p["acted"] = True
    else:
        raise PokerError("extra.poker_invalid_action")
    events.append({"type": "action", "seat": seat, "user_id": p["user_id"], "action": type_, "amount": p["total"] - committed_before,
                   "to": p["bet"], "stack": p["stack"], "street": h["street"], "all_in": p["all_in"]})
    h["log"].append({"seat": seat, "action": type_, "to": p["bet"], "street": h["street"]})
    events.extend(_settle(h, advance_from=_idx(h, seat)))
    return events


def _settle(h: dict, advance_from: int | None) -> list[dict]:
    """Depois de cada ação: decide quem joga a seguir, avança a rua ou termina a mão."""
    events: list[dict] = []
    while True:
        live = [p for p in h["players"] if not p["folded"]]
        if len(live) == 1:
            events.extend(_finish(h, showdown=False))
            return events
        need = [p for p in live if _can_act(p) and (not p["acted"] or p["bet"] < h["current_bet"])]
        if need:
            if advance_from is None:
                h["to_act"] = h["to_act"] if h["to_act"] in [p["seat"] for p in need] else need[0]["seat"]
            else:
                n = len(h["players"])
                for k in range(1, n + 1):
                    cand = h["players"][(advance_from + k) % n]
                    if cand in need:
                        h["to_act"] = cand["seat"]
                        break
            return events
        h["to_act"] = None
        if h["street"] == "river":
            events.extend(_finish(h, showdown=True))
            return events
        events.append(_deal_street(h))
        di = _idx(h, h["dealer"])
        first = _first_actor(h, (di + 1) % len(h["players"]))
        h["to_act"] = first
        advance_from = None
        if first is None or sum(1 for p in live if _can_act(p)) < 2:
            h["to_act"] = None  # corre o resto das ruas sem apostas
            for p in live:
                p["acted"] = True
            continue


def _deal_street(h: dict) -> dict:
    h["deck"].pop()  # queima uma carta
    n = 3 if h["street"] == "preflop" else 1
    h["board"].extend(h["deck"].pop() for _ in range(n))
    h["street"] = {"preflop": "flop", "flop": "turn", "turn": "river"}[h["street"]]
    for p in h["players"]:
        p["bet"], p["acted"], p["can_raise"] = 0, False, True
    h["current_bet"], h["min_raise"] = 0, h["bb"]
    return {"type": "street", "street": h["street"], "board": list(h["board"])}


def side_pots(players: list[dict]) -> list[dict]:
    """Potes por níveis de contribuição: [{amount, eligible:[seats]}]. O dinheiro de quem desistiu fica nos potes."""
    levels = sorted({p["total"] for p in players if p["total"] > 0})
    pots, prev = [], 0
    for lvl in levels:
        amount = sum(min(p["total"], lvl) - min(p["total"], prev) for p in players)
        eligible = [p["seat"] for p in players if not p["folded"] and p["total"] >= lvl]
        if amount:
            if not eligible and pots:  # dinheiro morto acima do maior contributo vivo: vai para o último pote
                pots[-1]["amount"] += amount
            elif pots and pots[-1]["eligible"] == eligible:
                pots[-1]["amount"] += amount
            else:
                pots.append({"amount": amount, "eligible": eligible})
        prev = lvl
    return pots


def display_pots(players: list[dict]) -> list[dict]:
    """Potes para mostrar durante a mão: só se separa um side pot onde há um jogador all-in (nunca pela diferença das blinds)."""
    caps = {p["total"] for p in players if p["all_in"] and not p["folded"]}
    pots, prev, cur = [], 0, 0
    for lvl in sorted({p["total"] for p in players if p["total"] > 0}):
        cur += sum(min(p["total"], lvl) - min(p["total"], prev) for p in players)
        prev = lvl
        if lvl in caps:
            pots.append({"amount": cur})
            cur = 0
    if cur:
        if pots and sum(1 for p in players if p["total"] > max(caps) and not p["folded"]) < 2:
            pots[-1]["amount"] += cur  # excesso que ninguém disputa (aposta ainda não paga): fica no último pote
        else:
            pots.append({"amount": cur})
    return pots


def _finish(h: dict, showdown: bool) -> list[dict]:
    live = [p for p in h["players"] if not p["folded"]]
    pots = side_pots(h["players"])
    hands: dict[int, dict] = {}
    if showdown:
        for p in live:
            value, five = best_hand(p["hole"] + h["board"])
            hands[p["seat"]] = {"cards": list(p["hole"]), "category": value[0], "name": HAND_NAMES[value[0]], "best5": list(five), "value": list(value)}
    seats = [p["seat"] for p in h["players"]]
    di = seats.index(h["dealer"])
    order = [seats[(di + 1 + k) % len(seats)] for k in range(len(seats))]  # a começar à esquerda do botão
    payouts = {s: 0 for s in seats}
    awarded = []
    for pot in pots:
        elig = [s for s in pot["eligible"]]
        if showdown:
            top = max(tuple(hands[s]["value"]) for s in elig)
            winners = [s for s in elig if tuple(hands[s]["value"]) == top]
        else:
            winners = elig
        share, rest = divmod(pot["amount"], len(winners))
        for s in winners:
            payouts[s] += share
        for s in [x for x in order if x in winners][:rest]:  # fichas ímpares: primeiro à esquerda do botão
            payouts[s] += 1
        awarded.append({"amount": pot["amount"], "eligible": elig, "winners": winners})
    for p in h["players"]:
        p["stack"] += payouts[p["seat"]]
    nets = {p["user_id"]: p["stack"] - p["start_stack"] for p in h["players"]}
    h["done"], h["to_act"] = True, None
    h["results"] = {"showdown": showdown, "board": list(h["board"]), "pots": awarded, "hands": {str(s): v for s, v in hands.items()},
                    "payouts": {str(s): v for s, v in payouts.items()}, "nets": {str(u): v for u, v in nets.items()},
                    "final_stacks": {str(p["seat"]): p["stack"] for p in h["players"]}}
    events = []
    if showdown:
        uid = {p["seat"]: p["user_id"] for p in h["players"]}
        events.append({"type": "showdown", "board": list(h["board"]), "hands": [
            {"seat": int(s), "user_id": uid[int(s)], "rank_name": x["name"], **{k: v for k, v in x.items() if k != "value"}} for s, x in hands.items()]})
    uid = {p["seat"]: p["user_id"] for p in h["players"]}
    events.append({"type": "pot_awarded", "pots": awarded, "payouts": {str(s): v for s, v in payouts.items()},
                   "awards": [{"user_id": uid[s], "seat": s, "amount": v} for s, v in payouts.items() if v > 0]})
    return events


def fold_out(h: dict, seat: int) -> list[dict]:
    """Retira um jogador da mão fora da sua vez (saiu da mesa): desiste e a mão continua."""
    p = h["players"][_idx(h, seat)]
    if p["folded"] or h["done"]:
        return []
    if h["to_act"] == seat:
        return act(h, seat, "fold")
    p["folded"] = True
    ev = [{"type": "action", "seat": seat, "user_id": p["user_id"], "action": "fold", "amount": 0, "to": p["bet"], "stack": p["stack"],
           "street": h["street"], "all_in": p["all_in"]}]
    return ev + _settle(h, advance_from=None)


# ---------------- vistas ----------------
def out_card(c: str) -> str:
    """Formato de saída das cartas: o dez é "10" (ex. "10h"), como nos sprites."""
    return "10" + c[1] if c[0] == "T" else c


def out_cards(cards):
    return None if cards is None else [out_card(c) for c in cards]


def pot_total(h: dict) -> int:
    return sum(p["total"] for p in h["players"])


def public_view(h: dict, viewer_user_id: int | None) -> dict:
    """Vista de um jogador: só as SUAS cartas fechadas; as dos outros só depois do showdown (se mostradas)."""
    shown = {int(s) for s in (h["results"] or {}).get("hands", {})} if h["done"] else set()
    return {
        "street": h["street"], "dealer": h["dealer"], "sb_seat": h["sb_seat"], "bb_seat": h["bb_seat"], "board": list(h["board"]),
        "pot": pot_total(h), "pots": display_pots(h["players"]), "current_bet": h["current_bet"], "min_raise": h["min_raise"],
        "to_act": h["to_act"], "done": h["done"],
        "players": [{
            "seat": p["seat"], "user_id": p["user_id"], "stack": p["stack"], "bet": p["bet"], "total": p["total"], "folded": p["folded"], "all_in": p["all_in"],
            "cards": p["hole"] if (p["user_id"] == viewer_user_id or p["seat"] in shown) else None,
        } for p in h["players"]],
        "results": ({k: v for k, v in h["results"].items() if k != "hands"} | {"hands": {s: {k: v for k, v in x.items() if k != "value"} for s, x in h["results"]["hands"].items()}}) if h["done"] else None,
    }
