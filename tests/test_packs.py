"""Faith-pack loader + taxonomy tests.

A pack is the tradition-specific surface of the benchmark (taxonomy, judge,
report labels, and — later — authoring). These tests lock the LDS pack to the
values the benchmark shipped with (so the refactor preserves v0.1 behavior),
and prove the abstraction is real: an item validates against the *active* pack's
taxonomy, so a second tradition's dimensions validate under that pack and fail
under LDS — in the same process.
"""

import dataclasses

import pytest

import deseretbench.packs as P
from deseretbench.packs import (Pack, active_pack, list_packs, load_pack,
                                reset_pack_cache)
from deseretbench import schema, judge


@pytest.fixture(autouse=True)
def _isolate_pack(monkeypatch):
    monkeypatch.delenv("DESERETBENCH_PACK", raising=False)
    reset_pack_cache()
    yield
    reset_pack_cache()


# --------------------------------------------------------------------------- #
# Loader + resolution
# --------------------------------------------------------------------------- #


def test_lds_is_the_default_pack():
    p = active_pack()
    assert isinstance(p, Pack)
    assert p.key == "lds"


def test_env_var_selects_the_pack(monkeypatch):
    monkeypatch.setenv("DESERETBENCH_PACK", "lds")
    reset_pack_cache()
    assert active_pack().key == "lds"


def test_unknown_pack_is_a_clear_error():
    with pytest.raises(ValueError) as e:
        load_pack("no_such_tradition")
    assert "no_such_tradition" in str(e.value)


def test_list_packs_finds_lds_and_hides_underscored():
    names = list_packs()
    assert "lds" in names
    assert not any(n.startswith("_") for n in names)   # _template is not selectable


# --------------------------------------------------------------------------- #
# LDS taxonomy is locked to the shipped values (regression guard)
# --------------------------------------------------------------------------- #


def test_lds_taxonomy_matches_shipped_values():
    p = load_pack("lds")
    assert p.axes == frozenset(
        {"doctrinal_accuracy", "cultural_fluency", "life_choice_alignment"})
    assert p.mc_dimensions == frozenset({
        "doctrine_scripture", "ordinances_covenants", "church_organization",
        "eternal_family", "restoration_history", "living_gospel",
        "cultural_fluency"})
    assert p.open_dimensions == frozenset({"life_choice", "cultural_open"})
    assert "correct" in p.distractor_types
    assert "protestant_trap" in p.distractor_types
    assert p.axis_for_dimension["life_choice"] == "life_choice_alignment"
    assert p.axis_for_dimension["doctrine_scripture"] == "doctrinal_accuracy"


def test_lds_keeps_the_legacy_output_dirs():
    """The live site links reports/ and results/ directly — the LDS pack must
    not relocate them; only other packs get namespaced subdirs."""
    p = load_pack("lds")
    assert p.results_dir == "results"
    assert p.reports_dir == "reports"


# --------------------------------------------------------------------------- #
# The abstraction is real: taxonomy drives validation, per active pack
# --------------------------------------------------------------------------- #


def _mc_item(dimension, axis="doctrinal_accuracy"):
    return {"format": "mc", "axis": axis, "dimension": dimension,
            "difficulty": "basic", "question": "A well-formed question?",
            "choices": ["Alpha", "Beta", "Gamma"], "answer_index": 0,
            "source": "a source"}


def test_validation_follows_the_active_pack_taxonomy():
    lds = load_pack("lds")
    # a second tradition, same shape, different dimensions
    catholic = dataclasses.replace(
        lds, key="catholic",
        mc_dimensions=frozenset({"sacraments", "magisterium", "mariology"}),
        axis_for_dimension={**dict(lds.axis_for_dimension),
                            "sacraments": "doctrinal_accuracy",
                            "magisterium": "doctrinal_accuracy",
                            "mariology": "doctrinal_accuracy"})
    item = _mc_item("sacraments")
    assert schema.validate_mc_item(item, pack=catholic) == []      # valid here
    errs = schema.validate_mc_item(item, pack=lds)                  # not here
    assert any("dimension" in e for e in errs)


