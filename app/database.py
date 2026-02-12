import os
from sqlmodel import SQLModel, create_engine, Session
from app.config import get_settings

settings = get_settings()

# Ensure data directory exists
os.makedirs(os.path.dirname(settings.db_path), exist_ok=True)

engine = create_engine(
    f"sqlite:///{settings.db_path}",
    echo=False,
    connect_args={"check_same_thread": False},
)


def init_db():
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
