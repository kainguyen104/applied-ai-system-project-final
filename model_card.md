# Model Card: Game Glitch Investigator - AI Coaching System

## What this system does

This started as a simple number guessing game (pick Easy/Normal/Hard, guess a number, get Too High / Too Low feedback). The upgraded version adds an AI coach that gives contextual hints after each guess - not just "go lower" but something like "drop below 74, aim near 60 to cut the remaining range in half." The hint is based on retrieved strategy notes, the current game state, and optionally a live Claude model call.

## How I used AI during development

I used Claude throughout the project in three ways:

**For architecture decisions:** I asked Claude to help me think through whether to put game logic in `app.py` or a separate module. It pushed back on having everything in Streamlit - good call, because moving logic to `logic_utils.py` is what made every function independently testable without launching the UI.

**For debugging:** When the retriever kept returning the same documents every round, Claude helped me trace the bug to `_normalize_guesses()` reading the wrong dict key (`"guess"` instead of `"parsed_guess"`). The retriever was always seeing an empty history, so it treated every guess as a first guess.

**For prompting the model itself:** I iterated on the system prompt for `_call_claude_completion` to stay concise and coach-like. Early versions would explain their reasoning step by step, which felt like a lecture. The final version is constrained to one actionable line.

## One helpful suggestion, one flawed one

**Helpful:** Claude suggested structuring the agentic pipeline as three separate calls (Analyze → Plan → Generate) instead of one big prompt. This made each reasoning step visible in the UI and much easier to debug - if the hint was wrong, I could see exactly which step went sideways.

**Flawed:** An early version of `check_guess` that Claude drafted returned a tuple `("Win", "🎉 Correct!")`. The unit tests expected a plain string `"Win"`. I caught it immediately when pytest threw an assertion error, and corrected the function to return just the outcome string.

## Bias and known limitations

**Keyword retrieval isn't semantic.** The retriever scores documents by word overlap with the game state summary. A document with more matching words wins, even if a shorter document is more relevant. This means retrieval quality depends heavily on how the documents are worded.

**Confidence score is heuristic, not meaningful.** The confidence number rewards specific keywords like "narrow", "midpoint", "range". A hint that says "try 60" is actually useful but scores low because it lacks those words. Win-case hints consistently score around 0.49 even when they're perfectly correct - they just don't contain directional keywords.

**No memory across rounds.** The system treats each round as independent. A player who has been overshooting consistently across multiple games gets no different treatment than a first-time player.

**Fallback hints are deterministic.** Without an API key, every player in the same game state gets the exact same hint text. That's good for testability, but it means the "AI" in fallback mode is really just a formula.

## Testing results

Running `python evaluate_ai_system.py` tests 8 cases end-to-end:

- **8/8 cases pass** - every enhanced hint scores at least as well as the baseline
- **Average confidence: 0.76** - above the 0.50 threshold
- **All hints are leak-free** - the secret number never appears in any hint
- **Pass rate: 1.00** - above the 0.875 threshold

The winning case (correct guess) scores noticeably lower (conf ≈ 0.49) than Too High / Too Low cases (conf ≈ 0.77–0.81). This is a known limitation of the heuristic - not a problem with the hint itself.

## Few-shot specialization: before and after

Without few-shot examples, the live model sometimes responds with long explanations:
> *"Based on your guess of 74 being too high, you should consider that the target number must lie somewhere below 74. Given that your previous guesses were 61, 68, and 72, the number appears to be in the lower range..."*

With 5 coach-tone examples prepended to the prompt, the output tightens up:
> *"Drop below 74 - try around 60 to cut the remaining range in half."*

The examples train the model's tone without changing its underlying knowledge. Short, direct, no spoilers.

## What surprised me

The biggest surprise was how much a deterministic fallback improves everything else. Because the fallback always produces the same output for the same input, every test is repeatable, every evaluation case is predictable, and graders can run the full system without needing an API key. It made the project feel solid rather than flaky.

The second surprise: the `_normalize_guesses` bug. A single wrong dict key meant the retriever was blind to all history - it thought every guess was the first one. The fix was one line, but the symptom (same docs returned every round) was confusing until I traced it through.

## Future improvements

- Use embeddings instead of keyword overlap for retrieval - would fix cases where a relevant document uses different words than the query
- Add cross-round memory so the coach can notice patterns across multiple games
- Replace the heuristic confidence score with a model-graded quality score
- Add a difficulty-scaling hint style - Easy mode hints can be more encouraging, Hard mode hints more terse
