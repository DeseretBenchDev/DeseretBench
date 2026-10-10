"""merge_runs: combine separately-run cohorts into one analyzable run dir."""

import json

import pytest

from deseretbench.merge_runs import merge_runs


def _write(d, name, rows):
    d.mkdir(parents=True, exist_ok=True)
    (d / name).write_text("".join(json.dumps(r) + "\n" for r in rows))


def _rec(model, q, i):
    return {"model": model, "question_id": q, "run_index": i}


def _snap(d, phases, runs=5):
    (d / "config_snapshot.json").write_text(json.dumps(
        {p: {"run_config": {"runs": {"multiple_choice": runs, "open_ended": runs}},
             "n_runs": runs} for p in phases}))


def test_concatenates_each_record_file_across_sources(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    _write(a, "mc_responses.jsonl", [_rec("m1", "q1", 0)])
    _write(b, "mc_responses.jsonl", [_rec("m2", "q1", 0), _rec("m2", "q1", 1)])
    _snap(a, ["mc"]); _snap(b, ["mc"], runs=2)
    out = tmp_path / "out"
    merge_runs([a, b], out)
    rows = [json.loads(l) for l in (out / "mc_responses.jsonl").read_text().splitlines()]
    assert [r["model"] for r in rows] == ["m1", "m2", "m2"]


def test_duplicate_record_key_across_sources_is_refused(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    _write(a, "mc_responses.jsonl", [_rec("m1", "q1", 0)])
    _write(b, "mc_responses.jsonl", [_rec("m1", "q1", 0)])
    _snap(a, ["mc"]); _snap(b, ["mc"])
    with pytest.raises(ValueError, match="duplicate"):
        merge_runs([a, b], tmp_path / "out")


def test_judge_raw_rows_keyed_by_persona_are_not_duplicates(tmp_path):
    a = tmp_path / "a"
    _write(a, "open_judge_raw.jsonl",
           [{**_rec("m1", "q1", 0), "persona": p, "judge_role": "primary"}
            for p in ("bishop", "seminary_teacher")])
    _snap(a, ["open"])
    merge_runs([a], tmp_path / "out")
    assert len((tmp_path / "out" / "open_judge_raw.jsonl").read_text().splitlines()) == 2


def test_excluded_open_models_are_dropped_from_open_files_only(tmp_path):
    a = tmp_path / "a"
    _write(a, "mc_responses.jsonl", [_rec("partial", "q1", 0)])
    _write(a, "open_scores.jsonl", [_rec("partial", "q1", 0), _rec("full", "q1", 0)])
    _snap(a, ["mc", "open"])
    out = tmp_path / "out"
    merge_runs([a], out, exclude_open={"partial"})
    assert "partial" in (out / "mc_responses.jsonl").read_text()
    scores = (out / "open_scores.jsonl").read_text()
    assert "partial" not in scores and "full" in scores


def test_snapshot_keeps_first_source_and_records_every_source(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    _write(a, "mc_responses.jsonl", [_rec("m1", "q1", 0)])
    _write(b, "mc_responses.jsonl", [_rec("m2", "q1", 0)])
    _snap(a, ["mc"], runs=5); _snap(b, ["mc"], runs=2)
    out = tmp_path / "out"
    merge_runs([a, b], out, exclude_open={"partial"})
    snap = json.loads((out / "config_snapshot.json").read_text())
    assert snap["mc"]["n_runs"] == 5                      # analyze reads the base phase
    merged = snap["merged_from"]
    assert set(merged["sources"]) == {str(a), str(b)}
    assert merged["sources"][str(b)]["mc"]["n_runs"] == 2
    assert merged["excluded_open"] == ["partial"]


def test_mixed_repeat_counts_are_stated_as_a_range_not_the_base_count(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    _write(a, "mc_responses.jsonl", [_rec("m1", "q1", 0)])
    _write(b, "mc_responses.jsonl", [_rec("m2", "q1", 0)])
    _snap(a, ["mc", "open"], runs=5); _snap(b, ["mc"], runs=2)
    merge_runs([a, b], tmp_path / "out")
    snap = json.loads((tmp_path / "out" / "config_snapshot.json").read_text())
    assert snap["mc"]["run_config"]["runs"]["multiple_choice"] == "2–5"
    assert snap["open"]["run_config"]["runs"]["open_ended"] == 5     # one source: unchanged


def test_unpinned_openai_effort_is_disclosed_in_the_effort_stamp(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    for d in (a, b):
        _write(d, "mc_responses.jsonl", [_rec(d.name, "q1", 0)])
    _write(a, "open_scores.jsonl", [_rec("a", "q1", 0)])
    for d in (a, b):
        (d / "config_snapshot.json").write_text(json.dumps(
            {p: {"n_runs": 1, "run_config": {"effort": {"multiple_choice": "low",
                                                        "open_ended": "high"}}}
             for p in ("mc", "open")}))
    merge_runs([a, b], tmp_path / "out", unpinned={"b"})
    snap = json.loads((tmp_path / "out" / "config_snapshot.json").read_text())
    assert snap["mc"]["run_config"]["effort"]["multiple_choice"] == \
        "low (openai_compat models: provider default)"
    # no unpinned model has open-ended records, so that stamp stays as configured
    assert snap["open"]["run_config"]["effort"]["open_ended"] == "high"
