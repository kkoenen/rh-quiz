import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlmodel import SQLModel, Field


class User(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    display_name: str = Field(index=True, unique=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class QuizAttempt(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    user_id: str = Field(foreign_key="user.id", index=True)
    subject: str
    score_raw: int = 0
    multiplier: float = 1.0
    score_total: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class LeaderboardEntry(SQLModel, table=True):
    user_id: str = Field(foreign_key="user.id", primary_key=True)
    display_name: str
    best_score: int = 0
    total_score: int = 0
    quizzes_taken: int = 0
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# --- Pydantic request/response schemas ---

class UserCreate(SQLModel):
    display_name: str


class UserResponse(SQLModel):
    id: str
    display_name: str


class QuizRequest(SQLModel):
    subject: str


class AnswerOption(SQLModel):
    id: str
    text: str
    # class_ is reserved, using answer_class
    answer_class: str
    explanation: Optional[str] = None


class QuizQuestion(SQLModel):
    id: str
    question: str
    answers: list[AnswerOption]


class QuizGenerated(SQLModel):
    subject: str
    questions: list[QuizQuestion]
    multiplier_active: bool = False


class QuizSubmitAnswer(SQLModel):
    question_id: str
    answer_id: str


class QuizSubmit(SQLModel):
    subject: str
    questions: list[dict]  # full question data with classes
    answers: list[QuizSubmitAnswer]


class QuizResult(SQLModel):
    score_raw: int
    multiplier: float
    score_total: int
    details: list[dict]


class LeaderboardResponse(SQLModel):
    entries: list[LeaderboardEntry]
    last_updated: Optional[str] = None
