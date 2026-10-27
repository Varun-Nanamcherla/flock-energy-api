import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    urja_base_url: str = "https://urja-ops.flockenergy.tech"
    urja_username: str = "operator@urja.local"
    urja_password: str = "urja-ops-2026"
    host: str = "0.0.0.0"
    port: int = 8000

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()