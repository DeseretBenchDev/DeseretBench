"""Completeness-audit tests.

These pin the distinction that made the open phase spin forever: whether a
record can still be HEALED by a retry is a different question from whether the
dataset is COMPLETE enough to score. A judge verdict rejected by the
served-model guard is dropped, never accepted under the wrong model — so the
panel it belonged to must still be able to finish on its remaining judges.
"""

import json

import pytest

import deseretbench.audit as A


def _write(path, recs):
    with open(path, "w", encoding="utf-8") as fh:
        for r in recs:
            fh.write(json.dumps(r) + "\n")
    return path


def _judge(qid, persona, run=0, ok=True, scores=True, role="primary",
           model="qwen3:4b-instruct"):
    return {"model": model, "question_id": qid, "run_index": run,
            "persona": persona, "judge_role": role, "call_ok": ok,
            "parse_ok": bool(scores),
            "scores": {"doctrinal_accuracy": 4} if scores else None}


PERSONAS = ["seminary_teacher", "byu_religion_professor", "bishop"]


# --------------------------------------------------------------------------- #
# scan_jsonl — the retry signal
# --------------------------------------------------------------------------- #


def test_scan_missing_file_is_zeros(tmp_path):
    assert A.scan_jsonl(tmp_path / "nope.jsonl") == (0, 0, 0)


def test_scan_counts_failed_and_corrupt(tmp_path):
    p = tmp_path / "r.jsonl"
    _write(p, [{"call_ok": True}, {"call_ok": False}, {"call_ok": True}])
    with open(p, "a", encoding="utf-8") as fh:
        fh.write("{not json\n")
        fh.write("\n")            # blank lines are skipped, not corrupt
    fail, total, corrupt = A.scan_jsonl(p)
    assert (fail, total, corrupt) == (1, 4, 1)


def test_scan_treats_absent_call_ok_as_success(tmp_path):
    """Older records predate the flag; absent must not read as failure."""
    p = _write(tmp_path / "r.jsonl", [{"text": "hi"}])
    assert A.scan_jsonl(p) == (0, 1, 0)


# --------------------------------------------------------------------------- #
# judge_quorum_shortfall — the acceptance signal
# --------------------------------------------------------------------------- #


def test_full_panel_has_no_shortfall(tmp_path):
    p = _write(tmp_path / "j.jsonl", [_judge("q1", x) for x in PERSONAS])
    assert A.judge_quorum_shortfall(p, quorum=2) == 0


def test_one_failed_verdict_still_meets_quorum_of_two(tmp_path):
    """The live case: the served-model guard rejected one verdict; the panel
    scored over the other two and the triple has a valid composite."""
    recs = [_judge("q1", PERSONAS[0]), _judge("q1", PERSONAS[2]),
            _judge("q1", PERSONAS[1], ok=False, scores=False)]
    p = _write(tmp_path / "j.jsonl", recs)
    assert A.judge_quorum_shortfall(p, quorum=2) == 0
    assert A.judge_quorum_shortfall(p, quorum=3) == 1


def test_two_failed_verdicts_break_quorum(tmp_path):
    recs = [_judge("q1", PERSONAS[0])] + [
        _judge("q1", x, ok=False, scores=False) for x in PERSONAS[1:]]
    p = _write(tmp_path / "j.jsonl", recs)
    assert A.judge_quorum_shortfall(p, quorum=2) == 1


def test_unparsed_verdict_counts_against_quorum(tmp_path):
    """call_ok=True but unparseable carries no scores — it cannot count as a
    judge, even though it is cached and will never heal."""
    recs = [_judge("q1", PERSONAS[0]), _judge("q1", PERSONAS[1]),
            _judge("q1", PERSONAS[2], ok=True, scores=False)]
    p = _write(tmp_path / "j.jsonl", recs)
    assert A.judge_quorum_shortfall(p, quorum=3) == 1
    assert A.judge_quorum_shortfall(p, quorum=2) == 0


def test_triples_are_separated_by_model_and_run(tmp_path):
    recs = []
    for model in ("a", "b"):
        for run in (0, 1):
            recs.append(_judge("q1", PERSONAS[0], run=run, model=model))
    p = _write(tmp_path / "j.jsonl", recs)
    assert A.judge_quorum_shortfall(p, quorum=2) == 4   # each has only 1 judge


