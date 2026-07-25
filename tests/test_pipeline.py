"""Scoring/judging/orchestration behavior tests (no live model calls)."""

import json

import pytest

from deseretbench.score_mc import parse_answer
from deseretbench.judge import aggregate_panel, extract_last_json, parse_judge_json
from deseretbench.run_benchmark import JsonlSink, select_cohort, pick_crosscheck_keys


# --------------------------------------------------------------------------- #
# score_mc: rule-1 must not fish letters out of ordinary words
# --------------------------------------------------------------------------- #

def test_parse_answer_word_prefix_not_matched():
    assert parse_answer("The answer depends on context.", 5) is None
    assert parse_answer("The answer appears to be C", 5) == "C"
    # never confidently misparse the leading letter of a word as an answer
    assert parse_answer("ANSWER: Actually, it is unclear.", 5) != "A"


def test_parse_answer_hedge_is_parse_failure():
    assert parse_answer("ANSWER: A or B", 5) is None
    assert parse_answer("The answer is C or D, hard to say.", 5) is None


def test_parse_answer_statement_beats_option_mentions():
    t = "The correct answer is B, though option C is tempting but option D is wrong."
    assert parse_answer(t, 5) == "B"


def test_parse_answer_existing_formats_still_work():
    assert parse_answer("Reasoning...\nANSWER: C", 5) == "C"
    assert parse_answer("blah\nANSWER: (D)", 5) == "D"
    assert parse_answer("**B**", 5) == "B"
    assert parse_answer("I would choose E", 5) == "E"
    assert parse_answer("Final line:\nB", 5) == "B"


# --------------------------------------------------------------------------- #
# judge: malformed judge outputs must degrade, never crash or fake-clean
# --------------------------------------------------------------------------- #

def _dims(v=4):
    return {"doctrinal_accuracy": v, "cultural_authenticity": v,
            "practical_wisdom": v, "distinctiveness": v}


def test_aggregate_panel_survives_malformed_counts():
    jr = {**_dims(), "must_include_hits": "three", "must_include_total": 3,
          "should_not_violations": None}
    agg = aggregate_panel([jr])  # must not raise
    assert agg["composite_100"] is not None
    assert agg["must_include_coverage"] is None      # unparseable, not fabricated
    assert agg["mean_should_not_violations"] is None  # missing != zero violations


def test_aggregate_panel_clamps_coverage():
    jr = {**_dims(), "must_include_hits": 7, "must_include_total": 3,
          "should_not_violations": 0}
    agg = aggregate_panel([jr])
    assert agg["must_include_coverage"] == 1.0


def test_aggregate_panel_normal_case():
    jrs = [{**_dims(4), "must_include_hits": 2, "must_include_total": 4,
            "should_not_violations": 1},
           {**_dims(5), "must_include_hits": 3, "must_include_total": 4,
            "should_not_violations": 0}]
    agg = aggregate_panel(jrs)
    assert agg["n_judges"] == 2
    assert agg["must_include_coverage"] == pytest.approx(5 / 8)
    assert agg["mean_should_not_violations"] == pytest.approx(0.5)


def test_json_scanner_ignores_braces_inside_strings():
    text = 'preamble {"doctrinal_accuracy": 4, "cultural_authenticity": 4, ' \
           '"practical_wisdom": 4, "distinctiveness": 4, "must_include_hits": 1, ' \
           '"must_include_total": 2, "should_not_violations": 0, ' \
           '"justification": "close} but incomplete{"}'
    d = parse_judge_json(text)
    assert d is not None and d["doctrinal_accuracy"] == 4
    assert extract_last_json(text)["justification"] == "close} but incomplete{"


# --------------------------------------------------------------------------- #
# run_benchmark: sink atomicity + cohort validation + crosscheck selection
# --------------------------------------------------------------------------- #

def test_sink_is_atomic(tmp_path):
    p = tmp_path / "out.jsonl"
    p.write_text('{"old": true}\n')
    sink = JsonlSink(p)
    # while open, the original file is untouched (a crash preserves it)
    assert json.loads(p.read_text())["old"] is True
    sink.write({"new": 1})
    sink.write({"new": 2})
    assert json.loads(p.read_text())["old"] is True
    sink.close()  # finalize: atomic replace
    lines = p.read_text().splitlines()
    assert len(lines) == 2 and json.loads(lines[0])["new"] == 1
    assert not list(tmp_path.glob("*.tmp"))


def test_select_cohort_rejects_unknown_model():
    models = {"cohort": [{"id": "claude-opus-4-8"}, {"id": "claude-haiku-4-5-20251001"}]}
    assert [m["id"] for m in select_cohort(models, "claude-opus-4-8")] == ["claude-opus-4-8"]
    assert len(select_cohort(models, "")) == 2
    with pytest.raises(SystemExit):
        select_cohort(models, "claude-opsu-4-8")  # typo must be loud, not empty


def test_pick_crosscheck_keys_deterministic():
    keys = [("m", f"q{i}", r) for i in range(20) for r in range(3)]
    a = pick_crosscheck_keys(keys, 0.25, seed=19470417)
    b = pick_crosscheck_keys(keys, 0.25, seed=19470417)
    assert a == b
    assert 0 < len(a) < len(keys)
    assert len(a) == round(len(keys) * 0.25)


def test_hedge_does_not_trigger_on_english_article():
    assert parse_answer("ANSWER: B, or a close variant of it.", 5) == "B"
    assert parse_answer("ANSWER: A or B", 5) is None  # real hedges still fail
    assert parse_answer("ANSWER: C or D", 5) is None
