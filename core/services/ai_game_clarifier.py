"""
Pre-build clarification.

Classifies the prompt into a genre and decides whether anything is ambiguous
enough to be worth asking about. The bar is deliberately high: a question is
only justified if two plausible answers would produce materially different
games. "create a pacman game" needs no questions; "make me a game" needs two.

Capped at 3 questions. Every question ships with options so the user clicks
rather than types.
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional

from services import game_genres

logger = logging.getLogger(__name__)

MAX_QUESTIONS = 3


def _parse_json(text: str) -> Optional[Dict]:
    if not text:
        return None
    text = text.strip()
    if text.startswith("```"):
        parts = text.split("```")
        text = parts[1] if len(parts) > 1 else text
        if text.startswith("json"):
            text = text[4:]
    if not text.strip().startswith("{"):
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            return None
        text = text[start:end + 1]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        try:
            return json.loads(re.sub(r",\s*([}\]])", r"\1", text))
        except json.JSONDecodeError:
            return None


class GameClarifier:
    def __init__(self, deepseek_client):
        self.ai = deepseek_client

    async def clarify(self, user_prompt: str) -> Dict[str, Any]:
        catalogue = "\n".join(
            f'  {g["id"]}: {g["label"]} (like {g["example"]}) — {g["feel"]}'
            for g in game_genres.options()
        )

        prompt = f"""A user wants a game built. Their request:

"{user_prompt}"

STEP 1 — Pick the closest genre from this list:
{catalogue}

STEP 2 — Decide whether you need to ask anything before building.

Ask a question ONLY if two plausible answers would produce materially
different games. Be strict. If the request already names a known game
("pacman", "flappy bird", "space invaders"), you know what to build — ask
NOTHING and return an empty questions array.

Ask at most {MAX_QUESTIONS}. Prefer 0. Never ask about art style, colours,
difficulty or platform — those are your decisions to make.

Good questions are about mechanics that change the structure of the game:
  - what the player actually does moment to moment
  - how the player wins or loses
  - whether there are enemies, and how they behave

Return JSON:
{{
  "genre": "<one id from the list>",
  "confidence": "high" | "medium" | "low",
  "title_guess": "a likely game title",
  "summary": "one sentence describing the game you would build",
  "questions": [
    {{
      "id": "short_snake_case_key",
      "question": "A direct question, under 12 words.",
      "why": "what this changes about the build, under 10 words",
      "options": [
        {{"value": "snake_case", "label": "Short answer", "detail": "under 12 words"}}
      ]
    }}
  ]
}}

Each question needs 2-4 options. Return ONLY the JSON."""

        try:
            response = await self.ai.generate(
                [{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=16000,
                thinking=False,   # classification is cheap; skip the reasoning cost
            )
            data = _parse_json(response.get("content", ""))
        except Exception as e:
            logger.warning(f"Clarifier failed, falling back to defaults: {e}")
            data = None

        if not data:
            return {
                "genre": game_genres.DEFAULT_GENRE,
                "confidence": "low",
                "summary": "",
                "title_guess": "",
                "questions": [],
                "options": game_genres.options(),
            }

        genre = game_genres.get(data.get("genre")).id
        questions = self._clean_questions(data.get("questions"))

        logger.info(
            f"🧭 Clarifier: genre={genre} confidence={data.get('confidence')} "
            f"questions={len(questions)}"
        )

        return {
            "genre": genre,
            "confidence": data.get("confidence", "medium"),
            "title_guess": data.get("title_guess", ""),
            "summary": data.get("summary", ""),
            "questions": questions,
            "options": game_genres.options(),
        }

    @staticmethod
    def _clean_questions(raw: Any) -> List[Dict[str, Any]]:
        if not isinstance(raw, list):
            return []
        cleaned: List[Dict[str, Any]] = []
        for item in raw[:MAX_QUESTIONS]:
            if not isinstance(item, dict) or not item.get("question"):
                continue
            options = [
                {
                    "value": str(o.get("value") or o.get("label", "")).strip(),
                    "label": str(o.get("label", "")).strip(),
                    "detail": str(o.get("detail", "")).strip(),
                }
                for o in (item.get("options") or [])
                if isinstance(o, dict) and (o.get("label") or o.get("value"))
            ][:4]
            # A question with fewer than two options is not a choice.
            if len(options) < 2:
                continue
            cleaned.append({
                "id": str(item.get("id") or f"q{len(cleaned) + 1}"),
                "question": str(item["question"]).strip(),
                "why": str(item.get("why", "")).strip(),
                "options": options,
            })
        return cleaned


def build_brief(user_prompt: str, genre_id: str, answers: Optional[Dict[str, str]]) -> str:
    """Fold the user's answers back into a single brief for the planner."""
    genre = game_genres.get(genre_id)
    parts = [f'Original request: "{user_prompt}"']
    if answers:
        chosen = "\n".join(f"- {k.replace('_', ' ')}: {v}" for k, v in answers.items() if v)
        if chosen:
            parts.append(f"The user chose:\n{chosen}")
    parts.append(game_genres.rules_block(genre))
    return "\n\n".join(parts)
