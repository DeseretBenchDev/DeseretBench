"""A second judge family re-scores stored answers and is compared with the
primary panel. No model calls: the runner is a fake."""

import json
from types import SimpleNamespace

import pytest

from deseretbench import second_judge as sj
from deseretbench.judge import DIMENSIONS

PERSONAS = ["seminary_teacher", "byu_religion_professor", "bishop"]
MODELS = {"judges": {"primary_model": "claude-sonnet-4-6", "personas": PERSONAS}}


def _item(q):
    return {"question_id": q, "prompt": f"Situation {q}", "dimension": "life_choice",
            "difficulty": "advanced", "format": "open", "axis": "life_choice_alignment",
            "rubric": {"must_include": ["a", "b"], "should_not": ["c"],
                       "ideal_reasoning_pattern": "x"}}


def _write(path, recs):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r) for r in recs) + "\n")


def _run_dir(tmp_path, primary):
    """primary: {(model, qid, run): composite or None}"""
    d = tmp_path / "run"
    _write(d / "open_scores.jsonl",
           [{"model": m, "question_id": q, "run_index": r, "composite_100": c}
            for (m, q, r), c in primary.items()])
    _write(d / "open_responses.jsonl",
           [{"model": m, "question_id": q, "run_index": r, "text": f"{m} answers {q}"}
            for (m, q, r) in primary])
    return d


class FakeRunner:
    """Scores an answer from a table keyed by the answer text, the same way
    under every persona."""

    def __init__(self, score_of):
        self.score_of, self.jobs = score_of, []

    def map(self, jobs, on_done=None):
        self.jobs.extend(jobs)
        out = []
        for j in jobs:
            s = next(v for k, v in self.score_of.items() if k in j["prompt"])
            text = json.dumps({**{d: s for d in DIMENSIONS}, "must_include_hits": 1,
                               "must_include_total": 2, "should_not_violations": 0,
                               "justification": "ok"})
            out.append(SimpleNamespace(ok=True, text=text, model_served=j["model"],
                                       error=None, called_at="t"))
        return out


def test_family_is_the_first_name_part():
    assert sj.family("claude-sonnet-4-6") == "claude"
    assert sj.family("kimi-k3") == "kimi"
    assert sj.family("glm-5.3") == "glm"
    assert sj.family("hf.co/org/model:Q4") == "hf"


def test_second_judge_must_be_named_and_from_another_family():
    with pytest.raises(SystemExit):
        sj.judge_settings(MODELS)
    with pytest.raises(SystemExit):
        sj.judge_settings(MODELS, "claude-opus-4-8")
    j = sj.judge_settings(MODELS, "kimi-k3", "openai_compat")
    assert (j["model"], j["backend"]) == ("kimi-k3", "openai_compat")
    cfg = {"judges": {**MODELS["judges"],
                      "second": {"model": "glm-5.3", "backend": "openai_compat",
                                 "backend_opts": {"x": 1}}}}
    assert sj.judge_settings(cfg)["backend_opts"] == {"x": 1}
    # a judge named on the command line does not inherit another judge's options
    assert sj.judge_settings(cfg, "kimi-k3", "openai_compat")["backend_opts"] is None


def test_plan_takes_only_answers_the_primary_panel_scored(tmp_path):
    d = _run_dir(tmp_path, {("A", "q1", 0): 50.0, ("A", "q2", 0): None,
                            ("B", "q1", 0): 70.0, ("A", "gone", 0): 10.0})
    todo = sj.plan(d, [_item("q1"), _item("q2")], None, 1.0, 7)
    assert [(m, it["question_id"], r) for m, it, r, _ in todo] == [("A", "q1", 0), ("B", "q1", 0)]
    assert [m for m, *_ in sj.plan(d, [_item("q1")], {"B"}, 1.0, 7)] == ["B"]


def test_plan_fraction_is_seeded(tmp_path):
    d = _run_dir(tmp_path, {("A", f"q{i}", 0): 50.0 for i in range(40)})
    items = [_item(f"q{i}") for i in range(40)]
    a = sj.plan(d, items, None, 0.25, 7)
    assert len(a) == 10 and [x[:3] for x in a] == [x[:3] for x in sj.plan(d, items, None, 0.25, 7)]


