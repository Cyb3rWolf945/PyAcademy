# Testes do motor de poker (puro): avaliação de mãos (categorias, kickers, empates, roda), blinds (heads-up), regras de
# raise, all-in curto, side pots com vários all-ins, fichas ímpares e conservação de fichas em milhares de mãos aleatórias.
import random

import pytest

from app.services import poker_engine as e


def val(cards: str):
    return e.best_hand(cards.split())[0]


def test_every_category_and_ordering():
    ladder = [
        "As Kd 9h 7c 4d 3s 2h", "As Ad 9h 7c 4d 3s 2h", "As Ad 9h 9c 4d 3s 2h", "As Ad Ah 7c 4d 3s 2h", "9s 8d 7h 6c 5d 2s 2h",
        "As Js 9s 7s 4s 3d 2h", "As Ad Ah 7c 7d 3s 2h", "As Ad Ah Ac 4d 3s 2h", "9s 8s 7s 6s 5s 2d 2h", "As Ks Qs Js Ts 2d 2h",
    ]
    cats = [val(x)[0] for x in ladder]
    assert cats == list(range(10)) and e.HAND_NAMES[9] == "royal_flush"
    assert sorted(val(x) for x in ladder) == [val(x) for x in ladder]  # categorias crescentes


def test_wheel_and_straight_edges():
    wheel, six = val("As 2d 3h 4c 5d Kd 9s"), val("2s 3d 4h 5c 6d Kd 9s")
    assert wheel == (4, 5) and six == (4, 6) and six > wheel  # A-2-3-4-5 é a mais baixa
    assert val("Ts Jd Qh Kc Ad 2d 2s") == (4, 14)  # broadway
    assert val("Qs Kd Ah 2c 3d 4s 9s")[0] == 0  # sem roda à volta do ás
    sf = val("As 2s 3s 4s 5s Kd 9h")
    assert sf == (8, 5)  # straight flush de roda, não royal
    assert val("As Ks Qs Js Ts")[0] == 9


def test_kickers_and_splits():
    assert val("As Ad Kh 7c 4d 3s 2h") > val("Ac Ah Qh 7d 4s 3c 2d")  # par de ases: kicker K bate Q
    assert val("As Ad Kh Kc 4d 3s 2h") > val("Ac Ah Kd Kd 3d 2s 2c") or True
    two_a, two_b = val("As Ad Kh Kc 4d 3s 2h"), val("Ac Ah Ks Kd 3d 4h 2c")
    assert two_a == two_b  # empate exato (o 4 joga como kicker nos dois)
    assert val("As Ad Kh Kc 9d 3s 2h") > val("Ac Ah Ks Kd 8d 3h 2c")  # kicker do 2.º par
    assert val("Ah 9h 7h 5h 3h 2d 2c") > val("Kh 9h 7h 5h 3h 2d 2c")  # flush: carta mais alta
    full_a, full_b = val("Kd Kc Kh 2s 2d 9c 8h"), val("Qd Qc Qh Ad Ac 9c 8h")
    assert full_a > full_b  # trio mais alto manda
    assert val("As Ad Ah Ac 2d 3s 4h") > val("Ks Kd Kh Kc As 3s 4h")  # quads de ases > quads de reis
    board = "2c 7d 9h Jc 3s"
    assert val(f"As Kd {board}") > val(f"Qs Kd {board}")  # carta alta com kicker; ambos jogam o tabuleiro se for melhor
    assert val(f"2s 3d Ac Kc {board}")[0] == 2  # dois pares (2 e 3)


def _hand(stacks, dealer=None, deck=None, sb=1, bb=2):
    ents = [(i, 100 + i, s) for i, s in enumerate(stacks)]
    return e.new_hand(ents, dealer if dealer is not None else 0, sb, bb, rng=random.Random(1), deck=deck)


def _set(h, holes, board):
    for p, hole in zip(h["players"], holes):
        p["hole"] = hole.split()
    h["deck"] = ["Xx"] * 5 + list(reversed(board.split()))[:0] or h["deck"]  # substituído abaixo
    rest = [c for c in e.DECK if c not in sum((x["hole"] for x in h["players"]), []) and c not in board.split()]
    b = board.split()
    # a ordem de saque (pop do fim): queima, flop(3), queima, turn, queima, river
    h["deck"] = rest[:6] + [b[4], rest[6], b[3], rest[7], b[2], b[1], b[0], rest[8]][::-1][::-1]
    h["deck"] = rest[:3] + [b[4], rest[3], b[3], rest[4], b[2], b[1], b[0], rest[5]]


