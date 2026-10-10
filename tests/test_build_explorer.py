"""build_explorer: the question explorer's data comes from the run records."""

from deseretbench.build_explorer import build_data

MCQ = {"question_id": "q1", "format": "mc", "dimension": "d", "difficulty": "basic",
       "axis": "doctrinal_accuracy", "question": "Which?", "choices": ["w", "r", "x"],
       "answer_index": 1, "distractor_types": ["folk", "correct", "near"],
       "source": "src", "notes": "n"}
OQ = {"question_id": "o1", "format": "open", "dimension": "cultural_open",
      "difficulty": "basic", "axis": "cultural_fluency", "prompt": "What?",
      "rubric": {"must_include": ["a"]}}
MODELS = [{"id": "big", "label": "Big", "tier": "t"},
          {"id": "small", "label": "Small", "tier": "t"},
          {"id": "mconly", "label": "McOnly", "tier": "t"}]


def _mc(model, letter, run=0, ok=True):
    return {"model": model, "question_id": "q1", "run_index": run, "call_ok": ok,
            "parsed_letter": letter, "correct": letter == "B"}


def _summary(mc_means, open_means):
    return {"mc": {"overall": {m: {"mean": v} for m, v in mc_means.items()}},
            "open": {"overall": {m: {"mean": v} for m, v in open_means.items()}}}


def _score(model, run, comp):
    return {"model": model, "question_id": "o1", "run_index": run, "composite_100": comp,
            "dim_means": {"doctrinal_accuracy": 4.04}, "must_include_coverage": 0.5}


def _build(mc_recs, scores=(), texts=()):
    return build_data(
        models=MODELS, mc_questions=[MCQ], open_questions=[OQ],
        mc_records=mc_recs, open_scores=list(scores), open_responses=list(texts),
        summary=_summary({"big": 1.0, "small": 0.5, "mconly": 1.0},
                         {"big": 90.0, "small": 10.0}))


def test_answer_distribution_counts_the_letter_each_model_picked():
    data, _ = _build([_mc("big", "B"), _mc("small", "A"), _mc("small", "C"),
                      _mc("small", None)])
    it = data["mc"][0]
    assert it["dist"] == [1, 1, 1]          # unparsed answers are not counted
    assert it["n"] == 3 and it["p"] == round(1 / 3, 3)
    assert it["missed"] == {"small": 0.0}   # accuracy over parsed answers, misses only


def test_failed_calls_are_ignored():
    data, _ = _build([_mc("big", "B"), _mc("small", "A", ok=False)])
    assert data["mc"][0]["n"] == 1 and data["mc"][0]["missed"] == {}


def test_frontier_is_every_perfect_mc_model_and_flags_their_misses():
    data, _ = _build([_mc("big", "B"), _mc("mconly", "A")])
    assert set(data["frontier"]) == {"big", "mconly"}
    assert data["mc"][0]["fmiss"] is True


def test_models_listed_by_open_composite_then_mc_only_models_without_one():
    data, _ = _build([])
    assert [m["id"] for m in data["models"]] == ["big", "small", "mconly"]
    assert data["models"][2]["comp"] is None
    assert data["meta"] == {"n_mc": 1, "n_open": 1, "n_models": 3}


def test_open_item_shows_first_run_text_and_mean_over_runs():
    scores = [_score("big", 0, 80.0), _score("big", 1, 100.0), _score("small", 0, 10.0)]
    texts = [{"model": "big", "question_id": "o1", "run_index": 0, "call_ok": True,
              "text": "first"},
             {"model": "big", "question_id": "o1", "run_index": 1, "call_ok": True,
              "text": "second"}]
    data, tx = _build([], scores, texts)
    o = data["open"][0]
    assert list(o["models"]) == ["big", "small"]
    assert o["models"]["big"] == {"comp": 80.0, "mean": 90.0, "run": 0,
                                  "dims": {"doctrinal_accuracy": 4.0}, "cov": 0.5}
    assert o["cavg"] == 50.0
    assert tx == {"o1": {"big": "first"}}
