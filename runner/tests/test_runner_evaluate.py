# Testes funcionais do avaliador: liberdade criativa, requisitos, erros comuns, funções e geradores.
import evaluate
import pytest
from conftest import call, prog


def test_programa_ignora_prompt_e_aceita(judge):
    r = judge("n = int(input('Quantos? '))\nprint(n * 2)", [prog("4\n", "8"), prog("0\n", "0", False)])
    assert r["status"] == "accepted" and r["passed"] == 2 and r["total"] == 2


def test_criatividade_compreensao_e_sum_sao_aceites(judge):
    # problema "de bloco 2" resolvido com matéria futura (compreensão de listas + sum): resultado certo = aceite
    code = "valores = [int(x) for x in input().split()]\nprint(sum(v * v for v in valores))\n"
    r = judge(code, [prog("1 2 3\n", "14"), prog("4\n", "16", False)], comparacao="numeros")
    assert r["status"] == "accepted"


def test_wrong_answer_e_localizacao(judge):
    cases = [prog("", {"pt": "Olá", "en": "Hello"})]
    assert judge("print('hello')", cases, locale="en")["status"] == "accepted"
    assert judge("print('hello')", cases, locale="pt-PT")["status"] == "wrong_answer"


def test_requisito_usa_while_resolvido_com_for(judge):
    code = "total = 0\nfor i in range(1, 4):\n    total += i\nprint(total)\n"
    r = judge(code, [prog("", "6")], requisitos={"usa": ["while"]})
    assert r["status"] == "requirements_unmet"
    assert r["unmet_requirements"] == [{"kind": "usa", "value": "while"}]
    assert r["passed"] == r["total"] == 1  # o output está certo (assinalado)
    ok = "total = 0\ni = 1\nwhile i < 4:\n    total += i\n    i += 1\nprint(total)\n"
    assert judge(ok, [prog("", "6")], requisitos={"usa": ["while"]})["status"] == "accepted"


def test_requisito_proibe_max(judge):
    r = judge("print(max([1, 5, 2]))", [prog("", "5")], requisitos={"proibe": ["max"]})
    assert r["status"] == "requirements_unmet" and r["unmet_requirements"][0] == {"kind": "proibe", "value": "max"}
    ok = "m = 1\nfor v in [1, 5, 2]:\n    if v > m:\n        m = v\nprint(m)"
    assert judge(ok, [prog("", "5")], requisitos={"proibe": ["max"]})["status"] == "accepted"


def test_requisito_funcao_e_recursao(judge):
    cases = [call([3], 6)]
    code = "def fatorial(n):\n    r = 1\n    for i in range(2, n + 1):\n        r *= i\n    return r\n"
    r = judge(code, cases, assinatura="fatorial(n)", requisitos={"define_funcao": {"nome": "fatorial", "parametros": 1}, "recursiva": True})
    assert [u["kind"] for u in r["unmet_requirements"]] == ["recursiva"]
    r = judge(code, cases, assinatura="fatorial(n)", requisitos={"define_funcao": {"nome": "fatorial", "parametros": 2}})
    assert r["unmet_requirements"][0]["kind"] == "define_funcao"
    rec = "def fatorial(n):\n    return 1 if n < 2 else n * fatorial(n - 1)\n"
    assert judge(rec, cases, assinatura="fatorial(n)", requisitos={"recursiva": True})["status"] == "accepted"


def test_requisitos_so_depois_dos_testes(judge):
    r = judge("print(1)", [prog("", "2")], requisitos={"usa": ["while"]})
    assert r["status"] == "wrong_answer" and r["unmet_requirements"] == []


