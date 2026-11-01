"""The human review round: reviewers stay blind, and their sheets are read back
under the same keep rules the automated panel used. No model calls."""

import csv
import json

import pytest

from deseretbench import human_review as hr
from deseretbench import stats as stx
from deseretbench.packs import active_pack

DIMS = list(active_pack().judge_dimensions)
SECRET_MODEL = "secret-model-name"


def _mc_item(q, key=0):
    return {"question_id": q, "question": f"Question {q}?", "answer_index": key,
            "choices": ["right", "wrong one", "wrong two", "wrong three"],
            "distractor_types": ["correct", "x", "y", "z"]}


def _open_item(q):
    return {"question_id": q, "prompt": f"Situation {q}",
            "rubric": {"must_include": ["point a", "point b"], "should_not": ["bad"],
                       "ideal_reasoning_pattern": "HIDDEN-PATTERN"}}


def _run(tmp_path, n=6):
    run = tmp_path / "run"
    run.mkdir()
    scores, resp = [], []
    for i in range(n):
        base = {"model": SECRET_MODEL, "question_id": "o1", "run_index": i}
        scores.append({**base, "composite_100": float(i * 10)})
        resp.append({**base, "text": f"answer number {i}"})
    (run / "open_scores.jsonl").write_text("\n".join(map(json.dumps, scores)) + "\n")
    (run / "open_responses.jsonl").write_text("\n".join(map(json.dumps, resp)) + "\n")
    return run


def _rows(path):
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _sheet(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def _export(tmp_path, n_cal=3):
    out = tmp_path / "round"
    hr.export(_run(tmp_path), out, n_cal, 7, [_mc_item("m1", 1)], [_open_item("o1")])
    return out


def test_packet_keeps_reviewers_blind(tmp_path):
    out = _export(tmp_path)
    packet = "\n".join(p.read_text() for p in (out / "packet").iterdir())
    assert SECRET_MODEL not in packet
    assert "answer_index" not in packet and "distractor_types" not in packet
    assert "HIDDEN-PATTERN" not in packet
    cols = _rows(out / "packet" / "calibration.csv")[0].keys()
    assert not any("composite" in c or "judge" in c for c in cols)


def test_organiser_key_maps_every_calibration_answer(tmp_path):
    out = _export(tmp_path)
    key = json.loads((out / "organiser" / "calibration_key.json").read_text())["responses"]
    ids = [r["response_id"] for r in _rows(out / "packet" / "calibration.csv")]
    assert len(ids) == 3 and set(ids) == set(key)
    assert all(v["model"] == SECRET_MODEL for v in key.values())


def test_export_is_seeded_and_response_ids_do_not_name_the_model(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir(); b.mkdir()
    assert (_rows(_export(a) / "packet" / "calibration.csv")
            == _rows(_export(b) / "packet" / "calibration.csv"))
    assert SECRET_MODEL not in hr.response_id(SECRET_MODEL, "q", 0, 7)


def test_calibration_sample_spans_the_score_range():
    scores = [{"model": "m", "question_id": "q", "run_index": i, "composite_100": float(i)}
              for i in range(100)] + [
              {"model": "m", "question_id": "q", "run_index": 999, "composite_100": None}]
    got = sorted(r["composite_100"] for r in hr.calibration_sample(scores, 5, seed=1))
    assert [int(v // 20) for v in got] == [0, 1, 2, 3, 4]


def test_spearman_handles_ties_and_undefined_cases():
    assert stx.spearman([1, 2, 3], [10, 20, 30]) == pytest.approx(1.0)
    assert stx.spearman([1, 2, 3], [30, 20, 10]) == pytest.approx(-1.0)
    assert stx.spearman([1, 2], [1, 2]) is None
    assert stx.spearman([1, 1, 1], [1, 2, 3]) is None


def _mc_row(q, answer, clarity="5", flags="none"):
    return {"question_id": q, "best_answer": answer, "n_defensible_options": "1",
            "clarity": clarity, "flags": flags, "comment": ""}


def test_reviews_use_the_automated_panels_keep_rules(tmp_path):
    ret = tmp_path / "returned"
    for rid in ("R1", "R2", "R3"):
        _sheet(ret / f"review_mc.{rid}.csv",
               [_mc_row("good", "A"), _mc_row("bad", "B"),
                _mc_row("flagged", "A", flags="factually wrong; unfair")])
    # one reviewer left this item blank; two answers is under the quorum of three
    for rid in ("R1", "R2"):
        with (ret / f"review_mc.{rid}.csv").open("a", newline="") as f:
            csv.writer(f).writerow(["short", "A", "1", "5", "none", ""])
    reviews = hr.read_reviews(ret)
    assert {r["persona"] for r in reviews["mc"]} == {"R1", "R2", "R3"}
    items = [_mc_item(q) for q in ("good", "bad", "flagged", "short")]
    rep = hr.report(reviews, items, [], {})
    assert rep["mc"]["n_kept"] == 1
    assert rep["mc"]["n_unreviewed"] == 1
    assert {f["question_id"] for f in rep["mc"]["failed"]} == {"bad", "flagged"}
    assert "_review" not in items[0]        # the caller's items are not annotated


def test_a_blank_row_is_no_review(tmp_path):
    ret = tmp_path / "returned"
    _sheet(ret / "review_mc.R1.csv", [_mc_row("q", "")])
    assert hr.read_reviews(ret)["mc"] == []


def test_out_of_range_rating_is_missing_not_clamped(tmp_path):
    ret = tmp_path / "returned"
    _sheet(ret / "review_mc.R1.csv", [_mc_row("q", "A", clarity="9")])
    assert hr.read_reviews(ret)["mc"][0]["review"]["clarity"] is None


def _cal_row(rid, score):
    return {"response_id": rid, **{d: str(score) for d in DIMS},
            "must_include_hits": "1", "should_not_violations": "0", "comment": ""}


def test_calibration_compares_human_mean_with_the_judge(tmp_path):
    ret = tmp_path / "returned"
    _sheet(ret / "calibration.R1.csv", [_cal_row(f"r{i}", i) for i in range(1, 6)])
    _sheet(ret / "calibration.R2.csv", [_cal_row(f"r{i}", i) for i in range(1, 6)]
           + [_cal_row("unknown", 3)])
    key = {f"r{i}": {"judge_composite_100": (i - 1) * 25.0 + 2} for i in range(1, 6)}
    cal = hr.report(hr.read_reviews(ret), [], [], key)["calibration"]
    assert cal["n_responses"] == 5              # the row the key does not know is ignored
    assert cal["spearman_rho"] == pytest.approx(1.0)
    assert cal["meets_judge_target"]
    assert cal["mean_human_minus_judge"] == pytest.approx(-2.0)


def test_judge_failing_the_target_is_reported(tmp_path):
    ret = tmp_path / "returned"
    _sheet(ret / "calibration.R1.csv", [_cal_row(f"r{i}", i) for i in range(1, 6)])
    key = {f"r{i}": {"judge_composite_100": (5 - i) * 25.0} for i in range(1, 6)}
    cal = hr.report(hr.read_reviews(ret), [], [], key)["calibration"]
    assert cal["spearman_rho"] == pytest.approx(-1.0)
    assert not cal["meets_judge_target"]
