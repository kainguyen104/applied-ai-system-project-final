"""Utility functions for Game Glitch Investigator.

This module contains the game rules, high-score persistence, and the AI hint
pipeline used by the Streamlit UI.
"""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any

try:
    import anthropic as _anthropic_sdk
    _ANTHROPIC_AVAILABLE = True
except ImportError:
    _ANTHROPIC_AVAILABLE = False


PROJECT_ROOT = Path(__file__).resolve().parent
ASSETS_DIR = PROJECT_ROOT / "assets"
HIGH_SCORE_FILE = PROJECT_ROOT / "high_score.txt"
STRATEGY_DOCS_FILE = ASSETS_DIR / "strategy_docs.json"


DEFAULT_STRATEGY_DOCS: list[dict[str, Any]] = [
    {
        "id": "binary-search",
        "source": "strategy-docs",
        "title": "Binary search strategy",
        "tags": ["higher", "lower", "midpoint", "range", "narrowing"],
        "text": (
            "Use midpoint reasoning to narrow the interval quickly. "
            "When a guess is too high, shift the upper bound down. When a guess is too low, shift the lower bound up."
        ),
    },
    {
        "id": "endgame",
        "source": "strategy-docs",
        "title": "Endgame discipline",
        "tags": ["late game", "attempts", "precision", "conservative"],
        "text": (
            "As attempts shrink, stop making wide jumps. Use the remaining range and the last feedback to make smaller, safer guesses."
        ),
    },
    {
        "id": "history-awareness",
        "source": "strategy-docs",
        "title": "History-aware guessing",
        "tags": ["history", "pattern", "previous guesses"],
        "text": (
            "Recent guesses are useful evidence. If the last few guesses cluster on one side, the next guess should move toward the opposite side of that cluster."
        ),
    },
    {
        "id": "confidence-rules",
        "source": "strategy-docs",
        "title": "Confidence rules",
        "tags": ["confidence", "guardrail", "non-spoiler"],
        "text": (
            "Give one concrete next step, avoid spoilers, and keep the tone coach-like. The best hint explains how to search, not the final answer."
        ),
    },
    {
        "id": "difficulty-adjustment",
        "source": "game-state",
        "title": "Difficulty adjustment heuristic",
        "tags": ["easy", "normal", "hard", "range width"],
        "text": (
            "Hard mode has a wider range, so the hint should emphasize range reduction and careful midpoint choices. Easy mode can be more direct and reassuring."
        ),
    },
]


logger = logging.getLogger(__name__)


FEW_SHOT_EXAMPLES = [
    {
        "input": "Guess 70 was too high. Range 1-100, Normal difficulty. Recent guesses: 50, 65, 70.",
        "output": "Drop below 70 — aim near 60 to cut the remaining range in half.",
    },
    {
        "input": "Guess 30 was too low. Range 1-100, Normal difficulty. Recent guesses: 10, 20, 30.",
        "output": "Move up past 30. The midpoint of 30-100 is around 65 — try there.",
    },
    {
        "input": "First guess, no history. Range 1-200, Hard difficulty.",
        "output": "Start at 100 — the exact midpoint. Any result cuts the search space in half immediately.",
    },
    {
        "input": "Guess 15 was too high. Range 1-20, Easy difficulty. Recent guesses: 10, 13, 15.",
        "output": "Almost there — try 12 or 13. You are narrowing down fast.",
    },
    {
        "input": "Guess 42 was correct. Win.",
        "output": "Well done. Lock in that midpoint habit and start a new round.",
    },
]


def _format_few_shot_block() -> str:
    lines = ["Here are examples of the coaching style to follow:\n"]
    for i, example in enumerate(FEW_SHOT_EXAMPLES, start=1):
        lines.append(f"Example {i}:")
        lines.append(f"Game state: {example['input']}")
        lines.append(f"Coach hint: {example['output']}\n")
    return "\n".join(lines)


def configure_logging(log_file: str | os.PathLike[str] | None = None) -> logging.Logger:
    """Configure application logging once and return the module logger."""

    if logging.getLogger().handlers:
        return logger

    log_path = Path(log_file) if log_file else PROJECT_ROOT / "logs" / "app.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )
    return logger


