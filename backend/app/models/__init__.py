# Importa todos os modelos para o Alembic e o SQLModel os conhecerem.
from app.models.audit import AuditLog
from app.models.problem import Problem
from app.models.session import AuthSession, LoginAttempt
from app.models.user import Role, SchoolClass, User

__all__ = ["AuditLog", "AuthSession", "LoginAttempt", "Problem", "Role", "SchoolClass", "User"]
