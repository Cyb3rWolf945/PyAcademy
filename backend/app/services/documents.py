# PDFs do professor para a "Leitura recomendada": guardar o ficheiro, contar as páginas e desenhar cada página em PNG
# (pdftoppm, com cache no volume). Tocar na leitura abre o PDF mais recente do professor. O PDF nunca é enviado aos alunos.
import asyncio
import os
import re
import shutil
import tempfile
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.errors import ApiError
from app.models.academy import Document
from app.models.user import Role, SchoolClass, User

PAGE_WIDTH = 1200  # px: legível num portátil e leve no telemóvel
RENDER_TIMEOUT_S = 40
_render_slots = asyncio.Semaphore(2)  # no máximo 2 páginas a desenhar ao mesmo tempo por worker


def _pdf_path(doc_id: int) -> Path:
    return settings.docs_dir / f"{int(doc_id)}.pdf"


def _cache_dir(doc_id: int) -> Path:
    return settings.docs_dir / str(int(doc_id))


async def _run(*args: str, timeout: float) -> tuple[int, bytes, bytes]:
    proc = await asyncio.create_subprocess_exec(*args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        raise ApiError(504, "academy.doc_timeout") from None
    return proc.returncode, out, err


async def count_pages(path: Path) -> int:
    code, out, _ = await _run("pdfinfo", str(path), timeout=30)
    m = re.search(rb"^Pages:\s+(\d+)", out, re.M)
    if code != 0 or not m or int(m.group(1)) < 1:
        raise ApiError(422, "academy.doc_invalid")
    return int(m.group(1))


async def save_upload(db: AsyncSession, teacher: User, titulo: str, chunks) -> Document:
    """Guarda o corpo do pedido (PDF) num ficheiro temporário, valida-o e só depois cria o registo."""
    settings.docs_dir.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=settings.docs_dir, suffix=".upload")
    size, head = 0, b""
    try:
        with os.fdopen(fd, "wb") as f:
            async for chunk in chunks:
                if len(head) < 5:
                    head += chunk[:5]
                size += len(chunk)
                if size > settings.docs_max_bytes:
                    raise ApiError(413, "common.too_large")
                f.write(chunk)
        if not head.startswith(b"%PDF-"):
            raise ApiError(422, "academy.doc_not_pdf")
        pages = await count_pages(Path(tmp))
        doc = Document(teacher_id=teacher.id, titulo=titulo, pages=pages, size_bytes=size)
        db.add(doc)
        await db.flush()
        shutil.rmtree(_cache_dir(doc.id), ignore_errors=True)  # nunca servir páginas antigas de outro PDF com o mesmo id
        os.replace(tmp, _pdf_path(doc.id))
        await db.commit()
        return doc
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


async def delete(db: AsyncSession, teacher: User, doc_id: int) -> None:
    doc = await owned(db, teacher, doc_id)
    await db.delete(doc)  # as leituras ligadas a ele vão em cascata
    await db.commit()
    _pdf_path(doc_id).unlink(missing_ok=True)
    shutil.rmtree(_cache_dir(doc_id), ignore_errors=True)


async def owned(db: AsyncSession, teacher: User, doc_id: int) -> Document:
    doc = await db.get(Document, doc_id)
    if doc is None or doc.teacher_id != teacher.id:
        raise ApiError(404, "academy.doc_not_found")
    return doc


async def readable(db: AsyncSession, user: User, doc_id: int) -> Document:
    """O professor dono vê sempre; um aluno vê os documentos do professor da sua turma."""
    doc = await db.get(Document, doc_id)
    if doc is None:
        raise ApiError(404, "academy.doc_not_found")
    if user.role == Role.teacher:
        if doc.teacher_id != user.id:
            raise ApiError(404, "academy.doc_not_found")
        return doc
    cls = await db.get(SchoolClass, user.class_id) if user.class_id else None
    if cls is None or cls.teacher_id != doc.teacher_id:
        raise ApiError(404, "academy.doc_not_found")
    return doc


async def page_png(doc: Document, page: int) -> Path:
    """Caminho do PNG da página (desenha-o na primeira vez e guarda-o em cache)."""
    if not 1 <= page <= doc.pages:
        raise ApiError(404, "academy.doc_page_not_found")
    out = _cache_dir(doc.id) / f"{page}.png"
    if out.is_file():
        return out
    src = _pdf_path(doc.id)
    if not src.is_file():
        raise ApiError(404, "academy.doc_not_found")
    out.parent.mkdir(parents=True, exist_ok=True)
    async with _render_slots:
        if out.is_file():  # outro pedido desenhou-a enquanto esperávamos
            return out
        with tempfile.TemporaryDirectory(dir=out.parent) as tmpdir:
            prefix = Path(tmpdir) / "p"
            code, _, _ = await _run("pdftoppm", "-f", str(page), "-l", str(page), "-png", "-singlefile",
                                    "-scale-to-x", str(PAGE_WIDTH), "-scale-to-y", "-1", str(src), str(prefix), timeout=RENDER_TIMEOUT_S)
            made = prefix.with_suffix(".png")
            if code != 0 or not made.is_file():
                raise ApiError(422, "academy.doc_render_failed")
            os.replace(made, out)  # atómico: nunca se serve uma página a meio
    return out


def doc_view(doc: Document) -> dict:
    return {"id": doc.id, "titulo": doc.titulo, "pages": doc.pages, "size_bytes": doc.size_bytes, "created_at": doc.created_at.isoformat()}


# ---------------- o PDF que a "Leitura recomendada" abre ----------------
async def list_for_teacher(db: AsyncSession, teacher: User) -> list[dict]:
    docs = (await db.execute(select(Document).where(Document.teacher_id == teacher.id).order_by(Document.created_at.desc(), Document.id.desc()))).scalars().all()
    return [doc_view(d) for d in docs]


async def reading_for(db: AsyncSession, user: User) -> dict | None:
    """O PDF mais recente do professor (o do próprio, ou o do professor da turma do aluno), ou None se não houver."""
    if user.role == Role.teacher:
        teacher_id = user.id
    else:
        cls = await db.get(SchoolClass, user.class_id) if user.class_id else None
        if cls is None:
            return None
        teacher_id = cls.teacher_id
    doc = (await db.execute(select(Document).where(Document.teacher_id == teacher_id)
                            .order_by(Document.created_at.desc(), Document.id.desc()).limit(1))).scalars().first()
    return {"id": doc.id, "titulo": doc.titulo, "pages": doc.pages} if doc else None