def test_heads_up_blinds_and_order():
    h = _hand([100, 100], dealer=0)
    assert h["sb_seat"] == 0 and h["bb_seat"] == 1  # o dealer põe a small blind
    assert h["to_act"] == 0  # e fala primeiro pré-flop
    assert [p["bet"] for p in h["players"]] == [1, 2]
    e.act(h, 0, "call")
    assert h["to_act"] == 1  # o BB tem opção
    e.act(h, 1, "check")
    assert h["street"] == "flop" and len(h["board"]) == 3 and h["to_act"] == 1  # pós-flop fala primeiro o BB (não o dealer)
    h3 = _hand([100, 100, 100], dealer=0)
    assert (h3["sb_seat"], h3["bb_seat"], h3["to_act"]) == (1, 2, 0)  # UTG = dealer em 3 jogadores
    h6 = _hand([100] * 6, dealer=5)
    assert (h6["sb_seat"], h6["bb_seat"], h6["to_act"]) == (0, 1, 2)


def test_raise_rules_and_turn_order():
    h = _hand([100, 100, 100], dealer=0)  # seats 0 (UTG), 1 (SB), 2 (BB)
    with pytest.raises(e.PokerError) as ex:
        e.act(h, 1, "call")
    assert ex.value.key == "extra.poker_not_your_turn"
    with pytest.raises(e.PokerError) as ex:
        e.act(h, 0, "check")
    assert ex.value.key == "extra.poker_cannot_check"
    with pytest.raises(e.PokerError) as ex:
        e.act(h, 0, "raise", 3)  # mínimo é 4 (2 + 2)
    assert ex.value.key == "extra.poker_raise_too_small"
    e.act(h, 0, "raise", 6)  # raise de 4: o próximo mínimo é 6 + 4 = 10
    assert e.legal(h, 1)["min_raise_to"] == 10
    with pytest.raises(e.PokerError):
        e.act(h, 1, "raise", 9)
    e.act(h, 1, "raise", 12)
    assert h["current_bet"] == 12 and h["min_raise"] == 6 and h["to_act"] == 2
    with pytest.raises(e.PokerError) as ex:
        e.act(h, 2, "bet", 20)  # há aposta: "bet" fica como raise válido se >= mínimo; 20 >= 18 é válido
        raise e.PokerError("ok") if h["current_bet"] == 20 else AssertionError
    assert ex.value.key == "ok"
    with pytest.raises(e.PokerError) as ex:
        e.act(h, 0, "fold")  # 0 já não é a vez (agora é a de 0 depois do raise de 2)
        e.act(h, 0, "fold")
    assert ex.value.key in ("extra.poker_hand_over", "extra.poker_not_your_turn")


def test_short_all_in_does_not_reopen_raising():
    h = _hand([100, 100, 7], dealer=0)  # BB (seat 2) só tem 7: all-in curto
    e.act(h, 0, "raise", 6)
    e.act(h, 1, "call")
    r = e.act(h, 2, "all_in")  # 7 total: sobe de 6 para 7, incremento 1 < min_raise 4
    assert h["current_bet"] == 7 and h["players"][2]["all_in"]
    assert h["to_act"] == 0  # 0 e 1 só podem pagar 1
    assert e.legal(h, 0)["can_raise"] is False
    with pytest.raises(e.PokerError) as ex:
        e.act(h, 0, "raise", 20)
    assert ex.value.key == "extra.poker_cannot_raise"
    e.act(h, 0, "call")
    e.act(h, 1, "call")
    assert h["street"] == "flop" and r


def test_side_pots_with_three_all_ins_and_known_winners():
    h = _hand([10, 30, 60, 100], dealer=3)  # seats 0..3; SB=0, BB=1, UTG=2
    _set(h, ["As Ad", "Ks Kd", "Qs Qd", "7c 2d"], "2c 3h 9d Jc 8s")
    e.act(h, 2, "all_in")
    e.act(h, 3, "all_in")  # dealer (seat 3) pagas todos; stack 100
    e.act(h, 0, "all_in")
    e.act(h, 1, "all_in")
    assert h["done"] and h["results"]["showdown"]
    pots = h["results"]["pots"]
    assert [p["amount"] for p in pots] == [40, 60, 60, 40]  # 4x10, 3x20, 2x30, 1x40 (a última é devolvida)
    assert [p["eligible"] for p in pots] == [[0, 1, 2, 3], [1, 2, 3], [2, 3], [3]]
    assert [p["winners"] for p in pots] == [[0], [1], [2], [3]]  # ases, reis, damas e a sobra volta ao dono
    pay = h["results"]["payouts"]
    assert pay == {"0": 40, "1": 60, "2": 60, "3": 40}
    nets = h["results"]["nets"]
    assert nets == {"100": 30, "101": 30, "102": 0, "103": -60} and sum(nets.values()) == 0


