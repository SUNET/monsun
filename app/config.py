import os

from pydantic_settings import BaseSettings

_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://user:password@localhost:5432/claw"
    secret_key: str = "change"
    media_dir: str = os.path.join(_PROJECT_DIR, "media")
    storage_secret: str = "storage"
    base_path: str = ""

    model_config = {"env_prefix": "CLAW_"}


settings = Settings()
