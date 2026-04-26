"""Batch evaluation harness for the AI hint pipeline.

Runs 8 test cases and prints a PASS/FAIL report with threshold checks.
Exit code 1 on overall failure so CI can use the signal.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from statistics import mean

from logic_utils import (
    build_baseline_hint,
    generate_ai_hint,
    retrieve_strategy_docs,
    score_hint_quality,
)


EVALUATION_CASES = [
    {
        "name": "early_too_high",
        "difficulty": "Normal",
        "guess": 74,
        "secret": 52,
        "outcome": "Too High",
        "history": [61, 68, 72],
        "low": 1,
        "high": 100,
        "attempt_number": 4,
    },
    {
        "name": "early_too_low",
        "difficulty": "Normal",
        "guess": 18,
        "secret": 47,
        "outcome": "Too Low",
        "history": [11, 14, 16],
        "low": 1,
        "high": 100,
        "attempt_number": 3,
    },
    {
        "name": "hard_mode_midgame",
        "difficulty": "Hard",
        "guess": 128,
        "secret": 149,
        "outcome": "Too Low",
        "history": [101, 112, 121],
        "low": 1,
        "high": 200,
        "attempt_number": 5,
    },
    {
        "name": "winning_case",
        "difficulty": "Easy",
        "guess": 12,
        "secret": 12,
        "outcome": "Win",
        "history": [6, 9, 11],
        "low": 1,
        "high": 20,
        "attempt_number": 4,
    },
    {
        "name": "normal_first_guess",
        "difficulty": "Normal",
        "guess": 50,
        "secret": 73,
        "outcome": "Too Low",
        "history": [],
        "low": 1,
        "high": 100,
        "attempt_number": 1,
    },
    {
        "name": "hard_mode_early",
        "difficulty": "Hard",
        "guess": 100,
        "secret": 163,
        "outcome": "Too Low",
        "history": [],
        "low": 1,
        "high": 200,
        "attempt_number": 1,
    },
    {
        "name": "easy_mode_endgame",
        "difficulty": "Easy",
        "guess": 15,
        "secret": 17,
        "outcome": "Too Low",
        "history": [5, 8, 10, 13],
        "low": 1,
        "high": 20,
        "attempt_number": 5,
    },
    {
        "name": "hard_mode_cluster_high",
        "difficulty": "Hard",
        "guess": 155,
        "secret": 80,
        "outcome": "Too High",
        "history": [145, 150, 152],
        "low": 1,
        "high": 200,
        "attempt_number": 5,
    },
]

PASS_THRESHOLDS = {
    "min_confidence": 0.50,
    "min_improvement": 0.00,
    "min_pass_rate": 0.875,
}


@dataclass
class CaseResult:
    name: str
    baseline_score: float
    enhanced_score: float
    improvement: float
    confidence: float
    leak_free: bool
    mode: str
    passed: bool


def run_evaluation() -> None:
    print("AI Hint Evaluation Harness")
    print("=" * 60)
    print("CASE RESULTS")
    print()

    results: list[CaseResult] = []

    for case in EVALUATION_CASES:
        docs = retrieve_strategy_docs(
            difficulty=case["difficulty"],
            outcome=case["outcome"],
            guess=case["guess"],
            history=case["history"],
            low=case["low"],
            high=case["high"],
        )
        baseline_hint = build_baseline_hint(case["outcome"], case["guess"])
        enhanced = generate_ai_hint(
            difficulty=case["difficulty"],
            outcome=case["outcome"],
            guess=case["guess"],
            history=case["history"],
            low=case["low"],
            high=case["high"],
            attempt_number=case["attempt_number"],
            api_key=None,
        )

        baseline_score = score_hint_quality(baseline_hint, case["outcome"], docs)
        enhanced_score = score_hint_quality(enhanced["hint"], case["outcome"], docs)
        improvement = enhanced_score - baseline_score
        leak_free = str(case["secret"]) not in enhanced["hint"]
        passed = leak_free and enhanced_score >= baseline_score

        result = CaseResult(
            name=case["name"],
            baseline_score=baseline_score,
            enhanced_score=enhanced_score,
            improvement=improvement,
            confidence=enhanced["confidence"],
            leak_free=leak_free,
            mode=enhanced["mode"],
            passed=passed,
        )
        results.append(result)

        status = "PASS" if passed else "FAIL"
        leak_symbol = "+" if leak_free else "!"
        print(
            f"[{status}] {case['name']:<26} "
            f"baseline={baseline_score:.2f} enhanced={enhanced_score:.2f} "
            f"improvement={improvement:+.2f} conf={enhanced['confidence']:.2f} "
            f"leak_free={leak_symbol}"
        )

    pass_count = sum(1 for r in results if r.passed)
    total = len(results)
    avg_enhanced = mean(r.enhanced_score for r in results)
    avg_confidence = mean(r.confidence for r in results)
    pass_rate = pass_count / total

    print()
    print("SUMMARY")
    print("-" * 60)
    print(f"Cases: {pass_count}/{total} passed")
    print(f"Avg enhanced score: {avg_enhanced:.2f}")
    print(f"Avg confidence:     {avg_confidence:.2f}")
    print(f"Pass rate:          {pass_rate:.2f}")

    print()
    print("THRESHOLD CHECKS")
    print("-" * 60)
    conf_ok = avg_confidence >= PASS_THRESHOLDS["min_confidence"]
    impr_ok = all(r.improvement >= PASS_THRESHOLDS["min_improvement"] for r in results)
    rate_ok = pass_rate >= PASS_THRESHOLDS["min_pass_rate"]

    print(f"[{'PASS' if conf_ok else 'FAIL'}] avg_confidence >= {PASS_THRESHOLDS['min_confidence']}  (got {avg_confidence:.2f})")
    print(f"[{'PASS' if impr_ok else 'FAIL'}] all improvements >= {PASS_THRESHOLDS['min_improvement']}  (each enhanced >= baseline)")
    print(f"[{'PASS' if rate_ok else 'FAIL'}] pass_rate >= {PASS_THRESHOLDS['min_pass_rate']}  (got {pass_rate:.2f})")

    overall = conf_ok and impr_ok and rate_ok
    print()
    print(f"OVERALL: {'PASS' if overall else 'FAIL'}")

    if not overall:
        sys.exit(1)


if __name__ == "__main__":
    run_evaluation()
