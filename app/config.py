import functools

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./certgen.db"
    storage_dir: str = "./storage"
    max_recipients_per_job: int = 1000

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


@functools.lru_cache
def get_settings() -> Settings:
    return Settings()
