# Testes dos PDFs da "Leitura recomendada": só o professor carrega (e só PDFs), páginas servidas como PNG a quem tem
# acesso (professor dono e alunos da sua turma), a leitura abre o PDF mais recente e apagar limpa tudo.
import pytest

from app.config import settings
from app.models.user import Role
from tests.conftest import login

pytestmark = pytest.mark.asyncio


def tiny_pdf(pages: int = 3) -> bytes:
    """PDF mínimo válido com N páginas em branco (offsets da tabela xref calculados)."""
    kids = " ".join(f"{3 + i} 0 R" for i in range(pages))
    objs = ["<< /Type /Catalog /Pages 2 0 R >>", f"<< /Type /Pages /Kids [{kids}] /Count {pages} >>"]
    objs += ["<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 300] >>"] * pages
    out, offsets = b"%PDF-1.4\n", []
    for n, body in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{n} 0 obj\n{body}\nendobj\n".encode()
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{o:010d} 00000 n \n".encode() for o in offsets)
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return out


@pytest.fixture(autouse=True)
def _docs_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "docs_dir", tmp_path / "docs")


async def _setup(make_user, make_class, new_client):
    prof = await make_user("profdoc", Role.teacher)
    cls = await make_class(prof.id, code="DOCAAA")
    tc = new_client()
    th = await login(tc, "profdoc")
    await make_user("alunadoc", class_id=cls.id)
    sc = new_client()
    sh = await login(sc, "alunadoc")
    return tc, th, sc, sh


async def _upload(client, headers, data=None, ctype="application/pdf", titulo="Livro"):
    return await client.post(f"/api/academy/documents?titulo={titulo}", content=data if data is not None else tiny_pdf(),
                             headers={**headers, "Content-Type": ctype})


async def test_teacher_uploads_and_student_sees_pages(make_user, make_class, new_client):
    tc, th, sc, sh = await _setup(make_user, make_class, new_client)
    r = await _upload(tc, th)
    assert r.status_code == 201, r.text
    doc = r.json()
    assert doc["pages"] == 3 and doc["titulo"] == "Livro"
    p = await sc.get(f"/api/academy/documents/{doc['id']}/pages/2")
    assert p.status_code == 200 and p.headers["content-type"] == "image/png" and p.content[:8] == b"\x89PNG\r\n\x1a\n"
    assert "private" in p.headers["cache-control"]
    assert (await sc.get(f"/api/academy/documents/{doc['id']}/pages/4")).status_code == 404
    assert (await sc.get(f"/api/academy/documents/{doc['id']}/pages/0")).status_code == 404


async def test_only_teacher_uploads_and_only_pdfs(make_user, make_class, new_client):
    tc, th, sc, sh = await _setup(make_user, make_class, new_client)
    assert (await _upload(sc, sh)).status_code == 403
    assert (await _upload(tc, th, data=b"<html>not a pdf</html>")).status_code == 422
    assert (await _upload(tc, th, ctype="text/plain")).status_code == 415
    assert (await _upload(tc, th, data=b"%PDF-1.4 broken")).status_code == 422


async def test_other_class_cannot_read(make_user, make_class, new_client):
    tc, th, sc, sh = await _setup(make_user, make_class, new_client)
    doc = (await _upload(tc, th)).json()
    other = await make_user("outroprof", Role.teacher)
    cls2 = await make_class(other.id, code="DOCBBB", name="Outra")
    await make_user("intruso", class_id=cls2.id)
    ic = new_client()
    await login(ic, "intruso")
    assert (await ic.get(f"/api/academy/documents/{doc['id']}/pages/1")).status_code == 404
    oc = new_client()
    await login(oc, "outroprof")
    assert (await oc.get(f"/api/academy/documents/{doc['id']}/pages/1")).status_code == 404


async def test_reading_opens_newest_pdf_and_delete_cleans_up(make_user, make_class, new_client):
    tc, th, sc, sh = await _setup(make_user, make_class, new_client)
    sec = "m0-01-instrucoes"  # tem "Leitura recomendada"
    assert (await sc.get(f"/api/academy/sections/{sec}")).json()["leitura_doc"] is None  # ainda sem PDF: fica só o texto
    old = (await _upload(tc, th, titulo="Antigo")).json()
    new = (await _upload(tc, th, data=tiny_pdf(5), titulo="Livro")).json()
    assert [d["id"] for d in (await tc.get("/api/academy/documents")).json()["documents"]] == [new["id"], old["id"]]
    assert (await sc.get("/api/academy/documents")).status_code == 403
    view = (await sc.get(f"/api/academy/sections/{sec}")).json()
    assert view["leitura"] and view["leitura_doc"] == {"id": new["id"], "titulo": "Livro", "pages": 5}
    await sc.get(f"/api/academy/documents/{new['id']}/pages/1")
    assert (settings.docs_dir / f"{new['id']}.pdf").is_file() and (settings.docs_dir / str(new["id"]) / "1.png").is_file()
    assert (await sc.delete(f"/api/academy/documents/{new['id']}", headers=sh)).status_code == 403
    assert (await tc.delete(f"/api/academy/documents/{new['id']}", headers=th)).status_code == 200
    assert not (settings.docs_dir / f"{new['id']}.pdf").exists() and not (settings.docs_dir / str(new["id"])).exists()
    assert (await sc.get(f"/api/academy/sections/{sec}")).json()["leitura_doc"]["id"] == old["id"]  # volta ao anterior
