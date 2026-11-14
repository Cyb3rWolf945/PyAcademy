# Testes das ferramentas validate_problems e check_i18n (passam nos exemplos e falham em fixtures partidas),
# e verificação de que o frontend nunca usa innerHTML.
import json

from app.config import settings
from app.tools import check_i18n, validate_problems


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
