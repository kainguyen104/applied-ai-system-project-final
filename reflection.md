# 💭 Reflection: Game Glitch Investigator

Answer each question in 3 to 5 sentences. Be specific and honest about what actually happened while you worked. This is about your process, not trying to sound perfect.

## 1. What was broken when you started?

- What did the game look like the first time you ran it?
- List at least two concrete bugs you noticed at the start  
  (for example: "the secret number kept changing" or "the hints were backwards").

When I first ran the app, nothing worked. The game crashed right away and I couldn't even make a guess without errors showing up.

- Bug 1: the game crashed with NotImplementedError because check_guess in logic_utils.py was empty. I expected guessing the right number to win, but the function just threw an error instead.
- Bug 2: the hints were wrong every other guess. I guessed 60 when the secret was 50 and it still said go higher instead of go lower. Turns out the code was turning the secret into a string on even attempts, which broke the comparison.
- Bug 3: Hard mode was easier than Normal. Normal goes 1 to 100 but Hard only went 1 to 50, which means fewer numbers to guess from. The range was backwards for what "Hard" should mean.
---

## 2. How did you use AI as a teammate?

- Which AI tools did you use on this project (for example: ChatGPT, Gemini, Copilot)?
- Give one example of an AI suggestion that was correct (including what the AI suggested and how you verified the result).
- Give one example of an AI suggestion that was incorrect or misleading (including what the AI suggested and how you verified the result).

I am using Claude on this project. Claude correctly identified that all three tests failed because check_guess() in logic_utils.py was only a stub that raised NotImplementedError, and suggested moving the real logic from app.py into logic_utils.py. I verified this by reading both files and confirming the implementation existed in app.py, and after moving the logic and running pytest, all tests passed. However, Claude also suggested copying the check_guess function exactly, which returned a tuple like ("Win", "🎉 Correct!"). After checking tests/test_game_logic.py, I saw the tests expected only a single string such as "Win", so I modified the function accordingly to make the tests pass.
---

## 3. Debugging and testing your fixes

- How did you decide whether a bug was really fixed?
- Describe at least one test you ran (manual or using pytest)  
  and what it showed you about your code.
- Did AI help you design or understand any tests? How?

I decided a bug was fixed when the errors disappeared and the program worked correctly. I ran pytest tests/test_game_logic.py to check the check_guess() function. All three tests passed, showing the function returned the correct results. AI helped me understand the error message and locate where the missing implementation was.
---

## 4. What did you learn about Streamlit and state?

- In your own words, explain why the secret number kept changing in the original app.
- How would you explain Streamlit "reruns" and session state to a friend who has never used Streamlit?
- What change did you make that finally gave the game a stable secret number?

---
The secret number kept changing because Streamlit reruns the whole script whenever the user interacts with the app. This caused the number to regenerate each time. Session state works like memory that keeps values between reruns. I fixed the issue by storing the secret number in st.session_state.

## 5. Looking ahead: your developer habits

- What is one habit or strategy from this project that you want to reuse in future labs or projects?
  - This could be a testing habit, a prompting strategy, or a way you used Git.
- What is one thing you would do differently next time you work with AI on a coding task?
- In one or two sentences, describe how this project changed the way you think about AI generated code.

One habit I want to reuse is running tests often with pytest to confirm my fixes work. Next time, I will check AI suggestions more carefully instead of copying them directly. This project showed me that AI can help find bugs, but the developer still needs to verify the code.

---

## Challenge 5: AI Model Comparison

The bug I picked was the one where the secret number got cast to a string on every even-numbered attempt. This meant that when you guessed the right number on an even attempt, the comparison would fail because Python treats `50` and `"50"` as different values, so you could never win on those turns.

I asked both Claude and ChatGPT to fix it and compared their answers.

Claude explained the root cause right away — the type mismatch — and suggested removing the cast entirely instead of working around it. It also moved the comparison logic into a separate `check_guess` function in `logic_utils.py` so the code would be easier to test. The explanation walked through why odd and even attempts behaved differently, which helped me actually understand the bug rather than just copy a fix.

ChatGPT also caught the bug, but its fix was more narrow. It suggested writing `int(secret)` at the point of comparison instead of removing the bad cast upstream. That technically works, but it leaves the messy branching logic in place and does not clean anything up. The explanation was shorter and focused on making the error go away rather than explaining why it happened.

Claude gave the more useful answer here. The fix was cleaner, it came with a real explanation, and it pushed me toward better code structure. ChatGPT was faster to read but felt more like a patch than a solution.