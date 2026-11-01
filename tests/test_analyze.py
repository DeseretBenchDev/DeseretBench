"""analyze.py behavior on synthetic run data (no live calls)."""

import json

import pytest

from deseretbench.analyze import analyze_mc, analyze_open

COHORT = [
    {"id": "model-a", "label": "A", "tier": "opus"},
    {"id": "model-b", "label": "B", "tier": "haiku"},
]


def _mc_rec(model, qid, run, correct, *, call_ok=True, served=None, cost=0.01,
            parse_ok=True):
    return {"format": "mc", "model": model, "tier": "t", "label": model,
            "question_id": qid, "dimension": "doctrine_scripture",
            "difficulty": "basic", "axis": "doctrinal_accuracy", "run_index": run,
            "model_served": served or model, "call_ok": call_ok,
            "answer_index": 0, "parsed_letter": "A" if parse_ok else None,
            "correct": correct, "parse_ok": parse_ok, "cost_usd": cost,
            "input_tokens": 5, "output_tokens": 9, "duration_ms": 1,
            "attempts": 1, "cache_hit": False, "error": None, "text": "ANSWER: A"}


def _write(path, recs):
    path.write_text("\n".join(json.dumps(r) for r in recs) + "\n")


def test_mc_call_failures_excluded_from_accuracy(tmp_path):
    recs = []
    for q in range(4):
        for r in range(2):
            recs.append(_mc_rec("model-a", f"q{q}", r, True))
    # transport failure recorded correct=False — must shrink n, not accuracy
    recs.append(_mc_rec("model-a", "q0", 2, False, call_ok=False))
    recs += [_mc_rec("model-b", f"q{q}", 0, q < 2) for q in range(4)]
    p = tmp_path / "mc.jsonl"
    _write(p, recs)
    out = analyze_mc(p, COHORT, seed=7, n_boot=200, ci=0.95)
    assert out["overall"]["model-a"]["mean"] == pytest.approx(1.0)
    assert out["overall"]["model-a"]["n_call_failed"] == 1
    assert out["overall"]["model-b"]["mean"] == pytest.approx(0.5)


def test_mc_served_mismatch_classification(tmp_path):
    recs = []
    for q in range(6):
        recs.append(_mc_rec("model-a", f"q{q}", 0, True, cost=0.010))
    # multikey artifact: wrong served label but full model-a pricing
    recs.append(_mc_rec("model-a", "q6", 0, True, served="model-b", cost=0.0102))
    # genuine fallback: served by the cheap tier at cheap-tier price
    recs.append(_mc_rec("model-a", "q7", 0, True, served="model-b", cost=0.002))
    p = tmp_path / "mc.jsonl"
    _write(p, recs)
    out = analyze_mc(p, COHORT, seed=7, n_boot=200, ci=0.95)
    o = out["overall"]["model-a"]
    assert o["served_mismatch_artifact"] == 1
    assert o["served_mismatch_genuine"] == 1
    # the genuine-fallback item must not contribute to model-a's score
    assert o["n"] == 7  # q0..q6 kept, q7 excluded


def test_mc_pairwise_has_holm_adjustment(tmp_path):
    recs = []
    for q in range(10):
        recs.append(_mc_rec("model-a", f"q{q}", 0, True))
        recs.append(_mc_rec("model-b", f"q{q}", 0, q % 2 == 0))
    p = tmp_path / "mc.jsonl"
    _write(p, recs)
    out = analyze_mc(p, COHORT, seed=7, n_boot=200, ci=0.95)
    pw = out["pairwise"][0]
    assert "p_holm" in pw and pw["p_holm"] >= pw["p_bootstrap"]
    assert "significant_holm" in pw


def test_mc_ceiling_gets_exact_binomial_ci(tmp_path):
    recs = [_mc_rec("model-a", f"q{q}", r, True) for q in range(20) for r in range(2)]
    p = tmp_path / "mc.jsonl"
    _write(p, recs)
    out = analyze_mc(p, COHORT, seed=7, n_boot=200, ci=0.95)
    o = out["overall"]["model-a"]
    # bootstrap CI is degenerate [1,1] at the ceiling; the exact interval is not
    assert o["cp_lo"] < 1.0 and o["cp_hi"] == 1.0


def _open_score(model, qid, run, comp, dim="life_choice"):
    return {"model": model, "tier": "t", "label": model, "question_id": qid,
            "dimension": dim, "difficulty": "advanced", "run_index": run,
            "composite_100": comp, "dim_means": {}, "must_include_coverage": 0.8,
            "mean_should_not_violations": 0.1, "n_judges": 3}


def test_open_by_dimension_uses_item_unit(tmp_path):
    # 2 items x 3 identical runs: the sampling unit is the ITEM (n=2), not the
    # run-record (n=6) — pooling records pseudo-replicates and narrows CIs
    recs = []
    for q, base in (("q1", 40.0), ("q2", 80.0)):
        for r in range(3):
            recs.append(_open_score("model-a", q, r, base))
    sp = tmp_path / "open_scores.jsonl"
    _write(sp, recs)
    out = analyze_open(sp, tmp_path / "missing_judge.jsonl", COHORT,
                       seed=7, n_boot=200, ci=0.95)
    bd = out["by_dimension"]["model-a"]["life_choice"]
    assert bd["n"] == 2
    assert out["overall"]["model-a"]["n"] == 2


