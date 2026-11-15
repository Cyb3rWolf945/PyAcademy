# Fixtures dos testes do runner: um Sandbox real (zygotes) partilhado e um ajudante `judge`.
# Correm na imagem da app (`docker compose run --rm app pytest`) ou na do runner (stage "test").
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import evaluate  # noqa: E402
from sandbox import Sandbox  # noqa: E402


@pytest.fixture(scope="session")
def sandbox():
    sb = Sandbox(2)
    yield sb
    sb.close()


@pytest.fixture
def judge(sandbox):
    def _judge(code, cases, **kw):
        return evaluate.evaluate(dict(code=code, cases=cases, **kw), sandbox)
    return _judge


def prog(stdin, stdout, visible=True):
    return {"visible": visible, "stdin": stdin, "stdout": stdout}


def call(args, devolve, visible=True):
    return {"visible": visible, "args": args, "devolve": devolve}
