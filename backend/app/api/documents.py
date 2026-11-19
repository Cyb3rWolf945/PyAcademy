# Rotas dos PDFs da Academia: o professor carrega PDFs; tocar na "Leitura recomendada" abre o mais recente.
# Alunos e professor veem as páginas como imagens (nunca se descarrega o PDF). Erros: {"error": "academy.<chave>"}.
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Auth, active_auth, audit, origin_guard, teacher_auth
from app.db import get_db
from app.errors import ApiError
from app.services import documents as svc

router = APIRouter(prefix="/api/academy", dependencies=[Depends(origin_guard)])


class TitleIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    titulo: str = Field(min_length=1, max_length=120)


@router.post("/documents", status_code=201)
async def upload(request: Request, titulo: str = Query(min_length=1, max_length=120), auth: Auth = Depends(teacher_auth),
                 db: AsyncSession = Depends(get_db)):
    """Corpo = o próprio PDF (Content-Type: application/pdf)."""
    if request.headers.get("content-type", "").split(";")[0].strip() != "application/pdf":
        raise ApiError(415, "academy.doc_not_pdf")
    name = " ".join(titulo.split())
    doc = await svc.save_upload(db, auth.user, name, request.stream())
    await audit(db, auth.user.id, "academy.document_uploaded", {"document_id": doc.id, "pages": doc.pages})
    await db.commit()
    return svc.doc_view(doc)


@router.patch("/documents/{doc_id}")
async def rename(doc_id: int, body: TitleIn, auth: Auth = Depends(teacher_auth), db: AsyncSession = Depends(get_db)):
    doc = await svc.owned(db, auth.user, doc_id)
    doc.titulo = " ".join(body.titulo.split())
    await db.commit()
    return svc.doc_view(doc)


@router.delete("/documents/{doc_id}")
async def remove(doc_id: int, auth: Auth = Depends(teacher_auth), db: AsyncSession = Depends(get_db)):
    await svc.delete(db, auth.user, doc_id)
    await audit(db, auth.user.id, "academy.document_deleted", {"document_id": doc_id})
    await db.commit()
    return {"ok": True}


@router.get("/documents")
async def list_documents(auth: Auth = Depends(teacher_auth), db: AsyncSession = Depends(get_db)):
    return {"documents": await svc.list_for_teacher(db, auth.user)}


@router.get("/documents/{doc_id}")
async def info(doc_id: int, auth: Auth = Depends(active_auth), db: AsyncSession = Depends(get_db)):
    doc = await svc.readable(db, auth.user, doc_id)
    return {"id": doc.id, "titulo": doc.titulo, "pages": doc.pages}


@router.get("/documents/{doc_id}/pages/{page}")
async def page(doc_id: int, page: int, auth: Auth = Depends(active_auth), db: AsyncSession = Depends(get_db)):
    doc = await svc.readable(db, auth.user, doc_id)
    path = await svc.page_png(doc, page)
    return FileResponse(path, media_type="image/png", headers={"Cache-Control": "private, max-age=3600", "X-Content-Type-Options": "nosniff"})
