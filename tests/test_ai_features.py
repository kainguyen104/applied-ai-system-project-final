from logic_utils import (
    FEW_SHOT_EXAMPLES,
    _compose_hint_prompt,
    build_baseline_hint,
    build_game_state_summary,
    format_retrieved_context,
    generate_ai_hint,
    load_strategy_docs,
    retrieve_strategy_docs,
    run_agentic_hint_pipeline,
    score_hint_quality,
)


def test_load_strategy_docs_returns_documents():
    docs = load_strategy_docs()
    assert isinstance(docs, list)
    assert len(docs) >= 3
    assert all("title" in doc for doc in docs)


def test_build_game_state_summary_mentions_difficulty_and_history():
    summary = build_game_state_summary(
        guess=74,
        outcome="Too High",
        history=[61, 68, 72],
        difficulty="Normal",
        attempt_number=4,
        low=1,
        high=100,
    )
    assert "Difficulty: Normal" in summary
    assert "Recent numeric guesses" in summary
    assert "too high" in summary.lower()


def test_generate_ai_hint_fallback_is_contextual():
    result = generate_ai_hint(
        difficulty="Normal",
        outcome="Too High",
        guess=74,
        history=[61, 68, 72],
        low=1,
        high=100,
        attempt_number=4,
        api_key=None,
    )
    assert result["mode"] == "retrieval_fallback"
    assert result["hint"]
    assert result["confidence"] >= 0.0
    assert any(term in result["hint"].lower() for term in ["lower", "narrow", "range"])


def test_agentic_pipeline_returns_steps():
    result = run_agentic_hint_pipeline(
        difficulty="Normal",
        outcome="Too High",
        guess=74,
        history=[61, 68, 72],
        low=1,
        high=100,
        attempt_number=4,
        api_key=None,
    )
    assert "steps" in result
    assert len(result["steps"]) == 3
    assert result["steps"][0]["name"] == "Analyze"
    assert result["steps"][1]["name"] == "Plan"
    assert result["steps"][2]["name"] == "Generate"
    assert result["hint"]


def test_few_shot_prompt_contains_examples():
    docs = retrieve_strategy_docs("Normal", "Too High", 74, [61, 68, 72], 1, 100)
    context = format_retrieved_context(docs)
    prompt_with = _compose_hint_prompt(
        "Normal", "Too High", 74, [61, 68, 72], 1, 100, 4, context, use_few_shot=True
    )
    prompt_without = _compose_hint_prompt(
        "Normal", "Too High", 74, [61, 68, 72], 1, 100, 4, context, use_few_shot=False
    )
    assert len(prompt_with) > len(prompt_without)
    assert FEW_SHOT_EXAMPLES[0]["output"] in prompt_with
    assert FEW_SHOT_EXAMPLES[0]["output"] not in prompt_without


def test_enhanced_hint_scores_at_least_baseline():
    docs = retrieve_strategy_docs(
        difficulty="Hard",
        outcome="Too Low",
        guess=128,
        history=[101, 112, 121],
        low=1,
        high=200,
    )
    baseline = build_baseline_hint("Too Low", 128)
    enhanced = generate_ai_hint(
        difficulty="Hard",
        outcome="Too Low",
        guess=128,
        history=[101, 112, 121],
        low=1,
        high=200,
        attempt_number=5,
        api_key=None,
    )
    baseline_score = score_hint_quality(baseline, "Too Low", docs)
    enhanced_score = score_hint_quality(enhanced["hint"], "Too Low", docs)
    assert enhanced_score >= baseline_score
