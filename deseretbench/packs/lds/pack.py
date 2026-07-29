"""The Latter-day Saint pack.

This is the reference tradition and the model for every other pack. The values
below were extracted verbatim from the original ``schema``, ``judge``, and
``report`` module constants, so with this pack active the benchmark reproduces
v0.1 exactly. Authoring and reviewer content (the generation taxonomy and the
review prompts) are extracted in the authoring phase.

The framing throughout is the mainstream, official, correlated position of the
Church of Jesus Christ of Latter-day Saints — see ``data/grounding_brief.md``.
"""

from __future__ import annotations

from deseretbench.packs import Pack

# --------------------------------------------------------------------------- #
# Taxonomy
# --------------------------------------------------------------------------- #

AXES = frozenset({"doctrinal_accuracy", "cultural_fluency", "life_choice_alignment"})

MC_DIMENSIONS = frozenset({
    "doctrine_scripture", "ordinances_covenants", "church_organization",
    "eternal_family", "restoration_history", "living_gospel", "cultural_fluency",
})

OPEN_DIMENSIONS = frozenset({"life_choice", "cultural_open"})

DISTRACTOR_TYPES = frozenset({
    "correct",                       # the keyed answer
    "protestant_trap",
    "folk_doctrine_trap",
    "anti_mormon_trap",
    "progressive_trap",
    "correlation_oversimplification",
    "plausible_near_miss",
})

# Every dimension belongs to exactly one axis; a mismatch would silently pollute
# per-axis scoring downstream.
AXIS_FOR_DIMENSION = {
    "doctrine_scripture": "doctrinal_accuracy",
    "ordinances_covenants": "doctrinal_accuracy",
    "church_organization": "doctrinal_accuracy",
    "eternal_family": "doctrinal_accuracy",
    "restoration_history": "doctrinal_accuracy",
    "living_gospel": "doctrinal_accuracy",
    "cultural_fluency": "cultural_fluency",
    "life_choice": "life_choice_alignment",
    "cultural_open": "cultural_fluency",
}

# --------------------------------------------------------------------------- #
# Report labels (radar dimension order + short display names)
# --------------------------------------------------------------------------- #

DIM_ORDER = ("doctrine_scripture", "ordinances_covenants", "church_organization",
             "eternal_family", "restoration_history", "living_gospel",
             "cultural_fluency")

DIM_SHORT = {"doctrine_scripture": "Doctrine", "ordinances_covenants": "Ordinances",
             "church_organization": "Church Org", "eternal_family": "Eternal Family",
             "restoration_history": "Rest. History", "living_gospel": "Living Gospel",
             "cultural_fluency": "Cultural"}

# --------------------------------------------------------------------------- #
# Judge panel
# --------------------------------------------------------------------------- #

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

JUDGE_DIMENSIONS = ("doctrinal_accuracy", "cultural_authenticity",
                    "practical_wisdom", "distinctiveness")


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


PACK = Pack(
    key="lds",
    name="the Latter-day Saint tradition",
    report_title="DeseretBench",
    report_blurb=("a reproducible benchmark for LDS doctrinal accuracy, cultural "
                  "fluency, and life-choice alignment in large language models"),
    results_dir="results",
    reports_dir="reports",
    axes=AXES,
    mc_dimensions=MC_DIMENSIONS,
    open_dimensions=OPEN_DIMENSIONS,
    distractor_types=DISTRACTOR_TYPES,
    axis_for_dimension=AXIS_FOR_DIMENSION,
    dim_order=DIM_ORDER,
    dim_short=DIM_SHORT,
    judge_personas=JUDGE_PERSONAS,
    judge_system=JUDGE_SYSTEM,
    judge_dimensions=JUDGE_DIMENSIONS,
    build_judge_prompt=build_judge_prompt,
)
