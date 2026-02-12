from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    ollama_base_url: str = "http://192.168.1.153:11434"
    ollama_model: str = "mistral:7b-instruct"
    db_path: str = "/data/quiz.db"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    admin_token: str = "SECRET"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    return Settings()
