"""Schema enforcement + position-balancing invariants."""

import pytest

from deseretbench.schema import validate_mc_item, validate_open_item
from deseretbench.balance_positions import balance, make_position_map


def _mc(**over):
    d = {"format": "mc", "axis": "doctrinal_accuracy",
         "dimension": "doctrine_scripture", "difficulty": "basic",
         "question": "Which book opens the Book of Mormon?",
         "choices": ["1 Nephi", "Alma", "Ether", "Moroni"],
         "answer_index": 0,
         "distractor_types": ["correct", "plausible_near_miss",
                              "plausible_near_miss", "folk_doctrine_trap"],
         "source": "Book of Mormon"}
    d.update(over)
    return d


def test_schema_requires_correct_at_answer_index():
    assert validate_mc_item(_mc()) == []
    # 'correct' label not aligned with the key — balance_positions would
    # silently mislabel every distractor downstream
    bad = _mc(distractor_types=["plausible_near_miss", "correct",
                                "plausible_near_miss", "folk_doctrine_trap"])
    assert any("correct" in e for e in validate_mc_item(bad))
    two = _mc(distractor_types=["correct", "correct",
                                "plausible_near_miss", "folk_doctrine_trap"])
    assert any("correct" in e for e in validate_mc_item(two))


def test_schema_axis_dimension_consistency():
    bad = _mc(axis="cultural_fluency")  # doctrine_scripture is a doctrinal dim
    assert any("axis" in e for e in validate_mc_item(bad))
    ok = _mc(dimension="cultural_fluency", axis="cultural_fluency")
    assert validate_mc_item(ok) == []
    open_bad = {"format": "open", "axis": "doctrinal_accuracy",
                "dimension": "life_choice", "difficulty": "advanced",
                "prompt": "A long enough scenario prompt for validation purposes.",
                "rubric": {"must_include": ["x"], "should_not": ["y"],
                           "ideal_reasoning_pattern": "z"}}
    assert any("axis" in e for e in validate_open_item(open_bad))


def test_balance_preserves_pairing_and_validates():
    items = [_mc(question=f"Question number {i} of sufficient length?") for i in range(30)]
    out = balance(items, seed=42)
    for it in out:
        assert it["distractor_types"][it["answer_index"]] == "correct"
        assert sorted(it["choices"]) == sorted(items[0]["choices"])
        assert validate_mc_item(it) == []


def test_balance_without_distractor_types_stays_schema_valid():
    it = _mc()
    del it["distractor_types"]
    out = balance([it], seed=1)[0]
    # must NOT fabricate a [null,...] list that fails validation
    assert "distractor_types" not in out
    assert validate_mc_item(out) == []


def test_balance_null_distractor_types_is_loud():
    it = _mc(distractor_types=None)
    with pytest.raises(ValueError):
        balance([it], seed=1)


def test_position_map_roundtrip():
    items = [_mc(question=f"Question number {i} of sufficient length?",
                 question_id=f"q{i}") for i in range(5)]
    out = balance(items, seed=7)
    pm = make_position_map(items, out)
    for old, new in zip(items, out):
        m = pm[old["question_id"]]
        # applying the recorded permutation to the old choices gives the new
        assert [old["choices"][i] for i in m["order"]] == new["choices"]
        assert m["answer_from"] == old["answer_index"]
        assert m["answer_to"] == new["answer_index"]
