import os
import yaml
from thefuzz import fuzz
from app.config import get_settings

settings = get_settings()

# Load subjects from YAML
_subjects_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "subjects.yaml")
with open(_subjects_file, "r") as f:
    _subjects_data = yaml.safe_load(f)
    MULTIPLIER_SUBJECTS: list[str] = _subjects_data.get("subjects", [])

# Score values per answer class
SCORE_MAP = {
    "correct": 10,
    "obviously_wrong": -5,
    "doubtful": 0,
}

MULTIPLIER_THRESHOLD = 70  # fuzzy match threshold (0-100)
MULTIPLIER_VALUE = 2.0


def check_subject_multiplier(subject: str) -> bool:
    """Check if the subject matches any multiplier subject using fuzzy matching."""
    subject_lower = subject.lower().strip()
    for s in MULTIPLIER_SUBJECTS:
        s_lower = s.lower().strip()
        # Exact containment check
        if subject_lower in s_lower or s_lower in subject_lower:
            return True
        # Fuzzy ratio check
        if fuzz.ratio(subject_lower, s_lower) >= MULTIPLIER_THRESHOLD:
            return True
        # Partial ratio for substring matching
        if fuzz.partial_ratio(subject_lower, s_lower) >= 85:
            return True
    return False


def calculate_score(
    questions: list[dict], answers: list[dict]
) -> tuple[int, list[dict]]:
    """
    Calculate the raw score for a set of answers.
    Returns (raw_score, details_list).
    """
    # Build lookup: question_id -> {answer_id -> answer_class}
    q_lookup = {}
    for q in questions:
        q_id = q["id"]
        q_lookup[q_id] = {}
        for a in q["answers"]:
            q_lookup[q_id][a["id"]] = a

    raw_score = 0
    details = []

    for ans in answers:
        q_id = ans["question_id"]
        a_id = ans["answer_id"]

        answer_data = q_lookup.get(q_id, {}).get(a_id)
        if not answer_data:
            details.append({
                "question_id": q_id,
                "answer_id": a_id,
                "points": 0,
                "class": "unknown",
                "error": "Answer not found",
            })
            continue

        a_class = answer_data.get("class", answer_data.get("answer_class", "doubtful"))
        points = SCORE_MAP.get(a_class, 0)
        raw_score += points

        correct_answer = None
        for a in q_lookup[q_id].values():
            ac = a.get("class", a.get("answer_class", ""))
            if ac == "correct":
                correct_answer = a
                break

        details.append({
            "question_id": q_id,
            "selected_answer_id": a_id,
            "selected_text": answer_data.get("text", ""),
            "selected_class": a_class,
            "points": points,
            "correct_answer_id": correct_answer["id"] if correct_answer else None,
            "correct_answer_text": correct_answer.get("text", "") if correct_answer else "",
            "explanation": answer_data.get("explanation", ""),
        })

    return raw_score, details