def test_open_irr_per_dimension(tmp_path):
    sp = tmp_path / "open_scores.jsonl"
    _write(sp, [_open_score("model-a", "q1", 0, 50.0)])
    jr = []
    for q in ("q1", "q2", "q3"):
        for persona, off in (("p1", 0), ("p2", 1)):
            base = {"doctrinal_accuracy": 3 + off, "cultural_authenticity": 3,
                    "practical_wisdom": 2 + off, "distinctiveness": 4}
            jr.append({"model": "model-a", "question_id": q, "run_index": 0,
                       "persona": persona, "judge_model": "j", "judge_role": "primary",
                       "call_ok": True, "parse_ok": True, "scores": base})
    jp = tmp_path / "judge.jsonl"
    _write(jp, jr)
    out = analyze_open(sp, jp, COHORT, seed=7, n_boot=100, ci=0.95)
    irr = out["judge_irr"]
    assert "per_dimension_alpha" in irr
    assert set(irr["per_dimension_alpha"]) == {"doctrinal_accuracy",
                                               "cultural_authenticity",
                                               "practical_wisdom",
                                               "distinctiveness"}


# --------------------------------------------------------------------------- #
# generation reaches the summary (report needs it to plot scaling by size)
# --------------------------------------------------------------------------- #


SIZED_COHORT = [
    {"id": "model-a", "label": "A", "tier": "qwen3", "generation": 1.7},
    {"id": "model-b", "label": "B", "tier": "haiku"},          # no generation key
]


def test_mc_overall_carries_generation(tmp_path):
    """`generation` is the parameter count for local families, so the report
    can only draw a performance-vs-size curve if analyze passes it through."""
    recs = [_mc_rec("model-a", f"q{q}", 0, True) for q in range(3)]
    recs += [_mc_rec("model-b", f"q{q}", 0, True) for q in range(3)]
    p = tmp_path / "mc.jsonl"
    _write(p, recs)
    out = analyze_mc(p, SIZED_COHORT, seed=7, n_boot=50, ci=0.95)
    assert out["overall"]["model-a"]["generation"] == 1.7
    # absent in config -> None, never invented
    assert out["overall"]["model-b"]["generation"] is None


def test_open_overall_carries_generation(tmp_path):
    recs = [_open_score("model-a", f"q{q}", 0, 80.0) for q in range(3)]
    recs += [_open_score("model-b", f"q{q}", 0, 60.0) for q in range(3)]
    sp = tmp_path / "open_scores.jsonl"
    _write(sp, recs)
    out = analyze_open(sp, tmp_path / "missing_judge.jsonl", SIZED_COHORT,
                       seed=7, n_boot=50, ci=0.95)
    assert out["overall"]["model-a"]["generation"] == 1.7
    assert out["overall"]["model-b"]["generation"] is None


def test_open_reports_run_to_run_spread_and_repeat_count(tmp_path):
    # q1: runs 40, 60 -> SD (ddof=1) 14.142; q2: 80, 80 -> 0; q3 has one run and
    # cannot contribute. Mean over the two repeated items = 7.07.
    recs = [_open_score("model-a", "q1", 0, 40.0), _open_score("model-a", "q1", 1, 60.0),
            _open_score("model-a", "q2", 0, 80.0), _open_score("model-a", "q2", 1, 80.0),
            _open_score("model-a", "q3", 0, 50.0),
            # an unscored repeat is not a repeat
            _open_score("model-a", "q3", 1, None)]
    sp = tmp_path / "open_scores.jsonl"
    _write(sp, recs)
    o = analyze_open(sp, tmp_path / "missing_judge.jsonl", COHORT,
                     seed=7, n_boot=100, ci=0.95)["overall"]["model-a"]
    assert o["mean_within_item_sd"] == 7.07
    assert o["n_items_repeated"] == 2
    assert o["n_repeats"] == 2
    assert o["n"] == 3


def test_open_run_spread_is_undefined_with_a_single_repeat(tmp_path):
    # One run per item says nothing about spread: report None, not 0.0.
    sp = tmp_path / "open_scores.jsonl"
    _write(sp, [_open_score("model-a", "q1", 0, 40.0),
                _open_score("model-a", "q2", 0, 80.0)])
    o = analyze_open(sp, tmp_path / "missing_judge.jsonl", COHORT,
                     seed=7, n_boot=100, ci=0.95)["overall"]["model-a"]
    assert o["mean_within_item_sd"] is None
    assert o["n_items_repeated"] == 0
    assert o["n_repeats"] == 1


def test_context_override_travels_with_the_row_and_only_that_row(tmp_path):
    # A model run under its own context window must say so wherever its row is
    # printed; every other model's record must not gain the key.
    cohort = [{"id": "model-a", "label": "A", "tier": "opus"},
              {"id": "model-b", "label": "B", "tier": "phi", "backend": "ollama",
               "backend_opts": {"ollama_num_ctx": 4096}}]
    recs = [_mc_rec(m, q, r, True) for m in ("model-a", "model-b")
            for q in ("q1", "q2") for r in (0, 1)]
    p = tmp_path / "mc.jsonl"
    _write(p, recs)
    ov = analyze_mc(p, cohort, seed=7, n_boot=100, ci=0.95)["overall"]
    assert ov["model-b"]["num_ctx"] == 4096
    assert "num_ctx" not in ov["model-a"]

    from deseretbench.report import ctx_note, row_label
    assert row_label(ov["model-b"]) == "B § (context 4,096)"
    assert row_label(ov["model-a"]) == "A"
    assert "§" in ctx_note(ov)
    assert ctx_note({"model-a": ov["model-a"]}) == ""
