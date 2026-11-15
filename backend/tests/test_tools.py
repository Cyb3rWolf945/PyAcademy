# Testes das ferramentas validate_problems e check_i18n (passam nos exemplos e falham em fixtures partidas),
# e verificação de que o frontend nunca usa innerHTML.
import json

from app.config import settings
from app.tools import check_curriculum, check_i18n, validate_problems
from tests.fakes import FUNCAO_GERADOR, sync_local_post, write_problem


def test_validate_problems_passes_on_samples():
    assert validate_problems.validate(settings.problems_dir) == []


def test_validate_problems_fails_on_broken_fixture(tmp_path):
    sample = (settings.problems_dir / "block6" / "calcular-media.yaml").read_text(encoding="utf-8")
    (tmp_path / "ok.yaml").write_text(sample, encoding="utf-8")
    (tmp_path / "sem_en.yaml").write_text(sample.replace("calcular-media", "outro-id").replace("  en: The coffee average\n", ""), encoding="utf-8")
    (tmp_path / "dificuldade.yaml").write_text(sample.replace("calcular-media", "terceiro").replace("dificuldade: 1", "dificuldade: 9"), encoding="utf-8")
    errors = validate_problems.validate(tmp_path)
    assert len(errors) == 2 and not any("ok.yaml" in e for e in errors)


def test_check_i18n_passes_on_project():
    errs = check_i18n.run(settings.frontend_dir / "i18n", [settings.problems_dir, settings.problems_dir.parent / "content"])
    assert errs == []


def test_check_i18n_detects_missing_key(tmp_path):
    (tmp_path / "pt-PT.json").write_text(json.dumps({"a": "um", "b": "dois"}), encoding="utf-8")
    (tmp_path / "en.json").write_text(json.dumps({"a": "one"}), encoding="utf-8")
    errs = check_i18n.check_json(tmp_path)
    assert any("'b'" in e for e in errs)


def test_check_i18n_detects_missing_language_in_yaml(tmp_path):
    (tmp_path / "x.yaml").write_text("titulo:\n  pt: Olá\n  en: ''\nenunciado:\n  pt: só português\n", encoding="utf-8")
    errs = check_i18n.check_yaml(tmp_path)
    assert len(errs) == 2


