"""Unit tests for DeseretBench core logic (no network / no model calls).

Run:  .venv/bin/python -m pytest tests/ -q     (or: python tests/test_core.py)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from deseretbench.score_mc import parse_answer  # noqa: E402
from deseretbench.schema import validate_mc_item, validate_open_item, content_hash_id  # noqa: E402
from deseretbench.judge import parse_judge_json, extract_last_json, aggregate_panel  # noqa: E402
from deseretbench import stats as stx  # noqa: E402
from deseretbench.author import extract_array  # noqa: E402


def test_parse_answer_variants():
    assert parse_answer("reasoning...\nANSWER: B", 4) == "B"
    assert parse_answer("The correct answer is C.", 4) == "C"
    assert parse_answer("blah\n\nD", 4) == "D"
    assert parse_answer("I would choose (A).", 4) == "A"
    assert parse_answer("**ANSWER: E**", 5) == "E"
    assert parse_answer("first ANSWER: A ... reconsidered ANSWER: C", 4) == "C"  # last wins
    assert parse_answer("answer is E", 4) is None       # out of range for 4 choices
    assert parse_answer("no letter here", 4) is None


def test_schema_validation():
    good = {"format": "mc", "axis": "doctrinal_accuracy", "dimension": "doctrine_scripture",
            "difficulty": "basic", "question": "How many degrees of glory?",
            "choices": ["One", "Two", "Three", "Four"], "answer_index": 2,
            "distractor_types": ["plausible_near_miss", "plausible_near_miss", "correct",
                                 "plausible_near_miss"], "source": "D&C 76"}
    assert validate_mc_item(good) == []
    bad = dict(good, answer_index=9)
    assert validate_mc_item(bad)
    dup = dict(good, choices=["a", "a", "b", "c"])
    assert validate_mc_item(dup)
    op = {"format": "open", "axis": "life_choice_alignment", "dimension": "life_choice",
          "difficulty": "advanced", "prompt": "A long enough scenario prompt here for testing.",
          "rubric": {"must_include": ["x"], "should_not": ["y"], "ideal_reasoning_pattern": "z"}}
    assert validate_open_item(op) == []
    assert validate_open_item(dict(op, rubric={"must_include": []}))


def test_content_hash_id_stable():
    it = {"format": "mc", "dimension": "doctrine_scripture", "difficulty": "basic",
          "question": "Q?", "choices": ["a", "b", "c", "d"]}
    assert content_hash_id(it) == content_hash_id(dict(it))
    it2 = dict(it, question="Different?")
    assert content_hash_id(it) != content_hash_id(it2)


def test_json_extractors():
    assert extract_last_json('prefix {"a":1} mid {"b":2} end')["b"] == 2
    j = parse_judge_json('text {"doctrinal_accuracy":4,"cultural_authenticity":3,'
                         '"practical_wisdom":5,"distinctiveness":2,"must_include_hits":2,'
                         '"must_include_total":4,"should_not_violations":0}')
    assert j and j["doctrinal_accuracy"] == 4
    arr = extract_array('[{"x":1},{"x":2}]')
    assert len(arr) == 2


def test_aggregate_panel():
    jr = [{"doctrinal_accuracy": 5, "cultural_authenticity": 5, "practical_wisdom": 5,
           "distinctiveness": 5, "must_include_hits": 4, "must_include_total": 4,
           "should_not_violations": 0}]
    agg = aggregate_panel(jr)
    assert agg["composite_5"] == 5.0
    assert agg["composite_100"] == 100.0
    assert agg["must_include_coverage"] == 1.0


def test_stats_bootstrap_and_paired():
    ci = stx.bootstrap_mean_ci([1.0] * 80 + [0.0] * 20, n_resamples=2000, seed=1)
    assert 0.70 < ci["mean"] < 0.90 and ci["lo"] < ci["mean"] < ci["hi"]
    d = stx.paired_bootstrap_diff([1.0] * 70 + [0.0] * 30, [1.0] * 55 + [0.0] * 45,
                                  n_resamples=2000, seed=2)
    assert d["diff"] > 0 and d["p"] < 0.05


def test_krippendorff_known_value():
    # canonical interval example, alpha ~ 0.849
    ref = [[1, 2, 3, 3, 2, 1, 4, 1, 2, None, None, None],
           [1, 2, 3, 3, 2, 2, 4, 1, 2, 5, None, 3],
           [None, 3, 3, 3, 2, 3, 4, 2, 2, 5, 1, None],
           [1, 2, 3, 3, 2, 4, 4, 1, 2, 5, 1, None]]
    a = stx.krippendorff_alpha_interval(ref)
    assert abs(a - 0.849) < 0.01
    # random data -> ~0
    import numpy as np
    rng = np.random.default_rng(0)
    rand = [[float(x) for x in rng.integers(1, 6, 400)] for _ in range(3)]
    assert abs(stx.krippendorff_alpha_interval(rand)) < 0.06


def test_mcnemar_and_item_analysis():
    mc = stx.mcnemar_test([True] * 70 + [False] * 30, [True] * 55 + [False] * 45)
    assert mc["p"] < 0.05
    ia = stx.item_analysis({"q1": [1, 1, 1, 0], "q2": [1, 0, 1, 0], "q3": [0, 0, 1, 0]})
    assert ia["q2"]["difficulty_p"] == 0.5
    assert -1 <= ia["q2"]["discrimination"] <= 1


def _run_all():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for fn in fns:
        fn()
        passed += 1
        print(f"  PASS {fn.__name__}")
    print(f"\n{passed}/{len(fns)} tests passed")


if __name__ == "__main__":
    _run_all()