def test_funcao_ordem_importa_e_tipos(judge):
    code = "def f(xs):\n    return sorted(xs, reverse=True)\n"
    assert judge(code, [call([[1, 2, 3]], [1, 2, 3])], assinatura="f(xs)")["status"] == "wrong_answer"
    assert judge(code, [call([[1, 2, 3]], [1, 2, 3])], assinatura="f(xs)", ordem_importa=False)["status"] == "accepted"
    assert judge("def g(a):\n    return a / 2\n", [call([4], 2)], assinatura="g(a)")["status"] == "accepted"  # 2.0 == 2
    assert judge("def g(a):\n    return (a, a)\n", [call([4], [4, 4])], assinatura="g(a)")["status"] == "accepted"


def test_funcao_nao_altera_argumentos_entre_casos(judge):
    code = "def f(xs):\n    xs.append(1)\n    return len(xs)\n"
    r = judge(code, [call([[]], 1), call([[]], 1, False)], assinatura="f(xs)")
    assert r["status"] == "accepted"


def test_erro_comum_do_problema(judge):
    erros = [{"stdout": "Corre!", "quando_stdin": "10\n5\n", "mensagem": {"pt": "ordem", "en": "order"}}]
    r = judge("print('Corre!')", [prog("10\n5\n", "Vai", True)], erros_comuns=erros)
    assert r["status"] == "wrong_answer" and r["feedback"] == {"pt": "ordem", "en": "order"}
    r = judge("print('Outra')", [prog("10\n5\n", "Vai", True)], erros_comuns=erros)
    assert r["feedback"] is None


def test_familias_de_erros_classicos(judge):
    cases = [prog("", "x")]
    assert judge("print('a' + 1)", cases)["hint_family"] == "str_plus_int"
    assert judge("def f(n):\n    return f(n + 1)\nf(0)", cases)["hint_family"] == "recursion"
    assert judge("print(total)", cases)["hint_family"] == "uninitialized_variable"
    assert judge("xs = [1]\nprint(xs[1])", cases)["hint_family"] == "index_error"
    assert judge("n = input()\nif n > 3:\n    pass", [prog("5\n", "x")])["hint_family"] == "input_is_text"
    assert judge("print(int(input()))", [prog("3,5\n", "x")])["hint_family"] == "int_float_input"
    assert judge("print(1 +", cases)["status"] == "compile_error"


def test_compile_error_tem_linha(judge):
    r = judge("x = 1\nif x\n    print(x)\n", [prog("", "1")])
    assert r["status"] == "compile_error" and r["error"]["line"] == 2


def test_codigo_demasiado_grande(sandbox):
    with pytest.raises(evaluate.BadRequest):
        evaluate.evaluate({"code": "x=1\n" * 10000, "cases": [prog("", "")]}, sandbox)


def test_geradores_calculam_args_e_esperado_no_runner(sandbox):
    ref = "def soma(xs):\n    return sum(xs)\n"
    resp = evaluate.generate({
        "code": ref, "assinatura": "soma(xs)", "limite_tempo_s": 2,
        "exprs": ["[list(range(1000))]", "[[random.Random(1).randint(1, 5) for _ in range(10)]]"],
    }, sandbox)
    assert resp["status"] == "ok" and resp["items"][0] == {"args": [list(range(1000))], "devolve": 499500}
    assert len(resp["items"][1]["args"][0]) == 10
    bad = evaluate.generate({"code": ref, "assinatura": "soma(xs)", "exprs": ["__import__('os').getcwd()"]}, sandbox)
    assert bad["status"] != "ok"


def test_algoritmia_ingenua_da_tle_e_referencia_passa(judge):
    n = 3000
    gen_cases = [call([list(range(n)), -1], [], False)]
    naive = "def f(xs, t):\n    for i in range(len(xs)):\n        for j in range(len(xs)):\n            for k in range(len(xs)):\n                pass\n    return []\n"
    fast = "def f(xs, t):\n    return []\n"
    assert judge(naive, gen_cases, assinatura="f(xs, t)", limite_tempo_s=1)["cases"][0]["status"] == "time_limit"
    assert judge(fast, gen_cases, assinatura="f(xs, t)", limite_tempo_s=1)["status"] == "accepted"