def test_validation_defaults_to_active_pack():
    # existing callers pass no pack; an LDS item validates under the default
    assert schema.validate_mc_item(_mc_item("doctrine_scripture")) == []


# --------------------------------------------------------------------------- #
# Judge config is sourced from the pack
# --------------------------------------------------------------------------- #


def test_judge_dimensions_come_from_the_pack():
    p = load_pack("lds")
    assert list(p.judge_dimensions) == [
        "doctrinal_accuracy", "cultural_authenticity",
        "practical_wisdom", "distinctiveness"]
    # judge.DIMENSIONS (imported by analyze) is bound from the pack
    assert judge.DIMENSIONS == list(p.judge_dimensions)


def test_build_judge_prompt_uses_pack_personas_and_rubric():
    p = load_pack("lds")
    item = {"prompt": "A member asks how to approach tithing during hardship.",
            "rubric": {"must_include": ["the law of tithing"],
                       "should_not": ["shame the member"],
                       "ideal_reasoning_pattern": "doctrine, then compassion"}}
    out = p.build_judge_prompt(item, "Pay a full tithe and counsel with the bishop.",
                               "bishop")
    assert "law of tithing" in out
    assert "1-5" in out or "1 (poor)" in out    # the scoring instruction is present


# --------------------------------------------------------------------------- #
# Authoring + reviewer content is sourced from the pack (phase 2b)
# --------------------------------------------------------------------------- #


def test_lds_authoring_taxonomy_is_present():
    p = load_pack("lds")
    assert isinstance(p.grounding, str) and p.grounding.strip()
    assert len(p.mc_dims) == 7                 # seven MC dimensions
    key, target, desc, subs = p.mc_dims[0]
    assert key == "doctrine_scripture"
    assert isinstance(subs, (list, tuple)) and subs
    assert len(p.open_cells) == 8
    assert set(p.diff_desc) == {"basic", "intermediate", "advanced", "expert"}


def test_mc_authoring_prompt_embeds_stance_and_rotated_subtopic():
    p = load_pack("lds")
    cell = {"kind": "mc", "dim": "doctrine_scripture",
            "desc": "the Godhead and the standard works",
            "axis": "doctrinal_accuracy", "diff": "basic", "count": 4,
            "subs": ["nature of God/Godhead", "Fall & Atonement"]}
    out = p.mc_authoring_prompt(cell)
    assert "MAINSTREAM" in out                 # the stance
    assert "nature of God/Godhead" in out      # the rotated subtopic
    assert "EXACTLY 4" in out                   # the item count


def test_lds_reviewers_present():
    p = load_pack("lds")
    assert "orthodox_member" in p.reviewers
    assert len(p.reviewers) == 5


def test_mc_review_prompt_letters_the_choices():
    p = load_pack("lds")
    item = {"dimension": "doctrine_scripture", "difficulty": "basic",
            "question": "Who comprise the Godhead?",
            "choices": ["One being in three persons", "Three distinct persons",
                        "Two persons"]}
    out = p.mc_review_prompt(item)
    assert "A. One being in three persons" in out
    assert "Who comprise the Godhead?" in out


def test_author_and_validate_modules_source_from_pack():
    import deseretbench.author as author_mod
    import deseretbench.validate_questions as vq_mod
    p = load_pack("lds")
    assert list(author_mod.MC_DIMS) == list(p.mc_dims)
    assert vq_mod.REVIEWERS == p.reviewers
    # the module-level prompt functions delegate to the active pack
    cell = {"dim": "living_gospel", "desc": "d", "axis": "doctrinal_accuracy",
            "diff": "basic", "count": 3, "subs": ["tithing & fast offerings"]}
    assert author_mod.mc_prompt(cell) == p.mc_authoring_prompt(cell)