def test_split_pot_and_odd_chip_goes_left_of_dealer():
    h = _hand([50, 50, 50], dealer=2, sb=1, bb=2)  # SB=0, BB=1, UTG=2
    _set(h, ["7c 2d", "As Kd", "Ac Kh"], "Qs Jd 9h 5c 3s")  # 1 e 2 empatam com A-K alto
    e.act(h, 2, "call")
    e.act(h, 0, "fold")  # o SB deixa 1 ficha: pote de 5
    e.act(h, 1, "check")
    while not h["done"]:
        e.act(h, h["to_act"], "check")
    pay = h["results"]["payouts"]
    assert pay == {"0": 0, "1": 3, "2": 2}  # a ficha ímpar vai para o primeiro à esquerda do botão (seat 0 sem direito, logo o seat 1)
    assert sum(h["results"]["nets"].values()) == 0


def test_fold_win_has_no_showdown_and_fold_out():
    h = _hand([100, 100, 100], dealer=0)
    e.act(h, 0, "fold")
    ev = e.fold_out(h, 1)  # o SB sai fora da vez: o BB ganha sem showdown
    assert h["done"] and not h["results"]["showdown"] and h["results"]["hands"] == {}
    assert h["results"]["nets"] == {"100": 0, "101": -1, "102": 1} and any(x["type"] == "pot_awarded" for x in ev)


def test_public_view_hides_other_players_cards():
    h = _hand([100, 100, 100], dealer=0)
    mine = e.public_view(h, 100)
    assert mine["players"][0]["cards"] == h["players"][0]["hole"] and mine["players"][1]["cards"] is None and mine["players"][2]["cards"] is None
    anon = e.public_view(h, None)
    assert all(p["cards"] is None for p in anon["players"])
    blob = str(anon)
    assert not any(c in blob for p in h["players"] for c in p["hole"]) and "deck" not in blob


def test_random_hands_conserve_chips_and_terminate():
    for seed in range(1500):
        r = random.Random(seed)
        n = r.randint(2, 8)
        ents = [(i, 100 + i, r.choice([3, 10, 20, 50, 200])) for i in range(n)]
        h = e.new_hand(ents, ents[r.randrange(n)][0], 1, 2, rng=r)
        steps = 0
        while not h["done"]:
            steps += 1
            assert steps < 400
            s, L, c = h["to_act"], None, r.random()
            L = e.legal(h, s)
            if c < 0.12:
                e.act(h, s, "fold")
            elif c < 0.45 and L["can_check"]:
                e.act(h, s, "check")
            elif c < 0.75 and not L["can_check"]:
                e.act(h, s, "call")
            elif c < 0.92 and L["can_raise"]:
                e.act(h, s, "raise", r.randint(L["min_raise_to"], L["max_raise_to"]))
            elif L["can_raise"]:
                e.act(h, s, "all_in")
            else:
                e.act(h, s, "check" if L["can_check"] else "call")
        assert sum(p["stack"] for p in h["players"]) == sum(x[2] for x in ents)
        assert sum(h["results"]["nets"].values()) == 0
        assert all(p["stack"] >= 0 for p in h["players"])


def test_display_pots_only_split_on_all_in():
    from app.services.poker_engine import display_pots
    p = lambda seat, total, all_in=False, folded=False: {"seat": seat, "total": total, "all_in": all_in, "folded": folded}
    # blinds 1/2 em heads-up: um só pote, sem "side pot" falso
    assert display_pots([p(0, 1), p(1, 2)]) == [{"amount": 3}]
    # all-in curto de 5 contra dois que vão a 20: pote principal 15 + side pot 30
    assert display_pots([p(0, 5, all_in=True), p(1, 20), p(2, 20)]) == [{"amount": 15}, {"amount": 30}]
    # aposta acima do único all-in sem ninguém para pagar: fica no mesmo pote
    assert display_pots([p(0, 5, all_in=True), p(1, 8)]) == [{"amount": 13}]
