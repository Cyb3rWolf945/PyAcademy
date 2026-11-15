# Testes de segurança do sandbox: o código hostil tem de ser contido e o resultado não pode ser falsificado.
import json
import os
import time

from conftest import call, prog

HID = [prog("", "x", visible=False)]


def status(judge, code, cases=HID, **kw):
    r = judge(code, cases, limite_tempo_s=kw.pop("limite_tempo_s", 1), **kw)
    return r["status"], r


def test_fork_bomb_contido(judge):
    t0 = time.monotonic()
    st, r = status(judge, "import os\nwhile True:\n    os.fork()\n")
    assert st == "runtime_error" and r["hint_family"] == "import_blocked"
    # mesmo contornando o import (via módulo já carregado): sem processos novos
    code = "import random\nwhile True:\n    random._os.fork()\n"
    assert status(judge, code)[0] == "runtime_error"
    assert time.monotonic() - t0 < 10


def test_print_infinito_corta_o_output(judge):
    st, r = status(judge, "while True:\n    print(1)\n")
    assert st == "output_limit" and r["runtime_ms"] < 1500


def test_ciclo_infinito_silencioso_da_time_limit(judge):
    st, r = status(judge, "while True:\n    pass\n")
    assert st == "time_limit" and r["hint_family"] == "infinite_loop"


def test_nao_escreve_ficheiros(judge):
    for code in ("open('/etc/passwd','w')", "f = open('x.txt','w')\nf.write('a'*100)\nf.flush()", "import os\nos.remove('/etc/passwd')"):
        assert status(judge, code)[0] == "runtime_error", code


def test_imports_perigosos_bloqueados(judge):
    for code in (
        "import os", "import subprocess", "import socket", "import ctypes", "import shutil", "import threading",
        "import multiprocessing", "import signal", "import importlib", "__import__('os')", "from os import system",
        "exec('import os')", "import sys\nsys.modules['x'] = 1\n__import__('subprocess')",
    ):
        r = judge(code, HID)
        assert r["status"] == "runtime_error" and r["hint_family"] == "import_blocked", code


def test_os_ja_carregado_nao_executa_comandos(judge):
    code = "import random\nrandom._os.system('echo pwned > /tmp/pwned')\nprint('ok')"
    assert status(judge, code)[0] == "runtime_error"
    assert not os.path.exists("/tmp/pwned")


def test_socket_bloqueado(judge):
    code = "import socket\ns = socket.socket()\ns.connect(('example.com', 80))"
    assert status(judge, code)[0] == "runtime_error"


def test_alocacao_enorme_da_memory_limit(judge):
    st, r = status(judge, "x = [0] * (10 ** 10)\n")
    assert st == "memory_limit"
    st, r = status(judge, "x = 'a' * (10 ** 10)\n")
    assert st == "memory_limit"


def test_stdout_forjado_nao_engana_funcao(judge):
    # o aluno escreve no stdout um "resultado" falso: só conta o valor devolvido pelo pipe com nonce
    code = (
        "import json\nprint(json.dumps({'ok': True, 'value': 999}))\n"
        "def f(x):\n    print('{\"ok\": true, \"value\": 3}')\n    return x + 1\n"
    )
    r = judge(code, [call([1], 3, False)], assinatura="f(x)")
    assert r["status"] == "wrong_answer" and r["passed"] == 0
    r = judge(code, [call([1], 2, False)], assinatura="f(x)")
    assert r["status"] == "accepted"


def test_escrever_no_pipe_de_resultado_nao_engana(judge):
    # tenta escrever lixo/forjado diretamente no fd do resultado (3) e ler o fd do nonce (4)
    code = (
        "import sys, random\n_os = random._os\n"
        "def f(x):\n"
        "    try:\n        _os.write(3, b'FORGED{\"ok\": true, \"value\": 3}\\n')\n    except Exception: pass\n"
        "    try:\n        _os.read(4, 16)\n    except Exception: pass\n"
        "    return x + 1\n"
    )
    # o lixo escrito antes do nonce invalida o resultado desta execução: nunca é aceite com o valor forjado
    r = judge(code, [call([1], 3, False)], assinatura="f(x)")
    assert r["status"] in ("wrong_answer", "runtime_error") and r["passed"] == 0


def test_nao_le_ambiente_do_servidor(judge):
    code = (
        "import random\nenv = dict(random._os.environ)\n"
        "try:\n    data = open('/proc/%d/environ' % random._os.getppid(), 'rb').read()\nexcept Exception:\n    data = b''\n"
        "print(set(env) <= {'LC_CTYPE'}, b'RUNNER_TOKEN' in data)\n"
    )
    r = judge(code, [prog("", "True False")])
    assert r["status"] == "accepted", r


def test_erros_ficam_com_a_linha_do_aluno(judge):
    r = judge("x = 1\ny = 2\nprint(x / 0)\n", [prog("", "", visible=True)])
    assert r["status"] == "runtime_error" and r["error"]["line"] == 3 and r["error"]["type"] == "ZeroDivisionError"
    assert r["hint_family"] == "zero_division"


def test_hidden_nunca_vaza(judge):
    r = judge("print(int(input()))", [prog("3.5\n", "SEGREDO", visible=False), prog("1\n", "1", visible=True)])
    blob = json.dumps(r)
    assert "SEGREDO" not in blob and "3.5" not in blob
    assert set(r["cases"][0]) == {"index", "visible", "status", "passed", "runtime_ms"}
    assert r["hint_family"] == "int_float_input" and r["error"] == {"type": "ValueError", "line": 1}
