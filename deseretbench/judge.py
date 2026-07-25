"""Open-ended scoring: a multi-persona LLM judge panel scores responses against
each item's rubric. Judges return strict JSON; we parse tolerantly, aggregate the
panel, and expose per-judge scores for inter-rater-reliability analysis.
"""

from __future__ import annotations

import json
import re
from typing import Optional

JUDGE_PERSONAS = {
    "seminary_teacher": (
        "an experienced Latter-day Saint seminary teacher who knows the standard works "
        "and how to explain doctrine plainly to youth"),
    "byu_religion_professor": (
        "a BYU religion professor with deep knowledge of doctrinal development, Church "
        "history, the Gospel Topics Essays, and where genuine ambiguity exists"),
    "bishop": (
        "a serving bishop who counsels members through real life decisions with both "
        "doctrinal fidelity and pastoral compassion"),
}

JUDGE_SYSTEM = (
    "You are an expert evaluator scoring another AI's written response to a question "
    "about Latter-day Saint life and doctrine. Be rigorous, fair, and concrete. "
    "Output only the requested JSON.")

DIMENSIONS = ["doctrinal_accuracy", "cultural_authenticity", "practical_wisdom", "distinctiveness"]


def build_judge_prompt(item: dict, response: str, persona_key: str) -> str:
    persona = JUDGE_PERSONAS[persona_key]
    r = item["rubric"]
    must = "\n".join(f"  - {x}" for x in r["must_include"])
    snot = "\n".join(f"  - {x}" for x in r["should_not"])
    return f"""You are {persona}.

You are scoring an AI model's response to this scenario.

SCENARIO:
{item['prompt']}

SCORING RUBRIC
The response SHOULD engage these points (must_include):
{must}
The response should NOT do these (should_not):
{snot}
Ideal Latter-day Saint reasoning pattern:
  {r['ideal_reasoning_pattern']}

MODEL RESPONSE TO SCORE:
\"\"\"
{response}
\"\"\"

Score the response on each dimension from 1 (poor) to 5 (excellent):
- doctrinal_accuracy: reflects actual mainstream LDS teaching
- cultural_authenticity: sounds like someone who understands lived LDS life
- practical_wisdom: genuinely useful counsel, not just doctrinally correct
- distinctiveness: gives a recognizably Latter-day Saint answer (not generic Christian/secular)

Also report:
- must_include_hits: integer count of the must_include points genuinely engaged
- must_include_total: total number of must_include points
- should_not_violations: integer count of should_not items the response committed

Respond with ONLY this JSON (no other text):
{{"doctrinal_accuracy": <1-5>, "cultural_authenticity": <1-5>, "practical_wisdom": <1-5>, "distinctiveness": <1-5>, "must_include_hits": <int>, "must_include_total": <int>, "should_not_violations": <int>, "justification": "<one sentence>"}}"""


def _balanced_json_candidates(text: str) -> list[str]:
    """All top-level balanced {...} spans, tracking JSON string state so braces
    inside quoted strings (e.g. a '}' in a justification) don't break the scan."""
    candidates, depth, start = [], 0, None
    in_string, escaped = False, False
    for i, ch in enumerate(text):
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"' and depth > 0:
            in_string = True
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start is not None:
                candidates.append(text[start:i + 1])
                start = None
            depth = max(depth, 0)
    return candidates


def extract_last_json(text: str) -> Optional[dict]:
    """Return the last balanced {...} block that parses as a JSON object, with no
    required-key filtering. Used for generic structured outputs (e.g. reviews)."""
    if not text:
        return None
    for blob in reversed(_balanced_json_candidates(text)):
        try:
            d = json.loads(blob)
            if isinstance(d, dict):
                return d
        except json.JSONDecodeError:
            continue
    return None


def parse_judge_json(text: str) -> Optional[dict]:
    if not text:
        return None
    for blob in reversed(_balanced_json_candidates(text)):
        try:
            d = json.loads(blob)
        except json.JSONDecodeError:
            continue
        if isinstance(d, dict) and all(k in d for k in DIMENSIONS):
            return d
    return None


def _clamp(v, lo=1, hi=5):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return max(lo, min(hi, v))


def _num(v) -> Optional[float]:
    """Non-negative float or None — never raises on judge-emitted junk."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f >= 0 else None


def aggregate_panel(judge_results: list[dict]) -> dict:
    """judge_results: list of parsed judge dicts (one per persona). Returns panel
    aggregate with composite 0-100 and per-dimension means + rubric coverage.

    Missing/malformed counts are treated as MISSING DATA (None), never as
    zero — defaulting violations to 0 would silently score bad data as clean.
    """
    dims_vals = {d: [] for d in DIMENSIONS}
    hits, totals, viol = [], [], []
    for jr in judge_results:
        if not jr:
            continue
        for d in DIMENSIONS:
            v = _clamp(jr.get(d))
            if v is not None:
                dims_vals[d].append(v)
        h, tot = _num(jr.get("must_include_hits")), _num(jr.get("must_include_total"))
        if h is not None and tot:
            hits.append(min(h, tot))  # a judge can't hit more points than exist
            totals.append(tot)
        v = _num(jr.get("should_not_violations"))
        if v is not None:
            viol.append(v)

    dim_means = {d: (sum(v) / len(v) if v else None) for d, v in dims_vals.items()}
    present = [m for m in dim_means.values() if m is not None]
    composite_5 = sum(present) / len(present) if present else None
    composite_100 = (composite_5 - 1) / 4 * 100 if composite_5 is not None else None
    coverage = (sum(hits) / sum(totals)) if totals and sum(totals) else None
    return {
        "dim_means": dim_means,
        "composite_5": composite_5,
        "composite_100": composite_100,
        "must_include_coverage": coverage,
        "mean_should_not_violations": (sum(viol) / len(viol)) if viol else None,
        "n_judges": len([j for j in judge_results if j]),
    }
