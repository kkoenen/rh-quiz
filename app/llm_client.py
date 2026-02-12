import json
import re
import httpx
from app.config import get_settings

settings = get_settings()

SYSTEM_PROMPT = "You generate quiz questions as strict JSON only. No prose. No markdown. No code fences."

USER_PROMPT_TEMPLATE = """Create exactly 3 multiple choice questions about: "{subject}".

Each question must have exactly 4 answer options.
Exactly one option is correct, exactly one option is obviously wrong, and the other two must be plausible and cause doubt.

Questions should be concise and unambiguous.
Avoid trick questions that hinge on wording rather than knowledge.
No personally identifying questions.
Keep the difficulty "professional but accessible".

Return ONLY valid JSON in this exact schema (no other text):
{{
  "subject": "{subject}",
  "questions": [
    {{
      "id": "q1",
      "question": "...",
      "answers": [
        {{"id": "q1a1", "text": "...", "class": "correct", "explanation": "..."}},
        {{"id": "q1a2", "text": "...", "class": "obviously_wrong", "explanation": "..."}},
        {{"id": "q1a3", "text": "...", "class": "doubtful", "explanation": "..."}},
        {{"id": "q1a4", "text": "...", "class": "doubtful", "explanation": "..."}}
      ]
    }},
    {{
      "id": "q2",
      "question": "...",
      "answers": [
        {{"id": "q2a1", "text": "...", "class": "correct", "explanation": "..."}},
        {{"id": "q2a2", "text": "...", "class": "obviously_wrong", "explanation": "..."}},
        {{"id": "q2a3", "text": "...", "class": "doubtful", "explanation": "..."}},
        {{"id": "q2a4", "text": "...", "class": "doubtful", "explanation": "..."}}
      ]
    }},
    {{
      "id": "q3",
      "question": "...",
      "answers": [
        {{"id": "q3a1", "text": "...", "class": "correct", "explanation": "..."}},
        {{"id": "q3a2", "text": "...", "class": "obviously_wrong", "explanation": "..."}},
        {{"id": "q3a3", "text": "...", "class": "doubtful", "explanation": "..."}},
        {{"id": "q3a4", "text": "...", "class": "doubtful", "explanation": "..."}}
      ]
    }}
  ]
}}"""


def _extract_json(text: str) -> dict:
    """Extract JSON from LLM response, handling markdown fences and stray text."""
    # Try direct parse first
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try extracting from code fences
    fence_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if fence_match:
        try:
            return json.loads(fence_match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Try finding first { to last }
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace != -1:
        try:
            return json.loads(text[first_brace : last_brace + 1])
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not extract valid JSON from LLM response: {text[:200]}...")


def _validate_quiz(data: dict) -> dict:
    """Validate the quiz JSON structure and fix common issues."""
    if "questions" not in data:
        raise ValueError("Missing 'questions' key in response")

    questions = data["questions"]
    if len(questions) != 3:
        raise ValueError(f"Expected 3 questions, got {len(questions)}")

    for i, q in enumerate(questions):
        if "answers" not in q:
            raise ValueError(f"Question {i+1} missing 'answers'")
        if len(q["answers"]) != 4:
            raise ValueError(f"Question {i+1} has {len(q['answers'])} answers, expected 4")

        classes = [a.get("class") for a in q["answers"]]
        if classes.count("correct") != 1:
            raise ValueError(f"Question {i+1}: must have exactly 1 correct answer")
        if classes.count("obviously_wrong") != 1:
            raise ValueError(f"Question {i+1}: must have exactly 1 obviously_wrong answer")
        if classes.count("doubtful") != 2:
            raise ValueError(f"Question {i+1}: must have exactly 2 doubtful answers")

    return data


async def generate_quiz(subject: str, max_retries: int = 3) -> dict:
    """Call Ollama to generate a quiz. Retries on parse/validation failure."""
    url = f"{settings.ollama_base_url}/api/generate"
    prompt = USER_PROMPT_TEMPLATE.format(subject=subject)

    last_error = None
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    url,
                    json={
                        "model": settings.ollama_model,
                        "prompt": prompt,
                        "system": SYSTEM_PROMPT,
                        "stream": False,
                        "options": {
                            "temperature": 0.7,
                            "num_predict": 2048,
                        },
                    },
                )
                response.raise_for_status()
                result = response.json()
                raw_text = result.get("response", "")
                data = _extract_json(raw_text)
                validated = _validate_quiz(data)
                return validated
        except Exception as e:
            last_error = e
            continue

    raise RuntimeError(f"Failed to generate valid quiz after {max_retries} attempts: {last_error}")
