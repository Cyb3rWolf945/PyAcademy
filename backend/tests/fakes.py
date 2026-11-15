# Ajudantes dos testes: um "runner" local (o mesmo código do runner, em processo) e criação de problemas YAML.
import asyncio
import os
import sys
import textwrap

sys.path.insert(0, os.environ.get("RUNNER_DIR", "/app/runner"))

import evaluate  # noqa: E402
from sandbox import Sandbox  # noqa: E402

_sandbox = None


def sandbox():
    global _sandbox
    if _sandbox is None:
        _sandbox = Sandbox(2)
    return _sandbox


async def local_post(path, body, timeout=None):
    fn = evaluate.evaluate if path == "/run" else evaluate.generate
    return await asyncio.to_thread(fn, body, sandbox())


def sync_local_post(path, body):
    return (evaluate.evaluate if path == "/run" else evaluate.generate)(body, sandbox())


BASE = """
id: {id}
titulo: {{pt: Teste, en: Test}}
tipo: {tipo}
bloco: "{bloco}"
regiao: {regiao}
dificuldade: 1
estado: aprovado
enunciado: {{pt: Enunciado, en: Statement}}
"""


def write_problem(dir_, name, body, **kw):
    """Escreve um YAML de problema com o cabeçalho comum + `body` (indentado como em YAML de topo)."""
    head = BASE.format(**{"id": name, "tipo": "programa", "bloco": "2", "regiao": "floresta", **kw})
    path = dir_ / f"{name}.yaml"
    path.write_text(head + textwrap.dedent(body), encoding="utf-8")
    return path


QUIZ = """
perguntas:
  - pergunta: {pt: "Qual é a constante?", en: "Which is the constant?"}
    opcoes: [{pt: "O preço", en: "The price"}, {pt: "O troco", en: "The change"}, {pt: "A hora", en: "The time"}]
    resposta: [0, 2]
  - pergunta: {pt: "Valor de soma?", en: "Value of soma?"}
    codigo: "soma = 1 + 2"
    resposta_texto: "3"
"""

FUNCAO_GERADOR = """
assinatura: soma_lista(xs)
exemplos:
  - {args: [[1, 2, 3]], devolve: 6}
testes:
  - {args: [[]], devolve: 0}
  - args_gerador: "[list(range(5000))]"
  - args_gerador: "[[random.Random(7).randint(1, 9) for _ in range(50)]]"
comparacao: numeros
solucao_referencia: |
  def soma_lista(xs):
      total = 0
      for x in xs:
          total = total + x
      return total
"""
