# Testes do servidor HTTP do runner: token obrigatório, /health, /run, backpressure com muitos pedidos.
import json
import threading
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import pytest
import server as srv

TOKEN = "t" * 32


@pytest.fixture
def http(sandbox):
    s = srv.make_server(TOKEN, sandbox, "127.0.0.1", 0)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{s.server_address[1]}"
    s.shutdown()
    s.server_close()


def post(url, body, token=TOKEN):
    req = urllib.request.Request(url + "/run", json.dumps(body).encode(), {"X-Runner-Token": token})
    return json.loads(urllib.request.urlopen(req, timeout=30).read())


BODY = {"code": "print(1)", "cases": [{"visible": True, "stdin": "", "stdout": "1"}]}


def test_health_sem_token_e_run_exige_token(http):
    assert json.loads(urllib.request.urlopen(http + "/health").read())["status"] == "ok"
    with pytest.raises(urllib.error.HTTPError) as exc:
        post(http, BODY, token="errado")
    assert exc.value.code == 401
    assert post(http, BODY)["status"] == "accepted"


def test_pedido_invalido_da_400(http):
    with pytest.raises(urllib.error.HTTPError) as exc:
        post(http, {"code": "x", "cases": []})
    assert exc.value.code == 400


def test_muitos_pedidos_em_simultaneo_esperam_e_nao_falham(http):
    with ThreadPoolExecutor(12) as pool:
        results = list(pool.map(lambda _: post(http, BODY)["status"], range(24)))
    assert results == ["accepted"] * 24