def test_frontend_never_uses_innerhtml():
    """XSS: o frontend só escreve dados de utilizadores com textContent / createElement."""
    bad = []
    for p in settings.frontend_dir.rglob("*.js"):
        if "vendor" in p.parts or "dist" in p.parts:
            continue
        if any(s in p.read_text(encoding="utf-8") for s in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write")):
            bad.append(str(p))
    assert bad == []


def test_frontend_has_no_inline_scripts_or_styles():
    """CSP: sem <script> inline nem atributos style nos HTML."""
    import re
    for p in settings.frontend_dir.rglob("*.html"):
        if "vendor" in p.parts or "dist" in p.parts:
            continue
        html = p.read_text(encoding="utf-8")
        assert not re.search(r"<script(?![^>]*\bsrc=)[^>]*>", html), p
        assert not re.search(r"\sstyle=", html) and "<style" not in html, p
        assert not re.search(r"\son(click|load|error)=", html), p


def test_check_curriculum_passes_on_samples():
    assert check_curriculum.run(settings.problems_dir) == []


def test_check_curriculum_reports_future_material(tmp_path):
    ref = """
        exemplos: [{stdin: "", stdout: "1"}]
        testes: [{stdin: "", stdout: "1"}]
        solucao_referencia: |
          xs = [1, 2]
          total = sum(xs)
          xs.sort()
          print(max(xs), [x for x in xs])
          import random
        """
    write_problem(tmp_path, "cedo-demais", ref, bloco="5", regiao="rio")  # bloco 5: sem listas, sum, max, import random
    write_problem(tmp_path, "cedo-demais-7", ref, bloco="7", regiao="cidadela")
    rec = """
        assinatura: f(n)
        exemplos: [{args: [3], devolve: 6}]
        testes: [{args: [4], devolve: 24}]
        solucao_referencia: |
          def f(n):
              if n < 2:
                  return 1
              return n * f(n - 1)
        """
    write_problem(tmp_path, "recursao-cedo", rec, tipo="funcao", bloco="6", regiao="torre")
    write_problem(tmp_path, "recursao-ok", rec, tipo="funcao", bloco="6b", regiao="torre")
    write_problem(tmp_path, "livre", ref, bloco="mais_alem", regiao="ilhas")
    report = "\n".join(check_curriculum.run(tmp_path))
    assert "cedo-demais.yaml" in report and "recursao-cedo.yaml" in report
    assert "nó List" in report and "função sum()" in report and "função max()" in report and "método .sort()" in report
    assert "nó ListComp" in report and "import random" in report and "só é dado no bloco 7" in report
    assert "recursão" in report
    assert "recursao-ok" not in report and "livre.yaml" not in report
    # no bloco 7 só falham a compreensão e o import random
    seven = [line for line in report.splitlines() if "cedo-demais-7" in line]
    assert seven and all("ListComp" in line or "comprehension" in line or "random" in line for line in seven)


def test_validate_problems_runs_reference_solutions(tmp_path):
    ok = """
        exemplos: [{stdin: "2\\n", stdout: "4"}]
        testes: [{stdin: "3\\n", stdout: "6"}]
        comparacao: numeros
        solucao_referencia: |
          n = int(input())
          print(n * 2)
        """
    write_problem(tmp_path, "bom", ok)
    assert validate_problems.validate_all(tmp_path, sync_local_post) == []
    write_problem(tmp_path, "mau", ok.replace("n * 2", "n * 3"))
    errs = validate_problems.validate_all(tmp_path, sync_local_post)
    assert len(errs) == 2 and all("mau.yaml" in e and "não passa" in e for e in errs)  # pt e en


def test_validate_problems_localized_reference_and_bug(tmp_path):
    loc = """
        exemplos: [{stdin: "", stdout: {pt: "Olá", en: "Hello"}}]
        testes: [{stdin: "", stdout: {pt: "Olá", en: "Hello"}}]
        solucao_referencia: {pt: "print('Olá')", en: "print('Hello')"}
        """
    write_problem(tmp_path, "loc", loc)
    assert validate_problems.validate_all(tmp_path, sync_local_post) == []
    # solução em str com output localizado: falha numa das línguas
    write_problem(tmp_path, "loc-str", loc.replace("{pt: \"print('Olá')\", en: \"print('Hello')\"}", "\"print('Olá')\""))
    errs = validate_problems.validate_all(tmp_path, sync_local_post)
    assert len(errs) == 1 and "loc-str" in errs[0] and "[en]" in errs[0]
    (tmp_path / "loc-str.yaml").unlink()
    bug = """
        codigo_inicial: "print('Olá')"
        exemplos: [{stdin: "", stdout: {pt: "Olá", en: "Hello"}}]
        testes: [{stdin: "", stdout: {pt: "Olá", en: "Hello"}}]
        solucao_referencia: {pt: "print('Olá')", en: "print('Hello')"}
        """
    write_problem(tmp_path, "bug-mau", bug, tipo="bug")  # o codigo_inicial passa em pt: não é um bug
    errs = validate_problems.validate_all(tmp_path, sync_local_post)
    assert len(errs) == 1 and "codigo_inicial" in errs[0]


def test_validate_problems_algo_naive_must_time_out(tmp_path):
    base = FUNCAO_GERADOR.replace("comparacao: numeros", "comparacao: numeros\nlimite_tempo_s: 1\nnivel_algo: hard") + (
        "solucao_ingenua: |\n  def soma_lista(xs):\n      %s\n      return sum(xs)\n" "editorial: {pt: a, en: b}\n"
    )
    slow = "for _ in range(10 ** 9):\n          pass"
    write_problem(tmp_path, "algo-boa", base % slow, tipo="funcao", bloco="mais_alem", regiao="ilhas")
    assert validate_problems.validate_all(tmp_path, sync_local_post) == []
    write_problem(tmp_path, "algo-rapida", base % "pass", tipo="funcao", bloco="mais_alem", regiao="ilhas")
    errs = validate_problems.validate_all(tmp_path, sync_local_post)
    assert len(errs) == 1 and "algo-rapida" in errs[0] and "tempo limite" in errs[0]
