# Testes de regressão: o RUNNER_TOKEN nunca pode chegar ao código do aluno (nem por /proc), e o
# servidor, sendo o PID 1 no contentor, não pode acumular zombies.
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request

import pytest
from conftest import prog

import sandbox as sb_mod

TOKEN = "SEGREDO-do-runner-" + "x" * 24
RUNNER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SNOOP = r'''
import random
_os = random._os
found = []
def grab(path, mode="rb"):
    try:
        with open(path, mode) as f:
            return f.read()
    except Exception as e:
        return b"ERR:" + type(e).__name__.encode()
pids = [p for p in _os.listdir("/proc") if p.isdigit()]
for pid in pids:
    for name in ("environ", "cmdline"):
        found.append(grab("/proc/%s/%s" % (pid, name)))
found.append(grab("/proc/1/environ"))
found.append(grab("/proc/%d/environ" % _os.getppid()))
found.append(grab("/proc/self/../%d/environ" % _os.getppid()))
# /proc/<ppid>/mem e ficheiros do pai
mem = grab("/proc/%d/mem" % _os.getppid())
found.append(mem[:200])
print(b"\n".join(found).decode("utf-8", "replace"))
'''


@pytest.fixture
def real_server():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    proc = subprocess.Popen(
        [sys.executable, "-I", os.path.join(RUNNER_DIR, "server.py")],
        env={"RUNNER_TOKEN": TOKEN, "RUNNER_PORT": str(port), "RUNNER_CONCURRENCY": "2"},
        stdout=subprocess.DEVNULL,
    )
    url = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            urllib.request.urlopen(url + "/health", timeout=1)
            break
        except OSError:
            time.sleep(0.1)
    yield url, proc
    proc.terminate()
    proc.wait(timeout=10)


def run(url, code):
    body = {"code": code, "cases": [{"visible": True, "stdin": "", "stdout": "nunca-igual"}]}
    req = urllib.request.Request(url + "/run", json.dumps(body).encode(), {"X-Runner-Token": TOKEN})
    return json.loads(urllib.request.urlopen(req, timeout=30).read())


def test_token_nunca_aparece_no_output_do_aluno(real_server):
    url, _ = real_server
    r = run(url, SNOOP)
    assert r["status"] == "wrong_answer"
    blob = json.dumps(r)
    assert TOKEN not in blob and "SEGREDO-do-runner" not in blob
    # nem pelo erro/nem por uma tentativa de ler a memória do servidor
    r = run(url, "import random\nprint(open('/proc/%d/mem' % random._os.getppid(), 'rb').read(64))")
    assert r["status"] == "runtime_error" and r["error"]["type"] in ("PermissionError", "OSError")


def zombies_of(pid):
    out = []
    for name in os.listdir("/proc"):
        if name.isdigit():
            try:
                rest = open(f"/proc/{name}/stat").read().rsplit(")", 1)[1].split()
            except OSError:
                continue
            if rest[0] == "Z" and int(rest[1]) == pid:
                out.append(int(name))
    return out


def test_sem_zombies_depois_de_200_execucoes(sandbox):
    import evaluate
    for _ in range(200):
        evaluate.evaluate({"code": "print(1)", "cases": [prog("", "1")]}, sandbox)
    assert zombies_of(os.getpid()) == []


def test_reap_orphans_recolhe_so_os_nao_geridos():
    pid = os.fork()
    if pid == 0:
        os._exit(0)
    time.sleep(0.2)
    assert zombies_of(os.getpid()) == [pid]
    assert sb_mod.reap_orphans({pid}) == 0  # gerido por outro: não se toca
    assert sb_mod.reap_orphans(set()) == 1
    assert zombies_of(os.getpid()) == []
