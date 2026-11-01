"""near_duplicates lists reworded copies that the content-hash dedupe misses."""

from pathlib import Path

from deseretbench.near_duplicates import candidate_pairs, item_words, jaccard
from deseretbench.schema import load_jsonl

ROOT = Path(__file__).resolve().parent.parent


def _mc(qid, question, key):
    return {"question_id": qid, "question": question, "choices": ["other", key],
            "answer_index": 1}


def test_a_reworded_copy_scores_high_and_an_unrelated_item_low():
    a = _mc("a", "How does a member obtain a temple recommend?",
            "Two interviews with the bishopric and the stake presidency")
    b = _mc("b", "How does an adult member obtain or renew a temple recommend?",
            "Two worthiness interviews, bishopric and stake presidency")
    c = _mc("c", "Which kingdom of glory is compared to the sun?", "The celestial kingdom")
    pairs = candidate_pairs([a, b, c], min_score=0.45)
    assert [(x, y) for _, x, y in pairs] == [("a", "b")]


def test_the_keyed_answer_counts_toward_the_match():
    w = item_words(_mc("a", "Question stem", "keyed answer text"))
    assert {"keyed", "answer", "text"} <= w
    assert "church" not in item_words(_mc("b", "The Church question", "x"))


def test_jaccard_of_empty_sets_is_zero():
    assert jaccard(frozenset(), frozenset()) == 0.0


def test_the_shipped_set_still_holds_the_succession_cluster():
    # Pins the finding in DATASET_CARD.md: if a later edition removes these
    # duplicates, update the card and this test together.
    items = load_jsonl(ROOT / "data/questions_mc.jsonl")
    ids = {x for _, a, b in candidate_pairs(items, 0.45) for x in (a, b)}
    assert {"church_organization_intermediate_9852f4080b",
            "church_organization_intermediate_694f1e11c9",
            "church_organization_basic_d30e649482"} <= ids
