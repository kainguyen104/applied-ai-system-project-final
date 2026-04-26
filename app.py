import os
import random

import streamlit as st

from logic_utils import (
    build_game_state_summary,
    configure_logging,
    generate_ai_hint,
    get_hot_cold_hint,
    get_range_for_difficulty,
    load_high_score,
    parse_guess,
    check_guess,
    run_agentic_hint_pipeline,
    save_high_score,
    update_score,
)


configure_logging()

st.set_page_config(page_title="Glitchy Guesser", page_icon="🎮")

st.title("🎮 Game Glitch Investigator")
st.caption("An AI-generated guessing game. Something is off.")

st.sidebar.header("Settings")

difficulty = st.sidebar.selectbox(
    "Difficulty",
    ["Easy", "Normal", "Hard"],
    index=1,
)

attempt_limit_map = {
    "Easy": 6,
    "Normal": 8,
    "Hard": 5,
}
attempt_limit = attempt_limit_map[difficulty]

low, high = get_range_for_difficulty(difficulty)


def reset_game_state(selected_difficulty: str) -> None:
    """Reset the active game round for the current difficulty."""

    st.session_state.secret = random.randint(low, high)
    st.session_state.attempts = 0
    st.session_state.score = 0
    st.session_state.status = "playing"
    st.session_state.attempt_log = []
    st.session_state.active_difficulty = selected_difficulty
    st.session_state.last_ai_hint = ""
    st.session_state.last_ai_sources = []
    st.session_state.last_ai_context = ""
    st.session_state.last_agent_steps = []

st.sidebar.caption(f"Range: {low} to {high}")
st.sidebar.caption(f"Attempts allowed: {attempt_limit}")
st.sidebar.caption("AI hints are generated from retrieved strategy notes and recent game state.")

st.sidebar.divider()
st.sidebar.subheader("🏆 High Score")
st.sidebar.metric("Best Score", load_high_score())
st.sidebar.metric("Current Score", st.session_state.get("score", 0))

if "active_difficulty" not in st.session_state:
    reset_game_state(difficulty)
elif st.session_state.active_difficulty != difficulty:
    reset_game_state(difficulty)

if "attempt_log" not in st.session_state:
    st.session_state.attempt_log = []

if "last_ai_hint" not in st.session_state:
    st.session_state.last_ai_hint = ""

if "last_ai_sources" not in st.session_state:
    st.session_state.last_ai_sources = []

if "last_ai_context" not in st.session_state:
    st.session_state.last_ai_context = ""

if "last_agent_steps" not in st.session_state:
    st.session_state.last_agent_steps = []

st.subheader("Make a guess")

st.caption(
    f"Game state: {build_game_state_summary(guess=0, outcome='pending', history=st.session_state.attempt_log, difficulty=difficulty, attempt_number=st.session_state.attempts, low=low, high=high)}"
)

st.info(
    f"Guess a number between {low} and {high}. "
    f"Attempts left: {max(0, attempt_limit - st.session_state.attempts)}"
)

with st.expander("Developer Debug Info"):
    st.write("Secret:", st.session_state.secret)
    st.write("Attempts:", st.session_state.attempts)
    st.write("Score:", st.session_state.score)
    st.write("Difficulty:", difficulty)
    st.write("Attempt log:", st.session_state.attempt_log)

raw_guess = st.text_input(
    "Enter your guess:",
    key=f"guess_input_{difficulty}"
)

col1, col2, col3 = st.columns(3)
with col1:
    submit = st.button("Submit Guess 🚀")
with col2:
    new_game = st.button("New Game 🔁")
with col3:
    show_hint = st.checkbox("Show hint", value=True)

if new_game:
    reset_game_state(difficulty)
    st.success("New game started.")
    st.rerun()

if st.session_state.status != "playing":
    if st.session_state.status == "won":
        st.success("You already won. Start a new game to play again.")
    else:
        st.error("Game over. Start a new game to try again.")
    st.stop()

