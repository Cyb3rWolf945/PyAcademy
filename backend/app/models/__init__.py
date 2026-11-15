# Importa todos os modelos para o Alembic e o SQLModel os conhecerem.
from app.models.audit import AuditLog
from app.models.problem import Problem
from app.models.session import AuthSession, LoginAttempt
from app.models.submission import HintUse, Job, Submission
from app.models.tournament import (
    Presence, Tournament, TournamentBonus, TournamentEvent, TournamentHintUse, TournamentPlayer, TournamentRound,
    TournamentSolve, TournamentSubmission, TournamentTeam,
)
from app.models.user import Role, SchoolClass, User

__all__ = ["AuditLog", "AuthSession", "HintUse", "Job", "LoginAttempt", "Presence", "Problem", "Role", "SchoolClass", "Submission", "User", "Tournament", "TournamentBonus", "TournamentEvent", "TournamentHintUse", "TournamentPlayer", "TournamentRound", "TournamentSolve", "TournamentSubmission", "TournamentTeam"]