def test_crosscheck_verdicts_do_not_prop_up_the_primary_panel(tmp_path):
    """Crosscheck runs a different judge model for sensitivity analysis; it is
    not part of the scored panel and must not fill a quorum gap."""
    recs = [_judge("q1", PERSONAS[0])]
    recs += [_judge("q1", x, role="crosscheck") for x in PERSONAS[1:]]
    p = _write(tmp_path / "j.jsonl", recs)
    assert A.judge_quorum_shortfall(p, quorum=2) == 1


# --------------------------------------------------------------------------- #
# audit_open — the two signals stay independent
# --------------------------------------------------------------------------- #


def test_audit_open_reports_heal_and_accept_separately(tmp_path):
    gen = [{"model": "m", "question_id": "q1", "run_index": 0,
            "call_ok": True, "text": "x"}]
    _write(tmp_path / "open_responses.jsonl", gen)
    recs = [_judge("q1", PERSONAS[0], model="m"), _judge("q1", PERSONAS[2], model="m"),
            _judge("q1", PERSONAS[1], ok=False, scores=False, model="m")]
    _write(tmp_path / "open_judge_raw.jsonl", recs)

    r = A.audit_open(tmp_path, n_items=1, n_models=1, n_runs=1,
                     n_personas=3, quorum=2)
    assert r["strict_fail"] == 1      # the guard-rejected call could still heal
    assert r["below_quorum"] == 0     # ...but the panel is already scoreable
    assert r["accept_fail"] == 0      # ...so the phase may finish
    assert r["judge_failed"] == 1


def test_audit_open_empty_run_is_never_acceptable(tmp_path):
    """The trap quorum-acceptance could open: with nothing generated there are
    no panels, so no panel is below quorum. Generation gaps must still block."""
    _write(tmp_path / "open_responses.jsonl", [])
    _write(tmp_path / "open_judge_raw.jsonl", [])
    r = A.audit_open(tmp_path, n_items=2, n_models=1, n_runs=1,
                     n_personas=3, quorum=2)
    assert r["strict_fail"] > 0
    assert r["accept_fail"] > 0


def test_audit_open_unjudged_triple_blocks_acceptance(tmp_path):
    """A response that generated but was never judged has no panel records at
    all — invisible to a shortfall scan over records that exist."""
    _write(tmp_path / "open_responses.jsonl",
           [{"model": "m", "question_id": "q1", "run_index": 0,
             "call_ok": True, "text": "x"}])
    _write(tmp_path / "open_judge_raw.jsonl", [])
    r = A.audit_open(tmp_path, n_items=1, n_models=1, n_runs=1,
                     n_personas=3, quorum=2)
    assert r["below_quorum"] == 1
    assert r["accept_fail"] > 0


def test_audit_open_corrupt_judge_line_blocks_acceptance(tmp_path):
    """File damage is not a flaky call: never accept around it, even if the
    surviving verdicts still make quorum."""
    _write(tmp_path / "open_responses.jsonl",
           [{"model": "m", "question_id": "q1", "run_index": 0,
             "call_ok": True, "text": "x"}])
    p = _write(tmp_path / "open_judge_raw.jsonl",
               [_judge("q1", PERSONAS[0], model="m"),
                _judge("q1", PERSONAS[1], model="m")])
    with open(p, "a", encoding="utf-8") as fh:
        fh.write("{truncated\n")
    r = A.audit_open(tmp_path, n_items=1, n_models=1, n_runs=1,
                     n_personas=3, quorum=2)
    assert r["below_quorum"] == 0     # two good verdicts still make quorum
    assert r["accept_fail"] > 0       # ...but the corrupt line blocks anyway


def test_audit_mc_counts_missing(tmp_path):
    _write(tmp_path / "mc_responses.jsonl", [{"call_ok": True}])
    r = A.audit_mc(tmp_path, n_items=2, n_models=1, n_runs=1)
    assert r["strict_fail"] == 1      # 2 expected, 1 present
    assert r["accept_fail"] == 1      # MC has no panel to fall back on
