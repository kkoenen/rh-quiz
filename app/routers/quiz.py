import random
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from datetime import datetime, timezone
from app.database import get_session
from app.models import (
    User, QuizAttempt, LeaderboardEntry,
    QuizRequest, QuizGenerated, QuizSubmit, QuizResult,
    QuizQuestion, AnswerOption,
)
from app.llm_client import generate_quiz
from app.scoring import calculate_score, check_subject_multiplier, MULTIPLIER_VALUE

router = APIRouter(prefix="/api/quiz", tags=["quiz"])


@router.post("/generate", response_model=QuizGenerated)
async def generate(data: QuizRequest):
    """Generate 3 quiz questions about the given subject via LLM."""
    subject = data.subject.strip()
    if not subject:
        raise HTTPException(status_code=400, detail="Subject cannot be empty")
    if len(subject) > 200:
        raise HTTPException(status_code=400, detail="Subject too long (max 200 chars)")

    try:
        quiz_data = await generate_quiz(subject)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))

    # Parse into response model and shuffle answer order
    questions = []
    for q in quiz_data["questions"]:
        answers_list = [
            AnswerOption(
                id=a["id"],
                text=a["text"],
                answer_class=a["class"],
                explanation=a.get("explanation", ""),
            )
            for a in q["answers"]
        ]
        random.shuffle(answers_list)
        questions.append(QuizQuestion(
            id=q["id"],
            question=q["question"],
            answers=answers_list,
        ))

    multiplier_active = check_subject_multiplier(subject)

    return QuizGenerated(
        subject=quiz_data.get("subject", subject),
        questions=questions,
        multiplier_active=multiplier_active,
    )


@router.post("/submit", response_model=QuizResult)
def submit(data: QuizSubmit, user_id: str, session: Session = Depends(get_session)):
    """Submit quiz answers and calculate score."""
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if len(data.answers) != 3:
        raise HTTPException(status_code=400, detail="Must submit exactly 3 answers")

    # Calculate score
    raw_score, details = calculate_score(
        data.questions,
        [{"question_id": a.question_id, "answer_id": a.answer_id} for a in data.answers],
    )

    # Check multiplier
    multiplier = MULTIPLIER_VALUE if check_subject_multiplier(data.subject) else 1.0
    total_score = int(raw_score * multiplier)

    # Save attempt
    attempt = QuizAttempt(
        user_id=user_id,
        subject=data.subject,
        score_raw=raw_score,
        multiplier=multiplier,
        score_total=total_score,
    )
    session.add(attempt)

    # Update leaderboard
    entry = session.get(LeaderboardEntry, user_id)
    if entry:
        entry.total_score += total_score
        entry.quizzes_taken += 1
        if total_score > entry.best_score:
            entry.best_score = total_score
        entry.last_updated = datetime.now(timezone.utc)
        entry.display_name = user.display_name
    else:
        entry = LeaderboardEntry(
            user_id=user_id,
            display_name=user.display_name,
            best_score=total_score,
            total_score=total_score,
            quizzes_taken=1,
        )
        session.add(entry)

    session.commit()

    return QuizResult(
        score_raw=raw_score,
        multiplier=multiplier,
        score_total=total_score,
        details=details,
    )