def _load_json_file(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as file_handle:
        return json.load(file_handle)


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _normalize_guesses(history: list[Any]) -> list[int]:
    normalized: list[int] = []
    for entry in history:
        if isinstance(entry, dict):
            value = entry.get("guess") or entry.get("parsed_guess")
            if isinstance(value, int):
                normalized.append(value)
        elif isinstance(entry, int):
            normalized.append(entry)
    return normalized


def load_strategy_docs() -> list[dict[str, Any]]:
    """Load retrieval documents from disk and fall back to embedded docs."""

    try:
        if STRATEGY_DOCS_FILE.exists():
            docs = _load_json_file(STRATEGY_DOCS_FILE)
            if isinstance(docs, list) and docs:
                return docs
    except (OSError, json.JSONDecodeError):
        logger.exception("Failed to load strategy docs from disk")
    return DEFAULT_STRATEGY_DOCS


def get_range_for_difficulty(difficulty: str) -> tuple:
    """Return the inclusive (low, high) number range for a given difficulty level.

    Args:
        difficulty (str): One of "Easy", "Normal", or "Hard".

    Returns:
        tuple[int, int]: A (low, high) pair representing the inclusive guess range.
            Defaults to (1, 100) for any unrecognised difficulty value.
    """
    if difficulty == "Easy":
        return 1, 20
    if difficulty == "Normal":
        return 1, 100
    if difficulty == "Hard":
        return 1, 200
    return 1, 100


def parse_guess(raw: str | None) -> tuple:
    """Parse user input into an integer guess.

    Accepts plain integer strings and decimal strings (decimal portion is
    truncated, not rounded).  Rejects empty, None, or non-numeric input.

    Args:
        raw (str | None): The raw string entered by the player.

    Returns:
        tuple[bool, int | None, str | None]: A three-element tuple where
            - element 0 (ok) is True when parsing succeeded.
            - element 1 (guess_int) is the parsed integer, or None on failure.
            - element 2 (error_message) is a human-readable error string on
              failure, or None on success.

    Examples:
        >>> parse_guess("42")
        (True, 42, None)
        >>> parse_guess("3.9")
        (True, 3, None)
        >>> parse_guess("abc")
        (False, None, 'That is not a number.')
    """
    if raw is None or str(raw).strip() == "":
        return False, None, "Enter a guess."

    candidate = str(raw).strip()

    try:
        if "." in candidate:
            value = int(float(candidate))
        else:
            value = int(candidate)
    except (TypeError, ValueError):
        return False, None, "That is not a number."

    return True, value, None


def check_guess(guess: int, secret: int) -> str:
    """Compare a player's guess against the secret number and return the outcome.

    Args:
        guess (int): The player's guessed integer.
        secret (int): The secret integer the player is trying to identify.

    Returns:
        str: One of three possible outcome strings:
            - "Win"      – guess exactly equals secret.
            - "Too High" – guess is greater than secret.
            - "Too Low"  – guess is less than secret.
    """
    if guess == secret:
        return "Win"
    if guess > secret:
        return "Too High"
    return "Too Low"


def update_score(current_score: int, outcome: str, attempt_number: int) -> int:
    """Update and return the player's score based on the result of a single guess.

    Scoring rules:
        - **Win**: awards ``100 - 10 * (attempt_number + 1)`` points,
          with a floor of 10 so winning is always worth something.
        - **Too High on an even attempt**: awards +5 (intentional quirk).
        - **Too High on an odd attempt**: deducts 5.
        - **Too Low**: always deducts 5.

    Args:
        current_score (int): The player's accumulated score before this guess.
        outcome (str): The result string from :func:`check_guess`:
            ``"Win"``, ``"Too High"``, or ``"Too Low"``.
        attempt_number (int): The 1-based index of the current attempt.

    Returns:
        int: The updated score after applying the outcome.
    """
    if outcome == "Win":
        points = 100 - 10 * (attempt_number + 1)
        if points < 10:
            points = 10
        return current_score + points

    if outcome == "Too High":
        if attempt_number % 2 == 0:
            return current_score + 5
        return current_score - 5

    if outcome == "Too Low":
        return current_score - 5

    return current_score


def get_hot_cold_hint(guess: int, secret: int) -> tuple:
    """Return an emoji and label describing how close the guess is to the secret.

    Args:
        guess (int): The player's guessed integer.
        secret (int): The secret integer.

    Returns:
        tuple[str, str]: A two-element tuple ``(emoji, label)`` where both
            elements are strings.  Example return values:

            - ``("🎯", "Bullseye!")``        – exact match
            - ``("🔥", "Scorching Hot!")``   – within 5
            - ``("🌡️", "Warm!")``            – within 15
            - ``("🌊", "Cool...")``           – within 30
            - ``("❄️", "Freezing Cold!")``   – more than 30 away
    """
    distance = abs(guess - secret)
    if distance == 0:
        return "🎯", "Bullseye!"
    if distance <= 5:
        return "🔥", "Scorching Hot!"
    if distance <= 15:
        return "🌡️", "Warm!"
    if distance <= 30:
        return "🌊", "Cool..."
    return "❄️", "Freezing Cold!"


def load_high_score() -> int:
    """Load the all-time high score from the ``high_score.txt`` file on disk.

    Returns:
        int: The stored high score, or ``0`` if the file does not exist or
            contains an invalid value.
    """
    try:
        with HIGH_SCORE_FILE.open("r", encoding="utf-8") as file_handle:
            return int(file_handle.read().strip())
    except (FileNotFoundError, ValueError, OSError):
        return 0


def save_high_score(score: int) -> None:
    """Persist a new high score to disk if it beats the current saved record.

    Args:
        score (int): The score to potentially save as the new high score.
    """
    current = load_high_score()
    if score > current:
        with HIGH_SCORE_FILE.open("w", encoding="utf-8") as file_handle:
            file_handle.write(str(score))


def summarize_recent_guesses(history: list[Any], limit: int = 3) -> str:
    """Summarize recent guesses for retrieval and prompt context."""

    guesses = _normalize_guesses(history)[-limit:]
    if not guesses:
        return "No prior numeric guesses yet."
    return f"Recent numeric guesses: {', '.join(str(value) for value in guesses)}."


def build_game_state_summary(
    guess: int,
    outcome: str,
    history: list[Any],
    difficulty: str,
    attempt_number: int,
    low: int,
    high: int,
) -> str:
    """Build a compact runtime summary used by the AI hint pipeline."""

    recent_guess_text = summarize_recent_guesses(history)
    range_width = high - low
    direction_clause = {
        "Win": "The player already found the number.",
        "Too High": f"The current guess {guess} was too high, so the next move should be lower.",
        "Too Low": f"The current guess {guess} was too low, so the next move should be higher.",
    }.get(outcome, "The player has not received directional feedback yet.")

    return (
        f"Difficulty: {difficulty}. Attempt number: {attempt_number}. Range: {low} to {high}. "
        f"Range width: {range_width}. {direction_clause} {recent_guess_text}"
    )


def retrieve_strategy_docs(
    difficulty: str,
    outcome: str,
    guess: int,
    history: list[Any],
    low: int,
    high: int,
    limit: int = 3,
) -> list[dict[str, Any]]:
    """Retrieve the most relevant strategy documents for the current game state."""

    docs = load_strategy_docs()
    recent_guesses = _normalize_guesses(history)
    recent_tokens = {"history", "previous", "guesses", "trend"} if recent_guesses else {"start", "beginning", "fresh"}

    state_text = build_game_state_summary(
        guess=guess,
        outcome=outcome,
        history=history,
        difficulty=difficulty,
        attempt_number=len(recent_guesses) + 1,
        low=low,
        high=high,
    )
    query_tokens = _tokenize(state_text) | recent_tokens

    scored_docs: list[tuple[float, dict[str, Any]]] = []
    for doc in docs:
        tags = doc.get("tags", []) if isinstance(doc.get("tags", []), list) else []
        doc_tokens = _tokenize(" ".join([
            str(doc.get("title", "")),
            str(doc.get("text", "")),
            " ".join(str(tag) for tag in tags),
        ]))
        overlap = len(doc_tokens & query_tokens)
        tag_overlap = len(set(str(tag).lower() for tag in tags) & query_tokens)
        score = overlap + tag_overlap * 1.5
        if doc.get("id") == "binary-search":
            score += 2.0
        if outcome == "Too High" and any(token in doc_tokens for token in {"lower", "midpoint", "narrowing"}):
            score += 1.0
        if outcome == "Too Low" and any(token in doc_tokens for token in {"higher", "midpoint", "narrowing"}):
            score += 1.0
        if difficulty == "Hard" and any(token in doc_tokens for token in {"hard", "precision", "range"}):
            score += 0.5
        if recent_guesses and any(token in doc_tokens for token in {"history", "trend", "previous"}):
            score += 0.75
        scored_docs.append((score, doc))

    scored_docs.sort(key=lambda item: item[0], reverse=True)
    top_docs = [doc for score, doc in scored_docs[:limit] if score > 0]
    if not top_docs:
        top_docs = docs[:limit]
    return top_docs


def format_retrieved_context(docs: list[dict[str, Any]]) -> str:
    """Format retrieved documents into compact prompt context."""

    if not docs:
        return "No supporting strategy notes were retrieved."
    lines = []
    for index, doc in enumerate(docs, start=1):
        lines.append(
            f"{index}. {doc.get('title', 'Untitled')} ({doc.get('source', 'unknown')}): {doc.get('text', '')}"
        )
    return "\n".join(lines)


def build_baseline_hint(outcome: str, guess: int | None = None) -> str:
    """Build a non-RAG baseline hint used by the evaluation harness."""

    if outcome == "Win":
        return "You found it. Start a new round when ready."
    if outcome == "Too High":
        if guess is None:
            return "Try a lower guess."
        return f"Try a lower guess than {guess}."
    if outcome == "Too Low":
        if guess is None:
            return "Try a higher guess."
        return f"Try a higher guess than {guess}."
    return "Use the current feedback to narrow the range."


def score_hint_quality(hint: str, outcome: str, docs: list[dict[str, Any]]) -> float:
    """Score how useful a hint appears using deterministic heuristics."""

    lower_hint = hint.lower().strip()
    hint_tokens = _tokenize(lower_hint)
    word_count = len(lower_hint.split())
    score = 0.0

    if outcome == "Win" and any(term in lower_hint for term in {"new round", "start", "again"}):
        score += 0.35
    if outcome == "Too High" and any(term in lower_hint for term in {"lower", "smaller", "below", "down"}):
        score += 0.35
    if outcome == "Too Low" and any(term in lower_hint for term in {"higher", "bigger", "above", "up"}):
        score += 0.35
    if any(term in lower_hint for term in {"midpoint", "half", "narrow", "range"}):
        score += 0.2
    if any(term in lower_hint for term in {"history", "previous", "recent", "pattern"}):
        score += 0.1

    if 10 <= word_count <= 28:
        score += 0.12
    elif word_count <= 40:
        score += 0.08
    elif word_count <= 55:
        score += 0.03
    else:
        score -= 0.05

    retrieval_keywords: set[str] = set()
    for doc in docs:
        retrieval_keywords.update(_tokenize(str(doc.get("title", ""))))
        for tag in doc.get("tags", []) if isinstance(doc.get("tags"), list) else []:
            retrieval_keywords.update(_tokenize(str(tag)))

    if retrieval_keywords:
        overlap_ratio = len(hint_tokens & retrieval_keywords) / max(len(retrieval_keywords), 1)
        score += min(0.18, overlap_ratio)

    if docs and any(doc.get("title", "").lower() in lower_hint for doc in docs):
        score += 0.05

    if "retrieved strategy notes suggest" in lower_hint:
        score -= 0.03

    if any(char.isdigit() for char in lower_hint):
        score += 0.04

    return max(0.0, min(score, 1.0))


def _call_claude_completion(
    prompt: str,
    api_key: str,
    model: str = "claude-haiku-4-5",
    timeout: int = 20,
) -> str:
    """Call Claude via the Anthropic SDK."""

    if not _ANTHROPIC_AVAILABLE:
        raise ImportError("anthropic package is not installed")
    client = _anthropic_sdk.Anthropic(api_key=api_key)
    message = client.messages.create(
        model=model,
        max_tokens=120,
        system=(
            "You are a concise game coach. Give one actionable, non-spoiler hint "
            "for a number guessing game. Do not reveal the secret number."
        ),
        messages=[{"role": "user", "content": prompt}],
    )
    content = message.content[0].text.strip()
    if not content:
        raise ValueError("Empty completion content returned by the API")
    return content


def _compose_hint_prompt(
    difficulty: str,
    outcome: str,
    guess: int,
    history: list[Any],
    low: int,
    high: int,
    attempt_number: int,
    retrieved_context: str,
    use_few_shot: bool = True,
) -> str:
    game_context = build_game_state_summary(
        guess=guess,
        outcome=outcome,
        history=history,
        difficulty=difficulty,
        attempt_number=attempt_number,
        low=low,
        high=high,
    )
    few_shot_block = _format_few_shot_block() + "\n" if use_few_shot else ""
    return (
        f"{few_shot_block}"
        f"Game context:\n{game_context}\n\n"
        f"Retrieved strategy notes:\n{retrieved_context}\n\n"
        "Write one concise, coach-like hint that helps the player make the next guess. "
        "Do not reveal the secret number, do not quote the strategy notes verbatim, and do not explain your reasoning step-by-step. "
        "If the current guess was too high, guide downward; if too low, guide upward; if the player is winning, reinforce the endgame discipline."
    )


def generate_ai_hint(
    difficulty: str,
    outcome: str,
    guess: int,
    history: list[Any],
    low: int,
    high: int,
    attempt_number: int,
    api_key: str | None = None,
) -> dict[str, Any]:
    """Generate an AI-assisted hint using retrieval plus optional model generation."""

    docs = retrieve_strategy_docs(
        difficulty=difficulty,
        outcome=outcome,
        guess=guess,
        history=history,
        low=low,
        high=high,
    )
    retrieved_context = format_retrieved_context(docs)
    prompt = _compose_hint_prompt(
        difficulty=difficulty,
        outcome=outcome,
        guess=guess,
        history=history,
        low=low,
        high=high,
        attempt_number=attempt_number,
        retrieved_context=retrieved_context,
    )

    hint_text = ""
    mode = "retrieval_fallback"
    used_model = False

    resolved_api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if resolved_api_key:
        try:
            hint_text = _call_claude_completion(prompt=prompt, api_key=resolved_api_key)
            used_model = True
            mode = "claude"
        except Exception:
            logger.exception("Claude hint generation failed, falling back to local synthesis")

    if not hint_text:
        recent_guesses = _normalize_guesses(history)
        midpoint = (low + high) // 2
        if outcome == "Too High":
            new_high = guess - 1
            mid = (low + new_high) // 2
            if recent_guesses:
                hint_text = f"Below {guess} — try around {mid} to cut the remaining range in half."
            else:
                hint_text = f"Too high. Start lower — {mid} splits the range from {low} to {new_high}."
        elif outcome == "Too Low":
            new_low = guess + 1
            mid = (new_low + high) // 2
            if recent_guesses:
                hint_text = f"Above {guess} — try around {mid} to narrow things down."
            else:
                hint_text = f"Too low. Move up — {mid} splits the range from {new_low} to {high}."
        elif outcome == "Win":
            hint_text = "Well done. Start a new round when ready."
        else:
            hint_text = f"Try near {midpoint} to cut the range in half."

    hint_text = " ".join(hint_text.split())
    if len(hint_text) > 280:
        hint_text = hint_text[:277].rstrip() + "..."

    confidence = score_hint_quality(hint_text, outcome, docs)
    if used_model:
        confidence = min(1.0, confidence + 0.2)
    if docs:
        confidence = min(1.0, confidence + 0.06)

    if not any(term in hint_text.lower() for term in {"lower", "higher", "midpoint", "range", "start", "new round"}):
        hint_text = f"{hint_text} Focus on narrowing the remaining range."

    return {
        "hint": hint_text,
        "mode": mode,
        "confidence": round(confidence, 2),
        "sources": [doc.get("title", "Untitled") for doc in docs],
        "retrieved_context": retrieved_context,
    }


def _agentic_fallback_steps(
    outcome: str,
    guess: int,
    history: list[Any],
    difficulty: str,
    low: int,
    high: int,
    attempt_number: int,
    docs: list[dict[str, Any]],
) -> tuple[str, str, str]:
    """Build deterministic fallback outputs for all 3 agentic steps (no API call)."""
    recent_guesses = _normalize_guesses(history)
    range_remaining = high - low

    trend_map = {"Too High": "too_high", "Too Low": "too_low", "Win": "win"}
    trend = trend_map.get(outcome, "unknown")

    if not recent_guesses:
        strategy = "first_guess"
    elif difficulty == "Hard":
        strategy = "hard_mode_patience"
    else:
        strategy = "binary_search"

    step1 = f"trend={trend}, range_remaining={range_remaining}, attempt={attempt_number}, strategy={strategy}"

    tag_map = {"Too High": "overshoot_recovery", "Too Low": "undershoot_recovery", "Win": "endgame_discipline"}
    selected_tag = tag_map.get(outcome, "binary_search")
    if difficulty == "Hard":
        selected_tag = f"{selected_tag} + hard_mode_patience"
    step2 = f"selected strategy tag = {selected_tag}"

    baseline_hint = build_baseline_hint(outcome, guess)
    strategy_summary = docs[0]["text"] if docs else "Use a simple narrowing strategy."
    if outcome == "Win":
        step3 = "Great work. Keep the endgame disciplined and start a new round when ready."
    else:
        step3 = f"{baseline_hint} {strategy_summary}"

    step3 = " ".join(step3.split())
    if len(step3) > 280:
        step3 = step3[:277].rstrip() + "..."

    return step1, step2, step3


def run_agentic_hint_pipeline(
    difficulty: str,
    outcome: str,
    guess: int,
    history: list[Any],
    low: int,
    high: int,
    attempt_number: int,
    api_key: str | None = None,
) -> dict[str, Any]:
    """Run the 3-step agentic hint pipeline: Analyze → Plan → Generate.

    Each step's output is stored in the returned ``steps`` list so the UI
    can display intermediate reasoning.  Falls back to deterministic local
    outputs when no API key is available.
    """
    docs = retrieve_strategy_docs(
        difficulty=difficulty,
        outcome=outcome,
        guess=guess,
        history=history,
        low=low,
        high=high,
    )
    retrieved_context = format_retrieved_context(docs)
    game_summary = build_game_state_summary(
        guess=guess,
        outcome=outcome,
        history=history,
        difficulty=difficulty,
        attempt_number=attempt_number,
        low=low,
        high=high,
    )

    steps: list[dict[str, Any]] = []
    hint_text = ""
    mode = "retrieval_fallback"

    resolved_api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")

    if resolved_api_key and _ANTHROPIC_AVAILABLE:
        fb1, fb2, fb3 = _agentic_fallback_steps(
            outcome, guess, history, difficulty, low, high, attempt_number, docs
        )

        # Step 1 — Analyze
        try:
            step1_output = _call_claude_completion(
                f"Game state: {game_summary}\n\n"
                "Analyze in one line. Output only: trend=<too_high|too_low|win>, "
                "range_remaining=<number>, strategy=<tag>",
                resolved_api_key,
            )
        except Exception:
            logger.exception("Agentic step 1 failed, using fallback")
            step1_output = fb1
        steps.append({"step": 1, "name": "Analyze", "output": step1_output})

        # Step 2 — Plan
        try:
            step2_output = _call_claude_completion(
                f"Analysis: {step1_output}\n"
                f"Available strategy tags: {', '.join(doc['id'] for doc in docs)}\n\n"
                "Select the single best strategy tag. Output only the tag name.",
                resolved_api_key,
            )
        except Exception:
            logger.exception("Agentic step 2 failed, using fallback")
            step2_output = fb2
        steps.append({"step": 2, "name": "Plan", "output": step2_output})

        # Step 3 — Generate
        try:
            hint_text = _call_claude_completion(
                f"Analysis: {step1_output}\n"
                f"Strategy: {step2_output}\n"
                f"Retrieved notes:\n{retrieved_context}\n\n"
                "Write one concise coach hint. Do not reveal the secret number.",
                resolved_api_key,
            )
            mode = "claude_agentic"
        except Exception:
            logger.exception("Agentic step 3 failed, using fallback")
            hint_text = fb3
        steps.append({"step": 3, "name": "Generate", "output": hint_text})

    else:
        step1_output, step2_output, hint_text = _agentic_fallback_steps(
            outcome, guess, history, difficulty, low, high, attempt_number, docs
        )
        steps = [
            {"step": 1, "name": "Analyze", "output": step1_output},
            {"step": 2, "name": "Plan", "output": step2_output},
            {"step": 3, "name": "Generate", "output": hint_text},
        ]

    hint_text = " ".join(hint_text.split())
    if len(hint_text) > 280:
        hint_text = hint_text[:277].rstrip() + "..."

    if not any(term in hint_text.lower() for term in {"lower", "higher", "midpoint", "range", "start", "new round"}):
        hint_text = f"{hint_text} Focus on narrowing the remaining range."

    confidence = score_hint_quality(hint_text, outcome, docs)
    if mode == "claude_agentic":
        confidence = min(1.0, confidence + 0.2)
    if docs:
        confidence = min(1.0, confidence + 0.06)

    return {
        "hint": hint_text,
        "mode": mode,
        "confidence": round(confidence, 2),
        "sources": [doc.get("title", "Untitled") for doc in docs],
        "retrieved_context": retrieved_context,
        "steps": steps,
    }
