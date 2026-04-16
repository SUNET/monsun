import os

from pydantic_settings import BaseSettings

_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


WEAK_SECRETS = {"change", "storage", "secret", "change-me-storage-secret", "change-me-in-production", ""}
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://user:password@localhost:5432/claw"
    secret_key: str = "change"
    media_dir: str = os.path.join(_PROJECT_DIR, "media")
    storage_secret: str = "storage"
    base_path: str = ""

    model_config = {"env_prefix": "CLAW_"}


settings = Settings()


def validate_upload_extension(filename: str) -> str | None:
    """Return the lowercased extension if allowed, or None if rejected."""
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        return None
    return ext
