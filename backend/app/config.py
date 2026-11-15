# Definições da app, lidas das variáveis de ambiente (.env via docker compose).
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]  # /app (ou a raiz do projeto)

LOCALES = ("pt-PT", "en")
THEMES = ("floresta",)  # os restantes temas chegam na fase 6


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    database_url: str = "postgresql+asyncpg://pyarena:pyarena@db:5432/pyarena"
    session_secret: str = "dev-only-secret"
    public_origin: str = "http://localhost:8080"
    cookie_secure: bool = True
    teacher_username: str = ""
    teacher_password: str = ""

    runner_url: str = ""  # vazio = sem runner (dispatcher desligado)
    runner_token: str = ""
    runner_timeout_s: float = 60
    submissions_per_minute: int = 6
    max_code_bytes: int = 20 * 1024
    dispatch_concurrency: int = 4  # chamadas simultâneas ao runner, por worker da app
    job_stale_s: int = 60
    job_max_attempts: int = 3

    session_days: int = 14
    max_body_bytes: int = 256 * 1024
    login_max_failures: int = 5
    join_max_failures: int = 30  # por IP: uma sala de aula partilha o mesmo IP público
    login_window_minutes: int = 15

    frontend_dir: Path = ROOT / "frontend"
    problems_dir: Path = ROOT / "backend" / "problems"


settings = Settings()
