from logic_utils import check_guess, parse_guess, get_range_for_difficulty, update_score

# --- Original tests ---

def test_winning_guess():
    # If the secret is 50 and guess is 50, it should be a win
    result = check_guess(50, 50)
    assert result == "Win"

def test_guess_too_high():
    # If secret is 50 and guess is 60, hint should be "Too High"
    result = check_guess(60, 50)
    assert result == "Too High"

def test_guess_too_low():
    # If secret is 50 and guess is 40, hint should be "Too Low"
    result = check_guess(40, 50)
    assert result == "Too Low"

def test_guess_exact_match_always_wins():
    # Bug fix: original app cast secret to string on even attempts.
    # check_guess must return "Win" when guess equals the integer secret, not a string version of it.
    result = check_guess(75, 75)
    assert result == "Win"


# --- Challenge 1: Edge-case tests ---

# Edge case: negative number input
def test_parse_guess_negative_number():
    # Negative numbers are valid integers and should parse successfully
    ok, value, err = parse_guess("-5")
    assert ok is True
    assert value == -5
    assert err is None

# Edge case: decimal input is truncated to int
def test_parse_guess_decimal_truncated():
    # "3.7" should become 3 (truncated, not rounded)
    ok, value, err = parse_guess("3.7")
    assert ok is True
    assert value == 3
    assert err is None

# Edge case: extremely large number
def test_parse_guess_extremely_large_value():
    # Python handles arbitrary-precision integers, so this must succeed
    ok, value, err = parse_guess("999999999999")
    assert ok is True
    assert value == 999999999999
    assert err is None

# Edge case: empty string
def test_parse_guess_empty_string():
    ok, value, err = parse_guess("")
    assert ok is False
    assert value is None
    assert err is not None

# Edge case: None input
def test_parse_guess_none_input():
    ok, value, err = parse_guess(None)
    assert ok is False
    assert value is None
    assert err is not None

# Edge case: whitespace-only input is not a valid number
def test_parse_guess_whitespace_only():
    ok, value, err = parse_guess("   ")
    assert ok is False
    assert value is None
    assert err is not None

# Edge case: letters are rejected
def test_parse_guess_non_numeric_string():
    ok, value, err = parse_guess("abc")
    assert ok is False
    assert value is None
    assert err is not None

# Edge case: check_guess with both values at zero
def test_check_guess_zero_equals_zero():
    result = check_guess(0, 0)
    assert result == "Win"

# Edge case: guess is negative, secret is positive
def test_check_guess_negative_guess_vs_positive_secret():
    result = check_guess(-10, 50)
    assert result == "Too Low"

# Edge case: update_score with a very large attempt number should still award minimum 10 points
def test_update_score_large_attempt_still_awards_minimum():
    # At attempt 100, 100 - 10*(101) = -910, clamped to 10
    new_score = update_score(0, "Win", 100)
    assert new_score == 10

# Edge case: get_range_for_difficulty with unknown string falls back to (1, 100)
def test_get_range_unknown_difficulty_fallback():
    low, high = get_range_for_difficulty("Unknown")
    assert low == 1
    assert high == 100

# Edge case: Hard difficulty must be harder (wider range) than Normal
def test_hard_range_wider_than_normal():
    normal_low, normal_high = get_range_for_difficulty("Normal")
    hard_low, hard_high = get_range_for_difficulty("Hard")
    assert (hard_high - hard_low) > (normal_high - normal_low)
