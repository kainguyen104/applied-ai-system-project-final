"""Utility functions for Game Glitch Investigator.

This module contains all pure game logic so it can be tested independently
of the Streamlit UI layer in app.py.

Functions added / expanded with the help of Claude (Agent Mode):
- get_hot_cold_hint: provides proximity feedback for enhanced UI
- load_high_score / save_high_score: persist the all-time best score to disk
"""

HIGH_SCORE_FILE = "high_score.txt"


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
    # FIX: was 1-50, made it harder by changing to 1-200
    if difficulty == "Hard":
        return 1, 200
    return 1, 100


def parse_guess(raw: str) -> tuple:
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
    if raw is None or raw == "":
        return False, None, "Enter a guess."

    try:
        if "." in raw:
            value = int(float(raw))
        else:
            value = int(raw)
    except Exception:
        return False, None, "That is not a number."

    return True, value, None


# FIX: refactored from app.py into logic_utils.py using Claude. Returns plain string instead of tuple so tests pass.
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

    This function provides the "Hot/Cold" proximity feedback used by the
    enhanced UI layer in app.py (Challenge 4).  It does not depend on
    Streamlit, so it is straightforward to unit-test.

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

    Note:
        Added via Agent Mode (Claude) for Challenge 4 – Enhanced Game UI.
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

    Note:
        Added via Agent Mode (Claude) for Challenge 2 – High Score Tracker.
    """
    try:
        with open(HIGH_SCORE_FILE, "r") as f:
            return int(f.read().strip())
    except (FileNotFoundError, ValueError):
        return 0


def save_high_score(score: int) -> None:
    """Persist a new high score to disk if it beats the current saved record.

    The function reads the existing high score first and only writes when
    the supplied ``score`` is strictly greater, so the file is not
    overwritten unnecessarily.

    Args:
        score (int): The score to potentially save as the new high score.

    Note:
        Added via Agent Mode (Claude) for Challenge 2 – High Score Tracker.
    """
    current = load_high_score()
    if score > current:
        with open(HIGH_SCORE_FILE, "w") as f:
            f.write(str(score))
