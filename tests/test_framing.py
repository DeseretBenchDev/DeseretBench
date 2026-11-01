"""The framed edition: a second prompt condition, kept apart from the standings.

The standings are the neutral condition. A framed run appends one sentence from
the pack to the system prompt, writes into its own directory, and is compared
with the neutral run by `deseretbench.framing`. These tests pin the three ways
a framed score could leak into the standings (shared cache keys, a shared run
directory, a merged or analysed record) and the comparison arithmetic.
"""

import json
from types import SimpleNamespace

import pytest

from deseretbench import framing, run_benchmark as rb
from deseretbench.analyze import analyze_mc, analyze_open
from deseretbench.merge_runs import merge_runs
from deseretbench.packs import active_pack
from deseretbench.runner import _cache_key

COHORT = [{"id": "model-a", "label": "A", "tier": "opus"},
          {"id": "model-b", "label": "B", "tier": "haiku"}]


def _write(path, recs):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r) for r in recs) + "\n")


def _mc(model, qid, run, correct, condition=None):
    r = {"format": "mc", "model": model, "tier": "t", "label": model,
         "question_id": qid, "dimension": "doctrine_scripture", "difficulty": "basic",
         "axis": "doctrinal_accuracy", "run_index": run, "model_served": model,
         "call_ok": True, "answer_index": 0, "parsed_letter": "A", "correct": correct,
         "parse_ok": True, "cost_usd": 0.0, "text": "ANSWER: A"}
    if condition:
        r["condition"] = condition
    return r


def _open(model, qid, run, comp, condition=None):
    r = {"model": model, "tier": "t", "label": model, "question_id": qid,
         "dimension": "life_choice", "difficulty": "advanced", "run_index": run,
         "composite_100": comp, "dim_means": {}, "must_include_coverage": 0.8,
         "mean_should_not_violations": 0.1, "n_judges": 3}
    if condition:
        r["condition"] = condition
    return r


def test_neutral_condition_leaves_the_system_prompt_and_cache_key_alone():
    system = "You are answering items.\n"
    assert rb.condition_system(system, "neutral") is system
    assert rb.condition_fields("neutral") == {}


def test_framed_condition_appends_the_pack_sentence_and_changes_the_cache_key():
    system = "You are answering items.\n"
    framed = rb.condition_system(system, "framed")
    assert framed.startswith(system.rstrip())
    assert framed.rstrip().endswith(active_pack().framed_instruction)
    assert (_cache_key("ollama", "m", framed, "p", "low", 0)
            != _cache_key("ollama", "m", system, "p", "low", 0))
    assert rb.condition_fields("framed") == {"condition": "framed"}


def test_unknown_condition_is_refused():
    with pytest.raises(SystemExit):
        rb.condition_system("s", "devout")


def test_a_run_directory_holds_one_condition(tmp_path):
    (tmp_path / "config_snapshot.json").write_text(json.dumps({"mc": {"n_runs": 2}}))
    rb.guard_condition(tmp_path, "neutral")          # a snapshot with no key is neutral
    with pytest.raises(SystemExit):
        rb.guard_condition(tmp_path, "framed")
    (tmp_path / "config_snapshot.json").write_text(
        json.dumps({"open": {"condition": "framed"}}))
    rb.guard_condition(tmp_path, "framed")
    with pytest.raises(SystemExit):
        rb.guard_condition(tmp_path, "neutral")
    rb.guard_condition(tmp_path / "fresh", "framed")  # no snapshot yet: nothing to guard


def test_framed_mc_run_writes_marked_records_under_the_framed_prompt(tmp_path, monkeypatch):
    seen = []

    class FakeRunner:
        total_spend_usd = 0.0

        def __init__(self, *a, **k):
            pass

        def map(self, jobs, on_done=None):
            for i, j in enumerate(jobs):
                seen.append(j["system"])
                on_done(i, j, SimpleNamespace(
                    ok=True, text="ANSWER: A", model_served=j["model"], served_all=None,
                    provider_model=None, stop_reason="stop", called_at="t", cost_usd=0.0,
                    input_tokens=1, output_tokens=1, duration_ms=1, attempts=1,
                    cache_hit=False, error=None))

    monkeypatch.setattr(rb, "Runner", FakeRunner)
    run_cfg, models = rb.load_configs()
    mid = models["cohort"][0]["id"]
    out = tmp_path / "framed"
    rb.run_mc(SimpleNamespace(questions="data/questions_mc.jsonl", out=str(out),
                              models=mid, runs=1, limit=2, max_parallel=1,
                              condition="framed"))
    recs = [json.loads(x) for x in (out / "mc_responses.jsonl").read_text().splitlines()]
    assert len(recs) == 2 and {r["condition"] for r in recs} == {"framed"}
    assert all(active_pack().framed_instruction in s for s in seen)
    assert json.loads((out / "config_snapshot.json").read_text())["mc"]["condition"] == "framed"
    # the same directory now refuses a neutral run
    with pytest.raises(SystemExit):
        rb.run_mc(SimpleNamespace(questions="data/questions_mc.jsonl", out=str(out),
                                  models=mid, runs=1, limit=2, max_parallel=1,
                                  condition="neutral"))