if submit:
    st.session_state.attempts += 1
    attempt_number = st.session_state.attempts

    ok, guess_int, err = parse_guess(raw_guess)

    if not ok:
        st.session_state.attempt_log.append(
            {
                "attempt": attempt_number,
                "input": raw_guess,
                "parsed_guess": None,
                "outcome": "Invalid",
                "ai_hint": None,
                "confidence": None,
                "mode": "none",
                "sources": [],
                "error": err,
            }
        )
        st.error(err)
    else:
        secret = st.session_state.secret
        outcome = check_guess(guess_int, secret)

        ai_result = {
            "hint": None,
            "mode": "none",
            "confidence": None,
            "sources": [],
            "retrieved_context": "",
        }

        if show_hint:
            resolved_key = os.environ.get("ANTHROPIC_API_KEY")
            if resolved_key:
                ai_result = run_agentic_hint_pipeline(
                    difficulty=difficulty,
                    outcome=outcome,
                    guess=guess_int,
                    history=st.session_state.attempt_log,
                    low=low,
                    high=high,
                    attempt_number=attempt_number,
                    api_key=resolved_key,
                )
            else:
                ai_result = generate_ai_hint(
                    difficulty=difficulty,
                    outcome=outcome,
                    guess=guess_int,
                    history=st.session_state.attempt_log,
                    low=low,
                    high=high,
                    attempt_number=attempt_number,
                    api_key=None,
                )
                ai_result["steps"] = []
            st.session_state.last_ai_hint = ai_result["hint"]
            st.session_state.last_ai_sources = ai_result["sources"]
            st.session_state.last_ai_context = ai_result["retrieved_context"]
            st.session_state.last_agent_steps = ai_result.get("steps", [])
        else:
            st.session_state.last_ai_hint = ""
            st.session_state.last_ai_sources = []
            st.session_state.last_ai_context = ""
            st.session_state.last_agent_steps = []

        st.session_state.attempt_log.append(
            {
                "attempt": attempt_number,
                "input": raw_guess,
                "parsed_guess": guess_int,
                "outcome": outcome,
                "ai_hint": ai_result["hint"],
                "confidence": ai_result["confidence"],
                "mode": ai_result["mode"],
                "sources": ai_result["sources"],
                "error": None,
            }
        )

        # Challenge 4: color-coded directional hints
        hint_text = {"Win": "🎉 Correct!", "Too High": "📉 Go LOWER!", "Too Low": "📈 Go HIGHER!"}
        if show_hint:
            if outcome == "Win":
                st.success(hint_text[outcome])
            elif outcome == "Too High":
                st.error(hint_text[outcome])
            else:
                st.info(hint_text[outcome])

            # Hot/Cold proximity feedback
            hc_emoji, hc_label = get_hot_cold_hint(guess_int, secret)
            st.markdown(f"### {hc_emoji} {hc_label}")

            st.info(f"AI Coach: {ai_result['hint']}")
            st.caption(
                f"Confidence: {ai_result['confidence']:.2f} | Mode: {ai_result['mode']} | Sources: {', '.join(ai_result['sources']) or 'No docs'}"
            )

            with st.expander("AI Retrieval Evidence"):
                st.write(ai_result["retrieved_context"])

            if ai_result.get("steps"):
                with st.expander("Agent reasoning steps"):
                    for step in ai_result["steps"]:
                        st.markdown(f"**Step {step['step']} — {step['name']}:** {step['output']}")

        st.session_state.score = update_score(
            current_score=st.session_state.score,
            outcome=outcome,
            attempt_number=attempt_number,
        )

        if outcome == "Win":
            st.balloons()
            st.session_state.status = "won"
            save_high_score(st.session_state.score)
            st.success(
                f"You won! The secret was {st.session_state.secret}. "
                f"Final score: {st.session_state.score}"
            )
        else:
            if st.session_state.attempts >= attempt_limit:
                st.session_state.status = "lost"
                st.error(
                    f"Out of attempts! "
                    f"The secret was {st.session_state.secret}. "
                    f"Score: {st.session_state.score}"
                )

# Challenge 4: guess history summary table
if st.session_state.attempt_log:
    st.divider()
    st.subheader("📋 Guess History")
    rows = []
    for entry in st.session_state.attempt_log:
        if entry.get("error"):
            row = {
                "Attempt": entry["attempt"],
                "Input": entry["input"],
                "Result": "Invalid",
            }
            if show_hint:
                row.update(
                    {
                        "AI Hint": "—",
                        "Confidence": "—",
                        "Sources": "—",
                    }
                )
            rows.append(row)
        else:
            parsed_guess = entry["parsed_guess"]
            outcome = entry["outcome"]
            hc_emoji, hc_label = get_hot_cold_hint(parsed_guess, st.session_state.secret)
            row = {
                "Attempt": entry["attempt"],
                "Input": entry["input"],
                "Result": outcome,
                "Proximity": f"{hc_emoji} {hc_label}",
            }
            if show_hint:
                row.update(
                    {
                        "AI Hint": entry["ai_hint"] if entry["ai_hint"] else "—",
                        "Confidence": entry["confidence"] if entry["confidence"] is not None else "—",
                        "Sources": ", ".join(entry["sources"]) if entry["sources"] else "—",
                    }
                )
            rows.append(row)
    st.table(rows)

if show_hint and st.session_state.last_ai_hint:
    st.divider()
    st.subheader("🤖 AI Coach Summary")
    st.write(st.session_state.last_ai_hint)
    st.caption(
        f"Sources: {', '.join(st.session_state.last_ai_sources) if st.session_state.last_ai_sources else 'No docs'}"
    )

st.divider()
st.caption("Built by an AI that claims this code is production-ready.")
