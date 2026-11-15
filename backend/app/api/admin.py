# Rotas do professor: turmas, alunos e importação por CSV. Tudo auditado; só vê as suas turmas.
import csv
import io

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Auth, audit, origin_guard, teacher_auth
from app.api.schemas import ClassBulkDeleteIn, ClassIn, ImportIn, clean_display_name, clean_username
from app.db import get_db
from app.errors import ApiError
from app.models.user import Role, SchoolClass, User
from app.services import security

router = APIRouter(prefix="/api", dependencies=[Depends(origin_guard)])
MAX_IMPORT_ROWS = 200


def class_payload(c: SchoolClass) -> dict:
    return {"id": c.id, "name": c.name, "join_code": c.join_code, "created_at": c.created_at.isoformat()}


async def own_class(db: AsyncSession, class_id: int, teacher: User) -> SchoolClass:
    cls = await db.get(SchoolClass, class_id)
    if cls is None or cls.teacher_id != teacher.id:
        raise ApiError(404, "class.not_found")  # turma de outro professor = como se não existisse
    return cls


@router.post("/classes", status_code=201)
async def create_class(body: ClassIn, auth: Auth = Depends(teacher_auth), db: AsyncSession = Depends(get_db)):
    for _ in range(10):  # colisões de código são raríssimas; tenta de novo
        cls = SchoolClass(name=body.name, join_code=security.random_code(6), teacher_id=auth.user.id)
        db.add(cls)
        try:
            await db.flush()
            break
        except IntegrityError:
            await db.rollback()
    else:
        raise ApiError(500, "common.error")
    await audit(db, auth.user.id, "class.created", {"class_id": cls.id})
    await db.commit()
    return class_payload(cls)


@router.get("/classes")
async def list_classes(auth: Auth = Depends(teacher_auth), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(SchoolClass).where(SchoolClass.teacher_id == auth.user.id).order_by(SchoolClass.id))).scalars()
    return {"classes": [class_payload(c) for c in rows]}


@router.delete("/classes/{class_id}")
async def delete_class(class_id: int, auth: Auth = Depends(teacher_auth), db: AsyncSession = Depends(get_db)):
    cls = await own_class(db, class_id, auth.user)
    await audit(db, auth.user.id, "class.deleted", {"class_id": cls.id})
    await db.delete(cls)
    await db.commit()
    return {"ok": True}


@router.post("/classes/bulk-delete")
async def delete_classes(body: ClassBulkDeleteIn, auth: Auth = Depends(teacher_auth), db: AsyncSession = Depends(get_db)):
    classes = [await own_class(db, class_id, auth.user) for class_id in set(body.class_ids)]
    for cls in classes:
        await audit(db, auth.user.id, "class.deleted", {"class_id": cls.id})
        await db.delete(cls)
    await db.commit()
    return {"deleted": len(classes)}


@router.get("/classes/{class_id}/students")
async def list_students(class_id: int, auth: Auth = Depends(teacher_auth), db: AsyncSession = Depends(get_db)):
    await own_class(db, class_id, auth.user)
    rows = (await db.execute(select(User).where(User.class_id == class_id).order_by(User.display_name))).scalars()
    return {"students": [
        {"id": u.id, "username": u.username, "display_name": u.display_name, "must_change_password": u.must_change_password}
        for u in rows
    ]}


@router.post("/classes/{class_id}/students/import")
async def import_students(
    class_id: int, body: ImportIn, auth: Auth = Depends(teacher_auth), db: AsyncSession = Depends(get_db)
):
    """CSV `username,display_name`. As palavras-passe temporárias só são devolvidas aqui, uma vez."""
    await own_class(db, class_id, auth.user)
    rows = list(csv.reader(io.StringIO(body.csv)))
    if rows and [c.strip().lower() for c in rows[0][:1]] == ["username"]:
        rows = rows[1:]
    rows = [r for r in rows if any(c.strip() for c in r)]
    if len(rows) > MAX_IMPORT_ROWS:
        raise ApiError(422, "import.too_many_rows")
    created, errors = [], []
    for n, row in enumerate(rows, start=1):
        try:
            username = clean_username(row[0])
            display_name = clean_display_name(row[1] if len(row) > 1 and row[1].strip() else row[0])
        except (ValueError, IndexError):
            errors.append({"row": n, "error": "import.invalid_row"})
            continue
        temp = security.random_password()
        user = User(
            username=username, display_name=display_name, role=Role.student, class_id=class_id,
            password_hash=await security.hash_password(temp), must_change_password=True,
        )
        try:
            async with db.begin_nested():
                db.add(user)
                await db.flush()
        except IntegrityError:
            errors.append({"row": n, "error": "import.username_taken"})
            continue
        created.append({"username": username, "display_name": display_name, "temp_password": temp})
    await audit(db, auth.user.id, "students.imported", {"class_id": class_id, "created": len(created), "errors": len(errors)})
    await db.commit()
    return {"created": created, "errors": errors}