def test_standings_analysis_refuses_framed_records(tmp_path):
    p = tmp_path / "mc.jsonl"
    _write(p, [_mc("model-a", "q1", 0, True), _mc("model-a", "q2", 0, True, "framed")])
    with pytest.raises(SystemExit):
        analyze_mc(p, COHORT, seed=7, n_boot=50, ci=0.95)
    s = tmp_path / "open_scores.jsonl"
    _write(s, [_open("model-a", "q1", 0, 50.0, "framed")])
    with pytest.raises(SystemExit):
        analyze_open(s, tmp_path / "none.jsonl", COHORT, seed=7, n_boot=50, ci=0.95)


def test_merge_refuses_framed_records(tmp_path):
    _write(tmp_path / "a" / "mc_responses.jsonl", [_mc("model-a", "q1", 0, True)])
    _write(tmp_path / "b" / "mc_responses.jsonl", [_mc("model-b", "q1", 0, True, "framed")])
    with pytest.raises(ValueError):
        merge_runs([tmp_path / "a", tmp_path / "b"], tmp_path / "out")


def _two_runs(tmp_path):
    n, f = tmp_path / "neutral", tmp_path / "framed"
    # model-a: neutral right on q1 only, framed right on q1-q3 -> gap +0.5 over 4 items
    _write(n / "mc_responses.jsonl",
           [_mc("model-a", q, 0, q == "q1") for q in ("q1", "q2", "q3", "q4")]
           + [_mc("model-b", q, 0, True) for q in ("q1", "q2", "q3", "q4")])
    _write(f / "mc_responses.jsonl",
           [_mc("model-a", q, 0, q != "q4", "framed") for q in ("q1", "q2", "q3", "q4")]
           + [_mc("model-b", q, 0, True, "framed") for q in ("q1", "q2", "q3")])
    _write(n / "open_scores.jsonl",
           [_open("model-a", "o1", r, 40.0) for r in (0, 1)]
           + [_open("model-a", "o2", 0, 60.0)])
    _write(f / "open_scores.jsonl",
           [_open("model-a", "o1", 0, 70.0, "framed"),
            _open("model-a", "o2", 0, 60.0, "framed"),
            _open("model-a", "o3", 0, None, "framed")])
    return n, f


def test_gap_is_framed_minus_neutral_over_shared_items(tmp_path):
    n, f = _two_runs(tmp_path)
    out = framing.compare(n, f, COHORT, seed=7, n_boot=500, ci=0.95)
    a = out["mc"]["model-a"]
    assert (a["neutral"], a["framed"], a["n_items"]) == (0.25, 0.75, 4)
    assert a["gap"] == pytest.approx(0.5)
    assert a["lo"] <= a["gap"] <= a["hi"]
    b = out["mc"]["model-b"]                   # q4 has no framed answer: 3 shared items
    assert (b["n_items"], b["n_items_neutral_only"], b["gap"]) == (3, 1, 0.0)
    assert not b["significant_holm"]
    o = out["open"]["model-a"]                 # o1: 70 vs mean(40, 40); o2: 60 vs 60
    assert (o["neutral"], o["framed"], o["n_items"]) == (50.0, 65.0, 2)
    assert o["gap"] == pytest.approx(15.0)
    assert "model-b" not in out["open"]        # no open-ended records for it


def test_compare_is_seeded(tmp_path):
    n, f = _two_runs(tmp_path)
    assert (framing.compare(n, f, COHORT, 7, 300, 0.95)
            == framing.compare(n, f, COHORT, 7, 300, 0.95))


def test_compare_refuses_runs_given_the_wrong_way_round(tmp_path):
    n, f = _two_runs(tmp_path)
    with pytest.raises(SystemExit):
        framing.compare(f, n, COHORT, 7, 50, 0.95)
    with pytest.raises(SystemExit):
        framing.compare(n, n, COHORT, 7, 50, 0.95)


def test_report_states_the_instruction_and_marks_significance(tmp_path):
    n, f = _two_runs(tmp_path)
    out = framing.compare(n, f, COHORT, 7, 500, 0.95)
    md = framing.render(out, {"neutral": "runs/n", "framed": "runs/f", "seed": 7,
                              "n_boot": 500, "instruction": "Answer as X teaches."})
    assert "> Answer as X teaches." in md
    assert "| A | 0.250 | 0.750 | +0.500" in md
    assert "not part of the standings" in md