def test_plan_refuses_a_framed_run(tmp_path):
    d = _run_dir(tmp_path, {("A", "q1", 0): 50.0})
    _write(d / "open_scores.jsonl", [{"model": "A", "question_id": "q1", "run_index": 0,
                                      "composite_100": 50.0, "condition": "framed"}])
    with pytest.raises(SystemExit):
        sj.plan(d, [_item("q1")], None, 1.0, 7)


def test_run_judges_every_persona_on_the_named_backend_and_keeps_out_of_the_run(tmp_path):
    d = _run_dir(tmp_path, {("A", "q1", 0): 50.0, ("B", "q1", 0): 70.0})
    todo = sj.plan(d, [_item("q1")], None, 1.0, 7)
    judge = {"model": "kimi-k3", "backend": "openai_compat", "backend_opts": None}
    with pytest.raises(SystemExit):
        sj.run(d, d, judge, PERSONAS, "medium", FakeRunner({}), todo)
    fake = FakeRunner({"A answers": 4, "B answers": 5})
    out = tmp_path / "second"
    s = sj.run(d, out, judge, PERSONAS, "medium", fake, todo)
    assert len(fake.jobs) == 6 and {j["backend"] for j in fake.jobs} == {"openai_compat"}
    assert (s["n_calls"], s["n_failed"], s["n_unparsed"]) == (6, 0, 0)
    sc = {r["model"]: r["composite_100"] for r in map(json.loads, (out / sj.SCORES).read_text().splitlines())}
    assert sc == {"A": 75.0, "B": 100.0}
    raw = [json.loads(x) for x in (out / sj.RAW).read_text().splitlines()]
    assert {r["judge_role"] for r in raw} == {"second"} and len(raw) == 6
    assert sorted(p.name for p in d.iterdir()) == ["open_responses.jsonl", "open_scores.jsonl"]


def _second(tmp_path, scores):
    out = tmp_path / "second"
    _write(out / sj.SCORES, [{"model": m, "question_id": q, "run_index": r,
                              "composite_100": c} for (m, q, r), c in scores.items()])
    return out


def test_compare_reports_answer_and_ranking_agreement(tmp_path):
    prim = {(m, f"q{i}", 0): base + i for m, base in (("A", 10), ("B", 40), ("C", 70))
            for i in range(5)}
    d = _run_dir(tmp_path, prim)
    # the second judge is 5 points harsher on everything: ranks agree, levels differ
    s = _second(tmp_path, {k: v - 5 for k, v in prim.items()})
    res = sj.compare(d, s, {"A": "Model A"}, seed=7, n_boot=500, ci=0.95)
    assert res["answers"]["n"] == 15
    assert res["answers"]["spearman_rho"] == pytest.approx(1.0)
    assert res["answers"]["mean_second_minus_primary"] == -5.0
    assert res["ranking"]["n_pairs_reordered"] == 0
    assert res["models"]["A"]["label"] == "Model A"
    assert res["models"]["C"]["rank_primary"] == res["models"]["C"]["rank_second"] == 1
    assert res["models"]["B"]["diff"] == pytest.approx(-5.0)


def test_compare_finds_a_reordered_pair_and_uses_only_shared_answers(tmp_path):
    prim = {("A", "q1", 0): 80.0, ("A", "q2", 0): 80.0,
            ("B", "q1", 0): 60.0, ("B", "q2", 0): 60.0, ("B", "q3", 0): 99.0}
    d = _run_dir(tmp_path, prim)
    s = _second(tmp_path, {("A", "q1", 0): 50.0, ("A", "q2", 0): 50.0,
                           ("B", "q1", 0): 70.0, ("B", "q2", 0): 70.0})
    res = sj.compare(d, s, {}, seed=7, n_boot=200, ci=0.95)
    assert res["answers"]["n"] == 4                   # B/q3 was never second-judged
    assert res["models"]["B"]["primary"] == 60.0
    assert res["ranking"]["n_pairs_reordered"] == 1
    md = sj.render(res, {"primary": "p", "second": "s", "n_boot": 200, "seed": 7})
    assert "1 of 1" in md and "A / B" in md and "keep the primary judge" in md


def test_compare_with_nothing_shared_is_refused(tmp_path):
    d = _run_dir(tmp_path, {("A", "q1", 0): 80.0})
    s = _second(tmp_path, {("A", "q9", 0): 50.0})
    with pytest.raises(SystemExit):
        sj.compare(d, s, {}, 7, 50, 0.95)
